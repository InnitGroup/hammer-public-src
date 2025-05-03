"""
    Handles spinning up new servers for matchmaking
"""
import uuid
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_

from app.extensions import redis_controller, db

from app.services import assets
from app.models.gameserver import GameServer
from app.models.placeserver import PlaceServer
from app.models.placeserver_player import PlaceServerPlayer
from app.models.universe import Universe
from app.models.place import Place
from app.models.asset import Asset

from app.enums.CreatorType import CreatorType
from app.enums.PlaceYear import PlaceYear
from app.services.gameservers import gameserver_comm
from app.services.gameservers.server_actions import evict_player_json

class ServerDispatcherException( Exception ):
    pass

class GameServerOpenJobTimeout( ServerDispatcherException ):
    pass
class GameServerOpenJobFailed( ServerDispatcherException ):
    pass
class NoGameServerAvailable( ServerDispatcherException ):
    pass

async def get_gameserver_by_placeplayer( target_placeserverplayer : PlaceServerPlayer ) -> GameServer | None:
    parent_placeserver : PlaceServer = PlaceServer.query.filter_by( server_uuid = target_placeserverplayer.parent_placeserver_uuid ).first()
    if parent_placeserver is None:
        return None
    return GameServer.query.filter_by( id = parent_placeserver.parent_gameserver_uuid ).first()

async def get_universe_by_placeid( place_id : int ) -> Universe | None:
    place_obj : Place = Place.query.filter_by( place_id = place_id ).first()
    if place_obj is None:
        return None
    return Universe.query.filter_by( id = place_obj.parent_universe_id ).first()

async def start_new_placeserver(
    host_game_server: GameServer,
    place_year: PlaceYear,
    target_universe: Universe,
    target_place : Place,
    max_players: int | None = None,
    reserver_server_access_code : str | None = None,

    openjob_timeout : int = 30
) -> PlaceServer:
    place_server_id = str(uuid.uuid4())
    server_comm_api_key = str(uuid.uuid4())
    
    place_asset : Asset = await assets.GetAssetById( target_place.place_id )
    latest_asset_version = await assets.GetLatestAssetVersion( place_asset )
    
    if max_players is None:
        max_players = target_place.max_players
    
    new_place_server = PlaceServer(
        server_uuid = place_server_id,
        parent_gameserver_uuid = host_game_server.id,
        server_ip = host_game_server.arbiter_ip,
        server_port = 0,
        place_id = target_place.place_id,
        place_asset_version = latest_asset_version.version_number,
        max_players = max_players,
        reserved_server_access_code = reserver_server_access_code
    )
    db.session.add( new_place_server )
    db.session.commit()
    await redis_controller.set( f"place_server:{server_comm_api_key}:api_key", f"{place_server_id}:{host_game_server.id}" )
    
    try:
        openjob_response : gameserver_comm.GameServerHttpResponse = await gameserver_comm.perform_post(
            TargetGameserver = host_game_server,
            Endpoint = "start_new_game",
            JSONData = {
                "place_id": target_place.place_id,
                "place_year": place_year.value,
                "api_key": server_comm_api_key,
                "universe_id": target_universe.id,
                "creator_id": target_universe.creator_id,
                "creator_type": target_universe.creator_type.name,
                "place_version": latest_asset_version.version_number,
                "job_id": place_server_id,
                "max_players": max_players
            },
            RequestTimeout = openjob_timeout
        )
    except Exception as e:
        logging.error( f"services.gameservers.server_dispatcher > OpenJob req FAILED on GameServer ({host_game_server.id}), exception: {e}" )
        db.session.delete( new_place_server )
        db.session.commit()
        raise GameServerOpenJobTimeout( f"Failed to start new place server" )
    
    if openjob_response.status_code != 200:
        logging.error( f"services.gameservers.server_dispatcher > OpenJob req FAILED on GameServer ({host_game_server.id}), response: {openjob_response.response_data}" )
        db.session.delete( new_place_server )
        db.session.commit()
        raise GameServerOpenJobFailed( f"Failed to start new place server" )
    
    gameserver_opened_port : int = openjob_response.response_data["port"]
    new_place_server.server_port = gameserver_opened_port
    db.session.commit()
    
    return new_place_server

async def handle_server_closing( placeserver_obj : PlaceServer ):
    all_players : list[PlaceServerPlayer] = PlaceServerPlayer.query.filter_by( parent_placeserver_uuid = placeserver_obj.server_uuid ).all()
    for player in all_players:
        db.session.delete( player )
    db.session.delete( placeserver_obj )
    db.session.commit()
    await update_universe_playing_count( await get_universe_by_placeid( placeserver_obj.place_id ) )

async def get_gameserver_servers_count( gameserver : GameServer ) -> int:
    return PlaceServer.query.filter_by( parent_gameserver_uuid = gameserver.id ).count()

async def get_place_server( target_place_id : int, server_id : str ) -> PlaceServer | None:
    return PlaceServer.query.filter_by( place_id = target_place_id, server_uuid = server_id ).first()
    

async def find_best_gameserver() -> GameServer:
    allowed_gameservers : list[ GameServer ] = GameServer.query.filter(
        and_(
            GameServer.is_game_hoster == True,
            GameServer.last_heartbeat > datetime.utcnow() - timedelta( seconds = 40 )
        )
    ).all()
    if allowed_gameservers is None or len( allowed_gameservers ) == 0:
        raise NoGameServerAvailable( "No game servers available" )
    not_busy_gameservers : list[ GameServer ] = []
    for gameserver in allowed_gameservers:
        if await get_gameserver_servers_count( gameserver ) > 5:
            continue
        not_busy_gameservers.append( gameserver )
    if len( not_busy_gameservers ) == 0:
        raise NoGameServerAvailable( "No game servers available" )
    
    not_busy_gameservers.sort( key = lambda x: x.memory_usage )
    return not_busy_gameservers[0]

async def get_placeserver_player_count( place_server : PlaceServer ) -> int:
    players_joining = await redis_controller.get( f"place_server:{place_server.server_uuid}:players_joining" ) or 0
    return place_server.player_count + players_joining

async def increment_players_joining( place_server : PlaceServer, user_id : int ) -> None:
    await decrement_players_joining( place_server, user_id ) # If the user somehow managed to get here twice in 15 seconds
    await redis_controller.incr( f"place_server:{place_server.server_uuid}:players_joining" )
    await redis_controller.setex( f"place_server:{place_server.server_uuid}:player:{user_id}", 60, "1" )
    async def handle_decrement_task():
        await asyncio.sleep( 15 )
        if await redis_controller.exists( f"place_server:{place_server.server_uuid}:player:{user_id}" ) > 0:
            await redis_controller.decr( f"place_server:{place_server.server_uuid}:players_joining" )
            await redis_controller.delete( f"place_server:{place_server.server_uuid}:player:{user_id}" )
    asyncio.create_task( handle_decrement_task() )

async def decrement_players_joining( place_server : PlaceServer, user_id : int ) -> None:
    if await redis_controller.exists( f"place_server:{place_server.server_uuid}:player:{user_id}" ) == 0:
        return
    await redis_controller.decr( f"place_server:{place_server.server_uuid}:players_joining" )
    await redis_controller.delete( f"place_server:{place_server.server_uuid}:player:{user_id}" )

async def get_placeserver_for_place(
    target_place : Place,
    reserver_server_access_code : str | None = None,
    
    allow_new_server : bool = True,
    increment_redis_player_count : bool = True,
    user_id_context : int | None = None,
    bypass_start_cooldown : bool = False
) -> PlaceServer:
    place_asset : Asset = await assets.GetAssetById( target_place.place_id )
    latest_asset_version = await assets.GetLatestAssetVersion( place_asset )
    
    available_place_servers : list[ PlaceServer ] = PlaceServer.query.filter(
        and_(
            PlaceServer.place_id == target_place.place_id,
            PlaceServer.place_asset_version == latest_asset_version.version_number,
            PlaceServer.reserved_server_access_code == reserver_server_access_code,
            PlaceServer.player_count < PlaceServer.max_players
        )
    ).all()
    if available_place_servers is not None and len( available_place_servers ) > 0:
        for placeserver in available_place_servers:
            if placeserver.server_port == 0:
                continue
            actual_player_count = await get_placeserver_player_count( placeserver )
            if actual_player_count >= placeserver.max_players:
                continue
            if increment_redis_player_count and user_id_context:
                await increment_players_joining( placeserver, user_id_context )
            return placeserver
    
    if not allow_new_server:
        raise NoGameServerAvailable( "No place servers available" )
    placeserver_start_cooldown_key = f"place_server:{target_place.place_id}:{reserver_server_access_code}:start_cooldown"
    if not bypass_start_cooldown and await redis_controller.exists( placeserver_start_cooldown_key ) > 0:
        raise NoGameServerAvailable( "Place server start cooldown" )
    await redis_controller.setex( placeserver_start_cooldown_key, 15, "1" )
    
    place_universe : Universe = Universe.query.filter_by( id = target_place.parent_universe_id ).first()
    
    host_gameserver : GameServer = await find_best_gameserver()
    new_place_server : PlaceServer = await start_new_placeserver(
        host_game_server = host_gameserver,
        place_year = place_universe.place_year,
        target_universe = place_universe,
        target_place = target_place,
        max_players = target_place.max_players,
        reserver_server_access_code = reserver_server_access_code
    )
    
    if increment_redis_player_count and user_id_context:
        await increment_players_joining( placeserver, user_id_context )
    
    return new_place_server

async def update_universe_playing_count( universe_obj : Universe ) -> None:
    child_places : list[ Place ] = Place.query.filter_by( parent_universe_id = universe_obj.id ).all()
    total_playing_count = 0
    for place in child_places:
        running_place_servers : list[ PlaceServer ] = PlaceServer.query.filter_by( place_id = place.place_id ).all()
        for server in running_place_servers:
            total_playing_count += server.player_count
            
    universe_obj.active_player_count = total_playing_count
    db.session.commit()

async def handle_player_joining( place_server : PlaceServer, user_id : int ):
    existing_player_check : PlaceServerPlayer | None = PlaceServerPlayer.query.filter_by( user_id = user_id ).first()
    if existing_player_check is not None:
        parent_gameserver : GameServer = await get_gameserver_by_placeplayer( existing_player_check )
        if parent_gameserver is not None:
            asyncio.create_task( 
                evict_player_json(
                    target_gameserver = parent_gameserver,
                    server_jobid = str( place_server.server_uuid ),
                    player_id = user_id
                )
            )
        db.session.delete( existing_player_check )
        db.session.commit()
    
    place_obj : Place = Place.query.filter_by( place_id = place_server.place_id ).first()
    universe_obj : Universe = Universe.query.filter_by( id = place_obj.parent_universe_id ).first()
    
    if universe_obj.creator_id != user_id and universe_obj.creator_type == CreatorType.User:
        place_obj.visit_count += 1
        universe_obj.visit_count += 1
        db.session.commit()