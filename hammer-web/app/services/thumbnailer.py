import uuid
import json
import logging
import hashlib
import aiofiles
import base64
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_

from app.services import avatar, assets, s3manager

from app.models.user import User
from app.models.user_avatar import UserAvatar
from app.models.user_thumbnail import UserThumbnail
from app.models.asset import Asset
from app.models.asset_thumbnail import AssetThumbnail
from app.models.asset_version import AssetVersion
from app.models.gameserver import GameServer
from app.models.asset import Asset
from app.models.avatar_thumbnails_cache import AvatarThumbnailsCache
from app.enums.ThumbnailRequestTypes import ThumbnailRequestTypes
from app.enums.ModerationStatus import ModerationStatus
from app.enums.CreatorType import CreatorType
from app.enums.AssetType import AssetType
from app.enums.RigType import RigType

from app.extensions import redis_controller, db
from app.services.gameservers import gameserver_comm

asset_render_type_lookup : dict[ AssetType, ThumbnailRequestTypes ] = {
    AssetType.Image : ThumbnailRequestTypes.Image,
    AssetType.TShirt : ThumbnailRequestTypes.TShirt,
    AssetType.Mesh : ThumbnailRequestTypes.Mesh,
    AssetType.Hat : ThumbnailRequestTypes.AvatarHat,
    AssetType.Place : ThumbnailRequestTypes.Place,
    AssetType.Model : ThumbnailRequestTypes.Model,
    AssetType.Shirt : ThumbnailRequestTypes.Shirt,
    AssetType.Pants : ThumbnailRequestTypes.Pants,
    AssetType.Decal : ThumbnailRequestTypes.Image,
    AssetType.Head : ThumbnailRequestTypes.AvatarHead,
    AssetType.Face : ThumbnailRequestTypes.Image,
    AssetType.Gear : ThumbnailRequestTypes.AvatarGear,
    AssetType.Torso : ThumbnailRequestTypes.AvatarBodypart,
    AssetType.RightArm : ThumbnailRequestTypes.AvatarBodypart,
    AssetType.LeftArm : ThumbnailRequestTypes.AvatarBodypart,
    AssetType.LeftLeg : ThumbnailRequestTypes.AvatarBodypart,
    AssetType.RightLeg : ThumbnailRequestTypes.AvatarBodypart,
    AssetType.Package : ThumbnailRequestTypes.Package,
    AssetType.MeshPart : ThumbnailRequestTypes.MeshPart,
    AssetType.HairAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.FaceAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.NeckAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.ShoulderAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.FrontAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.BackAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.WaistAccessory : ThumbnailRequestTypes.AvatarHat,
    AssetType.EmoteAnimation : ThumbnailRequestTypes.AnimationSilhouette
}

class RenderServiceExceptions():
    class UnsupportedThumbnailType( Exception ):
        pass
    class ThumbnailRenderCooldown( Exception ):
        pass
    class NoGameserverAvailable( Exception ):
        pass
    class ThumbnailRenderRequestFailed( Exception ):
        pass
    class BadRenderData( Exception ):
        pass
    
async def get_user_by_id( user_id : int | User ) -> User | None:
    if isinstance( user_id, User ):
        return user_id
    return User.query.filter_by( id = user_id ).first()

async def get_asset_by_id( asset_id : int | Asset ) -> Asset | None:
    if isinstance( asset_id, Asset ):
        return asset_id
    return Asset.query.filter_by( id = asset_id ).first()

async def find_best_thumbnailer( ) -> GameServer | None:
    weight_ping_time = 3
    weight_queue_size = 0.3
    
    available_gameservers : list[GameServer] = GameServer.query.filter( and_(GameServer.thumbnail_queue_size < 40, GameServer.response_time > 0, GameServer.is_thumbnail_renderer == True ) ).all()
    if len(available_gameservers) == 0:
        return None
    selected_gameserver : GameServer | None = None
    
    for GameServerObject in available_gameservers:
        GameServerObject.score = (weight_ping_time * GameServerObject.response_time) + (weight_queue_size * GameServerObject.thumbnail_queue_size)
        if selected_gameserver is None:
            selected_gameserver = GameServerObject
            continue
        if GameServerObject.score < selected_gameserver.score:
            selected_gameserver = GameServerObject
    return selected_gameserver

async def get_user_thumbnail_obj( user_obj : User | int ) -> UserThumbnail:
    user_obj : User = await get_user_by_id( user_obj )
    user_thumbnail_obj : UserThumbnail | None = UserThumbnail.query.filter_by( user_id = user_obj.id ).first()
    if user_thumbnail_obj is None:
        user_thumbnail_obj = UserThumbnail( user_obj.id )
        db.session.add( user_thumbnail_obj )
        db.session.commit()
    
    return user_thumbnail_obj

async def update_asset_thumbnail_hash( asset_version_obj : AssetVersion, content_hash : str, bypass_moderation : bool = False, is_3d_obj_hash : bool = False ) -> None:
    asset_thumbnail_obj : AssetThumbnail | None = AssetThumbnail.query.filter_by( asset_id = asset_version_obj.asset_id, asset_version = asset_version_obj.version_number ).first()
    if asset_thumbnail_obj is None:
        if not is_3d_obj_hash:
            asset_thumbnail_obj = AssetThumbnail( asset_version_obj.asset_id, asset_version_obj.version_number, content_hash, moderation_status = ModerationStatus.Approved if bypass_moderation else ModerationStatus.AwaitingApproval )
        else:
            asset_thumbnail_obj = AssetThumbnail( asset_version_obj.asset_id, asset_version_obj.version_number, None, moderation_status = ModerationStatus.Approved if bypass_moderation else ModerationStatus.AwaitingApproval, asset_3d_content_hash = content_hash )
        db.session.add( asset_thumbnail_obj )
    else:
        if not is_3d_obj_hash:
            asset_thumbnail_obj.content_hash = content_hash
        else:
            asset_thumbnail_obj.asset_3d_content_hash = content_hash
        asset_thumbnail_obj.moderation_status = ModerationStatus.Approved if bypass_moderation else ModerationStatus.AwaitingApproval
    db.session.commit()

async def get_asset_thumbnail_obj( asset_obj : Asset | int, version_number : int | None = None ) -> AssetThumbnail | None:
    asset_obj : Asset = await get_asset_by_id( asset_obj )
    requested_asset_version : AssetVersion = await assets.GetLatestAssetVersion( asset_obj ) if version_number is None else await assets.GetAssetVersionByVersionNumber( asset_obj, version_number )
    if requested_asset_version is None: 
        return None
    
    asset_thumbnail_obj : AssetThumbnail = AssetThumbnail.query.filter_by( asset_id = asset_obj.id, asset_version = requested_asset_version.version_number ).first()
    return asset_thumbnail_obj

async def update_user_thumbnail_hash( user_obj : User, render_type : ThumbnailRequestTypes, content_hash : str, is_3d_obj_hash : bool = False ) -> None:
    user_thumbnail_obj : UserThumbnail = await get_user_thumbnail_obj( user_obj )
    if render_type == ThumbnailRequestTypes.UserFullBody or render_type == ThumbnailRequestTypes.Avatar_R15_Action:
        if not is_3d_obj_hash:
            user_thumbnail_obj.fullbody_content_hash = content_hash
            user_thumbnail_obj.last_fullbody_updated = datetime.utcnow()
        else:
            user_thumbnail_obj.body_3d_content_hash = content_hash
            user_thumbnail_obj.last_body_3d_updated = datetime.utcnow()
    elif render_type == ThumbnailRequestTypes.UserHeadshot:
        if is_3d_obj_hash:
            raise RenderServiceExceptions.UnsupportedThumbnailType( "3D object hashes are not supported for headshots" )
        user_thumbnail_obj.headshot_content_hash = content_hash
        user_thumbnail_obj.last_headshot_updated = datetime.utcnow()
        
    db.session.commit()
    
async def set_avatar_thumbnail_cache( avatar_hash : str, render_format : str, thumbnail_request_type : ThumbnailRequestTypes, content_hash : str ) -> None:
    cache_obj : AvatarThumbnailsCache | None = AvatarThumbnailsCache.query.filter_by( avatar_hash = avatar_hash, render_format = render_format, thumbnail_request_type = thumbnail_request_type ).first()
    if cache_obj is None:
        cache_obj = AvatarThumbnailsCache( avatar_hash, render_format, thumbnail_request_type, content_hash )
        db.session.add( cache_obj )
    else:
        cache_obj.content_hash = content_hash
    db.session.commit()

async def submit_thumbnail_request(
    thumbnail_type : ThumbnailRequestTypes,
    user_id : int | None = None,
    asset_id : int | None = None,
    render_width : int = 512,
    render_height : int = 512,
    render_format : str = "PNG",
    
    avatar_hash : str | None = None
) -> str:
    request_id : str = str( uuid.uuid4() )
    request_data = {
        "thumbnail_request_type" : thumbnail_type.value,
        "user_id" : user_id,
        "asset_id" : asset_id,
        "width" : render_width,
        "height" : render_height,
        "format" : render_format,
        "request_id" : request_id,
        "avatar_hash" : avatar_hash
    }
    selected_gameserver : GameServer | None = await find_best_thumbnailer()
    if selected_gameserver is None:
        raise RenderServiceExceptions.NoGameserverAvailable( "No gameservers available to render the thumbnail" )
    server_response : gameserver_comm.GameServerHttpResponse = await gameserver_comm.perform_post(
        TargetGameserver = selected_gameserver,
        Endpoint = "thumbnail_render",
        JSONData = request_data,
        RequestTimeout = 20
    )
    if server_response.status_code != 200:
        logging.error( f"thumbnailer.submit_thumbnail_request: Thumbnail render request failed with status code {server_response.status_code}, response: { server_response.response_data }" )
        raise RenderServiceExceptions.ThumbnailRenderRequestFailed( f"Thumbnail render request failed with status code {server_response.status_code}" )
    await redis_controller.set( f"thumbnail_render_info:{request_id}", json.dumps( request_data ), ex = 60 * 20 )
    return request_id

async def handle_static_image( asset_obj : Asset, asset_version_obj : AssetVersion ) -> None:
    if asset_obj.asset_type.value not in [ 39, 3, 24, 5, 48,49,50,51,52,53,54,55,56 ]:
        raise RenderServiceExceptions.UnsupportedThumbnailType( f"Unsupported asset type {asset_obj.asset_type}" )
    static_image_path : str = "./app/files/NoRender.png"
    if asset_obj.asset_type == AssetType.Audio:
        static_image_path = "./app/files/AudioThumbnail.png"
    elif asset_obj.asset_type in [ 
        AssetType.Animation, AssetType.ClimbAnimation, AssetType.DeathAnimation, AssetType.FallAnimation, AssetType.IdleAnimation, 
        AssetType.JumpAnimation, AssetType.RunAnimation, AssetType.SwimAnimation, AssetType.WalkAnimation, AssetType.PoseAnimation
    ]:
        static_image_path = "./app/files/AnimationThumbnail.png"
    elif asset_obj.asset_type == AssetType.Lua:
        static_image_path = "./app/files/LuaThumbnail.png"
    async with aiofiles.open( static_image_path, "rb" ) as file:
        image_bytes = await file.read()
    static_image_hash : str = hashlib.sha512( image_bytes ).hexdigest()
    if not await s3manager.does_object_exist_in_s3( static_image_hash ):
        await s3manager.upload_bytes_to_s3(
            content = image_bytes,
            content_type = "image/png"
        )
    await update_asset_thumbnail_hash( asset_version_obj, static_image_hash, bypass_moderation = True if asset_obj.creator_type == CreatorType.User and asset_obj.creator_id <= 2 else False )

async def render_asset_thumbnail( asset_obj : Asset, render_type : ThumbnailRequestTypes | None = None, bypass_cooldown : bool = False, bypass_cache : bool = False, render_format : str = "PNG" ):
    """
        Renders an asset's thumbnail

        :param asset_obj: The asset to render the thumbnail for
        :param render_type: The type of thumbnail to render, will automatically be determined if not specified
        :param bypass_cooldown: Whether or not to bypass the render cooldown
        :param bypass_cache: Whether or not to bypass the cache by looking up the asset's version hash
    """
    LatestAssetVersion : AssetVersion = await assets.GetLatestAssetVersion( asset_obj )
    thumbnail_cache_lookup : str = f"thumbnail_render_cache:{ LatestAssetVersion.content_hash }:{ render_type }:{render_format.lower()}"
    if not bypass_cache and await redis_controller.exists( thumbnail_cache_lookup ) > 0:
        render_content_hash = await redis_controller.get( thumbnail_cache_lookup )
        await update_asset_thumbnail_hash( asset_obj, render_content_hash, bypass_moderation = True if asset_obj.creator_type == CreatorType.User and asset_obj.creator_id <= 2 else False )
        return
    thumbnail_render_cooldown : str = f"thumbnail_cooldown_{LatestAssetVersion.content_hash}:{render_type}:{render_format.lower()}"
    if not bypass_cooldown and await redis_controller.exists( thumbnail_render_cooldown ) > 0:
        raise RenderServiceExceptions.ThumbnailRenderCooldown( f"Asset hash {LatestAssetVersion.content_hash} is on cooldown" )
    if render_type is None:
        if asset_obj.asset_type in asset_render_type_lookup:
            render_type = asset_render_type_lookup[ asset_obj.asset_type ]
        else:
            return await handle_static_image( asset_obj, LatestAssetVersion )
    await redis_controller.set( thumbnail_render_cooldown, "1", ex = 5 )
    await submit_thumbnail_request(
        thumbnail_type = render_type,
        asset_id = asset_obj.id,
        render_width = 768,
        render_height = 768,
        render_format = render_format
    )
    
    logging.debug(f"thumbnailer.render_asset_thumbnail: sent render request of {render_type} for asset {asset_obj.id} (version {LatestAssetVersion.version_number})")

async def render_avatar_thumbnail( avatar_hash : str, render_type : ThumbnailRequestTypes = ThumbnailRequestTypes.UserFullBody, bypass_cooldown : bool = False, bypass_cache : bool = False, render_format : str = "PNG" ) -> None:
    """
        Renders an avatar's thumbnail
        ! Please call avatar.build_avatar_fetch_response before calling this function to populate the cache
        
        :param avatar_hash: The hash of the avatar to render the thumbnail for
        :param render_type: The type of thumbnail to render
        :param bypass_cooldown: Whether or not to bypass the render cooldown
        :param bypass_cache: Whether or not to bypass the cache by looking up the avatar's hash
        :param render_format: The format to render the thumbnail in
    """
    if render_type not in [ ThumbnailRequestTypes.UserFullBody, ThumbnailRequestTypes.UserHeadshot ]:
        raise RenderServiceExceptions.UnsupportedThumbnailType( f"Unsupported thumbnail type {render_type}" )
    
    if not bypass_cache:
        thumbnail_cache_query : AvatarThumbnailsCache | None = AvatarThumbnailsCache.query.filter_by( avatar_hash = avatar_hash, render_format = render_format, thumbnail_request_type = render_type ).first()
        if thumbnail_cache_query is not None and thumbnail_cache_query.created_at > datetime.now( timezone.utc ) - timedelta( days = 31 ):
            return
    
    if not bypass_cooldown and await redis_controller.exists( f"thumbnail_cooldown_{avatar_hash}:{render_type}:{render_format.lower()}" ) > 0:
        raise RenderServiceExceptions.ThumbnailRenderCooldown( f"Avatar hash {avatar_hash} is on cooldown" )
    
    await redis_controller.set( f"thumbnail_cooldown_{avatar_hash}:{render_type}:{render_format.lower()}", "1", ex = 15 )
    await submit_thumbnail_request(
        thumbnail_type = render_type,
        render_width = 768,
        render_height = 768,
        render_format = render_format,
        avatar_hash = avatar_hash,
        user_id = 0
    )
    
    logging.debug(f"thumbnailer.render_avatar_thumbnail: sent render request of {render_type} for avatar {avatar_hash}")

async def render_user_thumbnail( user_obj : User, render_type : ThumbnailRequestTypes = ThumbnailRequestTypes.UserFullBody, bypass_cooldown : bool = False, bypass_cache : bool = False, render_format : str = "PNG" ) -> None:
    """
        Renders a user's thumbnail

        :param user_obj: The user to render the thumbnail for
        :param render_type: The type of thumbnail to render
        :param bypass_cooldown: Whether or not to bypass the render cooldown
        :param bypass_cache: Whether or not to bypass the cache by looking up the user's avatar hash
        :param render_format: The format to render the thumbnail in
    """
    if render_type not in [ ThumbnailRequestTypes.UserFullBody, ThumbnailRequestTypes.UserHeadshot ]:
        raise RenderServiceExceptions.UnsupportedThumbnailType( f"Unsupported thumbnail type {render_type}" )

    if render_type == ThumbnailRequestTypes.UserFullBody:
        user_avatar_obj : UserAvatar = await avatar.get_user_avatar_obj( user_obj )
        if user_avatar_obj.rig_type == RigType.R15:
            render_type = ThumbnailRequestTypes.Avatar_R15_Action

    user_avatar_hash : str = await avatar.generate_user_avatar_hash( user_obj )
    if not bypass_cache:
        thumbnail_cache_query : AvatarThumbnailsCache | None = AvatarThumbnailsCache.query.filter_by( avatar_hash = user_avatar_hash, render_format = render_format, thumbnail_request_type = render_type ).first()
        if thumbnail_cache_query is not None and thumbnail_cache_query.created_at > datetime.utcnow() - timedelta( days = 31 ):
            await update_user_thumbnail_hash( user_obj, render_type, thumbnail_cache_query.content_hash, is_3d_obj_hash = render_format.lower() == "obj" )
            return

    if not bypass_cooldown and await redis_controller.exists( f"thumbnail_cooldown_{user_avatar_hash}:{render_type}:{render_format.lower()}" ) > 0:
        raise RenderServiceExceptions.ThumbnailRenderCooldown( f"Avatar hash {user_avatar_hash} is on cooldown" )

    await redis_controller.set( f"thumbnail_cooldown_{user_avatar_hash}:{render_type}:{render_format.lower()}", "1", ex = 15 )
    await avatar.build_avatar_fetch_response( user_obj = user_obj, avatar_hash = user_avatar_hash ) # Populate the cache
    await submit_thumbnail_request(
        thumbnail_type = render_type,
        user_id = user_obj.id,
        render_width = 768,
        render_height = 768,
        render_format = render_format,
        avatar_hash = user_avatar_hash
    )
    
    logging.debug(f"thumbnailer.render_user_thumbnail: sent render request of {render_type} for user {user_obj.id}")
    
async def handle_3d_obj_processing( render_results : bytes ) -> str:
    """
        Handles the data for RCCService's 3D object processing and returns
        a content hash for the metadata of the processed object
        
        :param render_results: The results of the render
        
        :return: str: The content hash of the obj metadata
    """
    
    try:
        parsed_data : dict = json.loads( render_results )
        assert "camera" in parsed_data, "Missing 'camera' key in JSON data"
        assert "AABB" in parsed_data, "Missing 'AABB' key in JSON data"
        assert "files" in parsed_data, "Missing 'files' key in JSON data"
        assert type( parsed_data["camera"] ) == dict, "Invalid 'camera' key in JSON data"
        assert type( parsed_data["AABB"] ) == dict, "Invalid 'AABB' key in JSON data"
        assert type( parsed_data["files"] ) == dict, "Invalid 'files' key in JSON data"
    except json.JSONDecodeError:
        raise RenderServiceExceptions.BadRenderData( "Failed to parse JSON data" )

    scene_obj_bytes : bytes | None = None
    scene_mtl_bytes : bytes | None = None
    scene_textures : list[ bytes ] = []
    scene_text_hash : list[ str ] = []
    
    for file_key, file_dict in parsed_data["files"].items():
        file_key : str
        file_dict : dict
        if "content" not in file_dict:
            raise RenderServiceExceptions.BadRenderData( f"Missing 'content' key in file {file_key}" )
        parsed_content : bytes = base64.b64decode( file_dict["content"] )
        if file_key.endswith(".obj"):
            scene_obj_bytes = parsed_content
        elif file_key.endswith(".mtl"):
            scene_mtl_bytes = parsed_content
        else:
            texture_content_hash = hashlib.sha512( parsed_content ).hexdigest() 
            scene_textures.append( parsed_content )
            scene_text_hash.append( texture_content_hash )
            
            decoded_scene_mtl : str = scene_mtl_bytes.decode()
            decoded_scene_mtl = decoded_scene_mtl.replace( file_key, texture_content_hash )
            scene_mtl_bytes = decoded_scene_mtl.encode()
    
    if scene_obj_bytes is None or scene_mtl_bytes is None or len( scene_textures ) == 0:
        raise RenderServiceExceptions.BadRenderData( "Missing scene data" )
    obj_render_metadata : bytes = json.dumps({
        "camera" : parsed_data["camera"],
        "aabb" : parsed_data["AABB"],
        "mtl": hashlib.sha512( scene_mtl_bytes ).hexdigest(),
        "obj": hashlib.sha512( scene_obj_bytes ).hexdigest(),
        "textures": scene_text_hash
    }).encode()
    
    s3_upload_jobs : list = []
    s3_upload_jobs.append( s3manager.upload_bytes_to_s3( scene_obj_bytes, content_type = "text/plain" ) )
    s3_upload_jobs.append( s3manager.upload_bytes_to_s3( scene_mtl_bytes, content_type = "text/plain" ) )
    s3_upload_jobs.append( s3manager.upload_bytes_to_s3( obj_render_metadata, content_type = "application/json" ) )
    for texture_bytes in scene_textures:
        s3_upload_jobs.append( s3manager.upload_bytes_to_s3( texture_bytes, content_type = "image/png" ) )
    
    await asyncio.gather( *s3_upload_jobs )
    obj_render_metadata_hash : str = hashlib.sha512( obj_render_metadata ).hexdigest()
    return obj_render_metadata_hash

async def queue_full_user_render(
    user_obj : User,
    clear_previous_thumbnails : bool = True,
    bypass_cooldown : bool = False,
    bypass_cache : bool = False,
    synchronous_queue : bool = False
) -> None:
    """
        Queues a FullBody 2D, Headshot 2D and Body 3D render for a user
    """
    if clear_previous_thumbnails:
        user_thumbnail_obj : UserThumbnail = await get_user_thumbnail_obj( user_obj )
        user_thumbnail_obj.fullbody_content_hash = None
        user_thumbnail_obj.headshot_content_hash = None
        user_thumbnail_obj.body_3d_content_hash = None
        db.session.commit()
    
    if not synchronous_queue:
        asyncio.create_task( render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserFullBody, render_format = "obj", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown ) )
        asyncio.create_task( render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserFullBody, render_format = "PNG", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown ) )
        asyncio.create_task( render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserHeadshot, render_format = "PNG", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown ) )
    else:
        await render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserFullBody, render_format = "obj", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown )
        await render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserFullBody, render_format = "PNG", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown )
        await render_user_thumbnail( user_obj = user_obj, render_type = ThumbnailRequestTypes.UserHeadshot, render_format = "PNG", bypass_cache = bypass_cache, bypass_cooldown = bypass_cooldown )