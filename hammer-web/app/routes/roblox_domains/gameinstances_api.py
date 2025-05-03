"""
    gameinstances.api.roblox.com
"""
import asyncio
from datetime import datetime, timedelta
from quart import Blueprint, request, jsonify, make_response, abort, g
from app.extensions import redis_controller, get_remote_address, csrf_protect, db
from app.models.gameserver import GameServer
from app.models.placeserver import PlaceServer
from app.models.placeserver_player import PlaceServerPlayer

from app.services.gameservers import server_dispatcher, server_actions
from app.services import authentication

GameinstancesAPIRoute = Blueprint("gameinstances_api", __name__, url_prefix="/", subdomain="gameinstances.api")

@GameinstancesAPIRoute.before_request
async def _verify_request():
    gameserver_obj : GameServer | None = await authentication.GetCurrentGameServer( verify_access_key = False )
    if gameserver_obj is None:
        abort( 404 )
    g.gameserver = gameserver_obj
    
@GameinstancesAPIRoute.route("/v2/CreateOrUpdate/", methods=["POST"])
@csrf_protect.exempt
async def _create_or_update():
    reporting_gameserver : GameServer = g.gameserver
    authentication_apikey : str | None = request.args.get( "apiKey", type = str, default = None )
    if authentication_apikey is None:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Missing API Key" } ] }), 400 )
    gameId : str | None = request.args.get( "gameId", type = str, default = None )
    authentication_metadata : str = await redis_controller.get( f"place_server:{authentication_apikey}:api_key" )
    if authentication_metadata != f"{gameId}:{reporting_gameserver.id}":
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid API Key" } ] }), 400 )
    
    place_server_obj : PlaceServer | None = PlaceServer.query.filter_by( server_uuid = gameId ).first()
    if place_server_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid Game ID" } ] }), 400 )
    
    place_server_obj.last_heartbeat = datetime.utcnow()
    try:
        server_data : list[dict] = await request.get_json()
    except:
        return await make_response( jsonify({ "errors": [ { "code": 4, "message": "Invalid JSON" } ] }), 400 )
    server_player_data = server_data["GameSessions"]
    player_count : int = len( server_player_data )
    last_reported_players : list[PlaceServerPlayer] = PlaceServerPlayer.query.filter_by( parent_placeserver_uuid = place_server_obj.server_uuid ).all()
    leaving_users : list[ int ] = []
    joining_users : list[PlaceServerPlayer] = []
    
    for player in last_reported_players:
        if player.user_id not in [ player_data["UserId"] for player_data in server_player_data ]:
            leaving_users.append( player.user_id )
            db.session.delete( player )
            continue
        player.last_heartbeat = datetime.utcnow()
    
    for player_data in server_player_data:
        user_id : int = player_data["UserId"]
        if user_id in [ player.user_id for player in last_reported_players ]:
            continue
        await server_dispatcher.handle_player_joining( place_server_obj, user_id )
        newPlayer : PlaceServerPlayer = PlaceServerPlayer(
            parent_placeserver_uuid = place_server_obj.server_uuid,
            user_id = user_id
        )
        db.session.add( newPlayer )
        joining_users.append( newPlayer )
        asyncio.create_task( server_dispatcher.decrement_players_joining( place_server_obj, user_id ) )
    
    place_server_obj.player_count = player_count
    db.session.commit()
    if len( leaving_users ) > 0 or len( joining_users ) > 0:
        asyncio.create_task( server_dispatcher.update_universe_playing_count( await server_dispatcher.get_universe_by_placeid( place_server_obj.place_id ) ) )
    if await server_dispatcher.get_placeserver_player_count( place_server_obj ) == 0 and place_server_obj.created_at < datetime.utcnow() - timedelta( seconds = 90 ):
        asyncio.create_task( server_dispatcher.handle_server_closing( place_server_obj ) )
    
    return await make_response( "OK", 200 )

@GameinstancesAPIRoute.route("/v1/Close/", methods=["POST"])
@csrf_protect.exempt
async def _report_closing():
    reporting_gameserver : GameServer = g.gameserver
    authentication_apikey : str | None = request.args.get( "apiKey", type = str, default = None )
    if authentication_apikey is None:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Missing API Key" } ] }), 400 )
    gameId : str | None = request.args.get( "gameId", type = str, default = None )
    authentication_metadata : str = await redis_controller.get( f"place_server:{authentication_apikey}:api_key" )
    if authentication_metadata != f"{gameId}:{reporting_gameserver.id}":
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid API Key" } ] }), 400 )
    
    place_server_obj : PlaceServer | None = PlaceServer.query.filter_by( server_uuid = gameId ).first()
    if place_server_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid Game ID" } ] }), 400 )
    await server_dispatcher.handle_server_closing( place_server_obj )
    return await make_response( "OK", 200 )

@GameinstancesAPIRoute.route("/v1/instance-killed", methods=["POST"])
@csrf_protect.exempt
async def _instance_killed_report():
    reporting_gameserver : GameServer | None = await authentication.GetCurrentGameServer()
    if reporting_gameserver is None:
        return abort( 404 )
    server_uuid : str | None = request.args.get( "server_uuid", type = str, default = None )
    if server_uuid is None:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Missing server_uuid" } ] }), 400 )
    place_server_obj : PlaceServer | None = PlaceServer.query.filter_by( server_uuid = server_uuid ).first()
    if place_server_obj is not None:
        await server_dispatcher.handle_server_closing( place_server_obj )
    return await make_response( "OK", 200 )