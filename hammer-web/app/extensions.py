import quart_flask_patch
import logging
import asyncio
import aiohttp
import time
from datetime import datetime, timedelta

from quart import request, g
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter, HEADERS
from quart_wtf.csrf import CSRFProtect

from config import Config

web_config = Config()

def get_remote_address():
    """
        Gets the remote address of the request in the current flask context
    """
    CloudflareReportingAddress = request.headers.get( key = "CF-Connecting-IP", default = None )
    if CloudflareReportingAddress is not None:
        return CloudflareReportingAddress
    return request.remote_addr

def get_user_identifier():
    from app.models.user import User
    user_obj : User | None = g.CurrentUser
    if user_obj is None:
        return "anonymous"
    return f"user_{user_obj.id}"

csrf_protect = CSRFProtect()
db = SQLAlchemy()
redis_controller = web_config.AIO_REDIS_CLIENT
sync_redis_controller = web_config.SYNC_REDIS_CLIENT

remote_address_limiter = Limiter(
    get_remote_address,

    storage_uri = Config.FLASK_LIMITED_STORAGE_URI,
    strategy = "fixed-window-elastic-expiry",
    headers_enabled = True,
    key_prefix = "address_limiter"
)

user_limiter = Limiter(
    get_user_identifier,
    
    storage_uri = Config.FLASK_LIMITED_STORAGE_URI,
    strategy = "fixed-window-elastic-expiry",
    headers_enabled = True,
    key_prefix = "user_limiter"
)

async def GameserverHeartbeatTask():
    """
        Background loop to send a heartbeat request to all gameservers
    """
    from app.models.gameserver import GameServer
    from app.models.placeserver import PlaceServer
    from app.services.gameservers import gameserver_comm, server_dispatcher, server_actions

    async def _hearbeat() -> None:
        try:
            if await redis_controller.exists( "gameserver_heartbeat_cooldown" ) > 0:
                return
            await redis_controller.set( "gameserver_heartbeat_cooldown", "1", ex = 20 )
            AllGameservers : list[GameServer] = GameServer.query.all()
            HearbeatJobs = []

            async def _handle_unresponsive_server( TargetServer : GameServer ) -> None:
                all_running_placeservers : list[PlaceServer] = PlaceServer.query.filter_by( parent_gameserver_uuid = TargetServer.id ).all()
                if all_running_placeservers is None or len( all_running_placeservers ) == 0:
                    return
                for placeserver in all_running_placeservers:
                    await server_dispatcher.handle_server_closing( placeserver )    

            async def _perform_heartbeat_on_server( TargetServer : GameServer ) -> None:
                serverResponseTime : float = 0
                serverMemoryUsage : float = 0
                serverMemorySize : float = 0
                serverProcessorUsage : float = 0
                serverCores : int = 0
                try:
                    request_start = time.time()
                    ServerResponse : gameserver_comm.GameServerHttpResponse = await gameserver_comm.perform_get(
                        TargetGameserver = TargetServer,
                        Endpoint = "info",
                        RequestTimeout = 5
                    )
                    if ServerResponse.status_code != 200:
                        logging.error( f"extensions > GameserverHeartbeatTask._perform_heartbeat_on_server: GameServer {TargetServer.id} returned status code {ServerResponse.status_code}" )
                    else:            
                        JSONResponse = ServerResponse.response_data
                        TargetServer.last_heartbeat = datetime.utcnow()
                        serverResponseTime = time.time() - request_start
                        serverMemoryUsage = JSONResponse.get( "memory_usage", 0 )
                        serverMemorySize = JSONResponse.get( "memory_size", 0 )
                        serverProcessorUsage = JSONResponse.get( "cpu_usage", 0 )
                        serverCores = JSONResponse.get( "cores", 0 )
                        running_instances = JSONResponse.get( "running_instances", [] )
                        last_reported_instances : list[PlaceServer] = PlaceServer.query.filter_by( parent_gameserver_uuid = TargetServer.id ).all() or []
                        for instance in last_reported_instances:
                            if str(instance.server_uuid) not in [ x["server_uuid"] for x in running_instances ]:
                                logging.info( f"extensions > GameserverHeartbeatTask._perform_heartbeat_on_server: GameServer {TargetServer.id} reported instance {instance.server_uuid} not existing" )
                                await server_dispatcher.handle_server_closing( instance )
                        for instance in running_instances:
                            instance_obj : PlaceServer | None = PlaceServer.query.filter_by( server_uuid = instance["server_uuid"] ).first()
                            if instance_obj is None:
                                await server_actions.request_close_server_instance( TargetServer, instance["server_uuid"], reason_type = "Roblox" )
                                continue
    
                except aiohttp.ServerTimeoutError:
                    if TargetServer.last_heartbeat is not None and datetime.utcnow() - TargetServer.last_heartbeat > timedelta( seconds = 90 ):
                        await _handle_unresponsive_server( TargetServer )
                    logging.error( f"extensions > GameserverHeartbeatTask._perform_heartbeat_on_server: GameServer {TargetServer.id} timed out" )
                except aiohttp.ClientConnectionError:
                    pass
                except Exception as e:
                    if TargetServer.last_heartbeat is not None and datetime.utcnow() - TargetServer.last_heartbeat > timedelta( seconds = 90 ):
                        await _handle_unresponsive_server( TargetServer )
                    logging.error( f"extensions > GameserverHeartbeatTask._perform_heartbeat_on_server: { type(e) }, {str(e)}" )

                TargetServer.response_time = serverResponseTime
                TargetServer.memory_usage = serverMemoryUsage
                TargetServer.memory_size = serverMemorySize
                TargetServer.processor_usage = serverProcessorUsage
                TargetServer.processor_cores = serverCores
                db.session.commit()

            for Server in AllGameservers:
                HearbeatJobs.append( _perform_heartbeat_on_server( Server ) )
            await asyncio.gather( *HearbeatJobs )
        except Exception as e:
            logging.error( f"extensions > GameserverHeartbeatTask._hearbeat: {str(e)}" )

    while True:
        await asyncio.sleep( 20 )
        try:
            await _hearbeat()
        except Exception as e:
            logging.error( f"extensions > GameserverHeartbeatTask: {str(e)}" )

async def AssetThumbnailTask():
    """
        Background loop to render broken asset thumbnails
    """
    from app.models.asset import Asset
    from app.models.asset_version import AssetVersion
    from app.models.asset_thumbnail import AssetThumbnail
    from app.enums.AssetType import AssetType
    from app.enums.ModerationStatus import ModerationStatus
    from app.services import thumbnailer
    from sqlalchemy import and_
    
    async def _heartbeat() -> None:
        try:
            if await redis_controller.exists( "asset_thumbnail_heartbeat_cooldown" ) > 0:
                return
            await redis_controller.set( "asset_thumbnail_heartbeat_cooldown", "1", ex = 40 )
            
            assetVersions : list[ AssetVersion ] = AssetVersion.query.filter(
            ~db.session.query(AssetThumbnail.asset_id).filter(
                AssetThumbnail.asset_id == AssetVersion.asset_id,
            ).filter(
                AssetThumbnail.asset_version == AssetVersion.version_number
            ).exists()
            ).join(Asset, Asset.id == AssetVersion.asset_id).filter(
                and_(
                    Asset.moderation_status == ModerationStatus.Approved #,
                    #Asset.asset_type != AssetType.Place
                )
            ).distinct(AssetVersion.asset_id).order_by(AssetVersion.asset_id, AssetVersion.version_number.desc()).limit( 30 ).all()
            async def _process_asset_version( AssetVersionObj : AssetVersion ) -> None:
                logging.info( f"extensions > AssetThumbnailTask._heartbeat._process_asset_version: Processing asset version {AssetVersionObj.id} ( asset_id { AssetVersionObj.asset_id })" )
                try:
                    asset_obj : Asset = Asset.query.filter_by( id = AssetVersionObj.asset_id ).first()
                    await thumbnailer.render_asset_thumbnail(
                        asset_obj = asset_obj
                    )
                except thumbnailer.RenderServiceExceptions.NoGameserverAvailable:
                    return
                except thumbnailer.RenderServiceExceptions.ThumbnailRenderCooldown:
                    return
                except thumbnailer.RenderServiceExceptions.ThumbnailRenderRequestFailed:
                    return
                except Exception as e:
                    logging.error( f"extensions > AssetThumbnailTask._heartbeat._process_asset_version: {str(e)}" )
            for AssetVersionObj in assetVersions:
                await _process_asset_version( AssetVersionObj )
            
        except KeyboardInterrupt:
            raise KeyboardInterrupt()
        except Exception as e:
            logging.error( f"extensions > AssetThumbnailTask._heartbeat: {str(e)}" )
    while True:
        await asyncio.sleep( 60 )
        try:
            await _heartbeat()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error( f"extensions > AssetThumbnailTask: {str(e)}" )

async def UserThumbnailTask():
    """
        Background loop to render broken user thumbnails
    """
    from app.models.user import User
    from app.models.user_thumbnail import UserThumbnail
    from app.enums.ThumbnailRequestTypes import ThumbnailRequestTypes
    from app.services import thumbnailer
    from sqlalchemy import or_
    async def _heartbeat() -> None:
        try:
            if await redis_controller.exists( "user_thumbnail_heartbeat_cooldown" ) > 0:
                return
            await redis_controller.set( "user_thumbnail_heartbeat_cooldown", "1", ex = 20 )
            
            broken_user_thumbnails : list[UserThumbnail] = UserThumbnail.query.filter(
                or_(
                    UserThumbnail.fullbody_content_hash == None,
                    UserThumbnail.headshot_content_hash == None,
                    UserThumbnail.body_3d_content_hash == None
                )
            ).limit( 20 ).all()
            render_jobs = []
            
            async def _handle_broken_thumbnail( UserThumbnailObj : UserThumbnail, selected_render_type : ThumbnailRequestTypes, is_3d : bool = False ) -> None:
                try:
                    user_obj : User = User.query.filter_by( id = UserThumbnailObj.user_id ).first()                    
                    try:
                        await thumbnailer.render_user_thumbnail(
                            user_obj = user_obj,
                            render_type = selected_render_type,
                            render_format = "obj" if is_3d else "png",
                            bypass_cache = True
                        )
                    except thumbnailer.RenderServiceExceptions.NoGameserverAvailable:
                        return
                    except thumbnailer.RenderServiceExceptions.ThumbnailRenderCooldown:
                        return
                    except thumbnailer.RenderServiceExceptions.ThumbnailRenderRequestFailed:
                        return
                    except Exception as e:
                        logging.error( f"extensions > UserThumbnailTask._heartbeat._handle_broken_thumbnail: exceptipon raised during render_user_thumbnail {str(e)}" )
                    
                    if UserThumbnailObj.headshot_content_hash is None and selected_render_type == ThumbnailRequestTypes.UserFullBody:
                        await _handle_broken_thumbnail( UserThumbnailObj, selected_render_type = ThumbnailRequestTypes.UserHeadshot )
                    
                except Exception as e:
                    logging.error( f"extensions > UserThumbnailTask._heartbeat._handle_broken_thumbnail: {str(e)}" )
                    
            for UserThumbnailObj in broken_user_thumbnails:
                selected_render_type = ThumbnailRequestTypes.UserFullBody if UserThumbnailObj.fullbody_content_hash is None or UserThumbnailObj.body_3d_content_hash is None else ThumbnailRequestTypes.UserHeadshot
                is_3d = True if selected_render_type == ThumbnailRequestTypes.UserFullBody and UserThumbnailObj.fullbody_content_hash is not None else False
                render_jobs.append( _handle_broken_thumbnail( UserThumbnailObj, selected_render_type, is_3d = is_3d ) )
            
            await asyncio.gather( *render_jobs )
        except Exception as e:
            logging.error( f"extensions > UserThumbnailTask._heartbeat: {str(e)}" )
        
    while True:
        await asyncio.sleep( 60 )
        try:
            await _heartbeat()
        except Exception as e:
            logging.error( f"extensions > UserThumbnailTask: {str(e)}" )