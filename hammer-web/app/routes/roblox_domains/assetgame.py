"""
    assetgame.roblox.com
"""

import logging
import uuid
import base64
import json
from datetime import datetime, timedelta
from quart import Blueprint, request, jsonify, make_response
from app.extensions import csrf_protect, user_limiter, remote_address_limiter, get_remote_address, redis_controller
from app.services import authentication, assets
from app.services.gameservers import server_dispatcher
from app.util.signscript import signUTF8

from app.enums.AssetType import AssetType
from app.enums.ModerationStatus import ModerationStatus
from app.enums.PlaceYear import PlaceYear
from app.models.asset import Asset
from app.models.universe import Universe
from app.models.place import Place
from app.models.user import User
from app.models.placeserver import PlaceServer

from config import Config

AssetGameRoute = Blueprint('assetgame_roblox', __name__, url_prefix='/', subdomain='assetgame')
web_config = Config()


class AssetGameException(Exception):
    pass
class AssetGameExceptions:
    class InvalidParameter(AssetGameException):
        pass

ticket_version_map = {
    PlaceYear.TwentyOne: 4
}

async def GenerateClientTicket( UserObj : User, JobId : str, CharacterURL : str | None = None, CustomTimestamp : str = "", TicketVersion : int = 1, PlaceId : int = 1) -> str:
    """
        Generates a client ticket so that RCC can verify the user is authenticated
        If CharacterURL is not None, it will be used as the character URL instead of the default
        If CustomTimestamp is not 0, it will be used as the timestamp instead of the current time
        
        Ported from SYNTAX Source code
    """
    if CustomTimestamp == "":
        CustomTimestamp = datetime.utcnow().strftime("%m/%d/%Y %I:%M:%S %p")
    if CharacterURL is None:
        if TicketVersion == 2:
            CharacterURL = str(UserObj.id) # characterAppearanceId
        elif TicketVersion == 1:
            CharacterURL = Config.BaseURL + "/Asset/CharacterFetch.ashx?userId=" + str(UserObj.id) # f"http://www.syntax.eco/v1.1/avatar-fetch?userId={str(UserObj.id)}&placeId={str(PlaceId)}"
        elif TicketVersion == 4:
            CharacterURL = f"http://avatar.{web_config.BaseDomain}/v1/avatar-fetch?userId={str(UserObj.id)}&placeId={str(PlaceId)}"
    
    FirstTicketUnsigned = f"{str(UserObj.id)}\n{UserObj.username}\n{CharacterURL}\n{JobId}\n{str(CustomTimestamp)}"
    SignedFirstTicketRaw : bytes = signUTF8(FirstTicketUnsigned, formatAutomatically=False, addNewLine=False, useNewKey=(TicketVersion > 1))
    SignedFirstTicket = base64.b64encode(SignedFirstTicketRaw).decode("utf-8")

    AccountAge = (datetime.utcnow() - UserObj.created_at).days
    UserMembershipType = "None"

    if TicketVersion <= 3:
        SecondTicketUnsigned = f"{str(UserObj.id)}\n{str(JobId)}\n{str(CustomTimestamp)}"
    elif TicketVersion == 4:
        SecondTicketUnsigned = f"{CustomTimestamp}\n{JobId}\n{UserObj.id}\n{UserObj.id}\n0\n{AccountAge}\nf\n{len(UserObj.username)}\n{UserObj.username}\n{len(UserMembershipType)}\n{UserMembershipType}\n0\n\n0\n\n{len(UserObj.username)}\n{UserObj.username}"

    SignedSecondTicketRaw : bytes = signUTF8(SecondTicketUnsigned, formatAutomatically=False, addNewLine=False, useNewKey=(TicketVersion > 1))
    SignedSecondTicket = base64.b64encode(SignedSecondTicketRaw).decode("utf-8")

    return f"{str(CustomTimestamp)};{SignedFirstTicket};{SignedSecondTicket}{f';{TicketVersion}' if TicketVersion > 1 else ''}"

@AssetGameRoute.errorhandler(AssetGameException)
async def _handle_asset_game_exception( e ):
    return await make_response( jsonify({ "status": 3, "message": str(e) }), 400 )

@AssetGameRoute.route("/Game/PlaceLauncher.ashx", methods=["POST"])
@csrf_protect.exempt
@authentication.require_authentication
@remote_address_limiter.limit("60/minute", deduct_when=lambda response: response.status_code != 200)
@remote_address_limiter.limit("240/hour", deduct_when=lambda response: response.status_code == 200)
async def _place_launcher():
    if "Roblox" not in request.headers.get("User-Agent", ""):
        return await make_response( jsonify({ "status": 3, "message": "Invalid User Agent"}), 400)
    
    request_type : str | None = request.args.get( key = "request", type = str, default = None )
    target_place_id : int | None = request.args.get( key = "placeId", type = int, default = None )
    requested_job_id : str | None = request.args.get( key = "gameId", type = str, default = None )
    
    try:
        assert request_type is not None, "Missing parameter"
        assert request_type in ["RequestGame", "RequestGameJob", "RequestPrivateGame"], "Request Type, Invalid parameter"
        if request_type in ["RequestGame", "RequestGameJob", "RequestPrivateGame"]:
            assert target_place_id is not None, "Missing parameter"
            assert target_place_id > 0, "Invalid parameter"
            assert target_place_id <= 2^64, "Invalid parameter"
        if request_type == "RequestGameJob":
            assert requested_job_id is not None, "Missing parameter"
            assert len( requested_job_id ) > 0, "Invalid parameter"
            assert len( requested_job_id ) <= 50, "Invalid parameter"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 3, "message": str(e) }), 400)
    
    authenticated_user : User = await authentication.GetCurrentUser()
    
    if request_type in ["RequestGame", "RequestGameJob", "RequestPrivateGame"]:
        place_asset_obj : Asset | None = await assets.GetAssetById( target_place_id )
        if place_asset_obj is None:
            raise AssetGameExceptions.InvalidParameter("PlaceId is invalid")
        if place_asset_obj.asset_type != AssetType.Place:
            raise AssetGameExceptions.InvalidParameter("PlaceId is invalid")
        if place_asset_obj.moderation_status != ModerationStatus.Approved:
            raise AssetGameExceptions.InvalidParameter("Place is not currently accessible")
        place_obj : Place | None = Place.query.filter_by( place_id = target_place_id ).first()
        if place_obj is None:
            raise AssetGameExceptions.InvalidParameter("PlaceId is invalid")
        universe_obj : Universe | None = Universe.query.filter_by( id = place_obj.parent_universe_id ).first()
        if universe_obj is None:
            raise AssetGameExceptions.InvalidParameter("PlaceId is invalid")
        
        if not universe_obj.is_public:
            raise AssetGameExceptions.InvalidParameter("Place is not currently accessible")
    
    target_placeserver : PlaceServer | None = None
    if request_type == "RequestGame":
        try:
            target_placeserver : PlaceServer = await server_dispatcher.get_placeserver_for_place(
                target_place = place_obj,
                user_id_context = authenticated_user.id,
                increment_redis_player_count = False
            )
        except server_dispatcher.NoGameServerAvailable:
            logging.info(f"roblox_domains.assetgame._place_launcher > NoGameServerAvailable for place {target_place_id}")
            return await make_response( jsonify({ "status": 1, "message": None }) )
        except server_dispatcher.GameServerOpenJobFailed:
            return await make_response( jsonify({ "status": 1, "message": None }) )
        except server_dispatcher.GameServerOpenJobTimeout:
            return await make_response( jsonify({ "status": 1, "message": None }) )
    elif request_type == "RequestGameJob":
        target_placeserver : PlaceServer | None = await server_dispatcher.get_place_server( target_place_id, requested_job_id )
        if target_placeserver is None:
            raise AssetGameExceptions.InvalidParameter("No servers available")
        if target_placeserver.reserved_server_access_code is not None:
            raise AssetGameExceptions.InvalidParameter("Invalid request type for reserved server")
    
    if target_placeserver.last_heartbeat is None:
        return await make_response( jsonify({ "status": 1, "message": None }) )
    if target_placeserver.max_players == await server_dispatcher.get_placeserver_player_count( target_placeserver ):
        return await make_response( jsonify({ "status": 6, "message": None }) )
    
    join_script_ticket : str = str(uuid.uuid4())
    ticket_metadata : str = json.dumps({
        "placeId": target_placeserver.place_id,
        "jobId": str(target_placeserver.server_uuid),
        "requestingIP": get_remote_address(),
        "userid": authenticated_user.id
    })
    await redis_controller.setex( f"place_server:{target_placeserver.server_uuid}:join_script_ticket:{join_script_ticket}", 90, ticket_metadata )
    return await make_response( jsonify({
        "jobId": str( target_placeserver.server_uuid ),
        "status": 2,
        "joinScriptUrl": f"http://assetgame.{web_config.BaseDomain}/Game/Join.ashx?placeId={ target_placeserver.place_id }&jobId={ target_placeserver.server_uuid }&ticket={ join_script_ticket }",
        "authenticationUrl": f"http://www.{web_config.BaseDomain}/Login/Negotiate.ashx",
        "authenticationTicket": None,
        "message": None
    }))
    
@AssetGameRoute.route("/Game/Join.ashx", methods=["GET"])
@remote_address_limiter.limit("60/minute", deduct_when=lambda response: response.status_code != 200)
async def _join_script():
    target_place_id : int | None = request.args.get( key = "placeId", type = int, default = None )
    requested_job_id : str | None = request.args.get( key = "jobId", type = str, default = None )
    join_script_ticket : str | None = request.args.get( key = "ticket", type = str, default = None )
    
    try:
        assert target_place_id is not None, "Missing parameter"
        assert target_place_id > 0, "Invalid parameter"
        assert target_place_id <= 2^64, "Invalid parameter"
        assert requested_job_id is not None, "Missing parameter"
        assert len( requested_job_id ) > 0, "Invalid parameter"
        assert len( requested_job_id ) <= 50, "Invalid parameter"
        assert join_script_ticket is not None, "Missing parameter"
        assert len( join_script_ticket ) > 0, "Invalid parameter"
        assert len( join_script_ticket ) <= 50, "Invalid parameter"
    except AssertionError as e:
        return await make_response(f"Invalid request, {str(e)}", 400)
    
    ticket_metadata : str | None = await redis_controller.get( f"place_server:{requested_job_id}:join_script_ticket:{join_script_ticket}" )
    if ticket_metadata is None:
        return await make_response("Invalid request", 400)
    ticket_metadata = json.loads( ticket_metadata )
    if ticket_metadata["placeId"] != target_place_id:
        return await make_response("Invalid request", 400)
    if ticket_metadata["jobId"] != requested_job_id:
        return await make_response("Invalid request", 400)
    requesting_address : str = get_remote_address()
    if ticket_metadata["requestingIP"] != requesting_address:
        return await make_response("Invalid request", 400)
    authenticated_user : User = authentication.get_user_by_id( ticket_metadata["userid"], return_none_on_deleted = True )
    
    await redis_controller.delete( f"place_server:{requested_job_id}:join_script_ticket:{join_script_ticket}" )
    target_placeserver : PlaceServer | None = await server_dispatcher.get_place_server( target_place_id, requested_job_id )
    if target_placeserver is None:
        return await make_response("Invalid request", 400)
    place_obj : Place | None = Place.query.filter_by( place_id = target_place_id ).first()
    universe_obj : Universe | None = Universe.query.filter_by( id = place_obj.parent_universe_id ).first()
    
    client_ticket : str = await GenerateClientTicket(
        UserObj = authenticated_user,
        JobId = requested_job_id,
        TicketVersion = ticket_version_map.get( universe_obj.place_year, 1 ),
        PlaceId = target_place_id
    )
    target_connecting_ip : str = target_placeserver.server_ip
    target_connecting_port : int = target_placeserver.server_port
    
    client_join_data : str = json.dumps({
        "ClientPort": 0,
        "MachineAddress": "127.0.0.1", #target_connecting_ip,
        "ServerConnections": [
            {
                "Port": target_connecting_port,
                "Address": "127.0.0.1", #target_connecting_ip
            }
        ],
        "ServerPort": target_connecting_port,
        "PingUrl": "",
        "PingInterval": 120,
        "UserName": authenticated_user.username,
        "DisplayName": authenticated_user.username,
        "SeleniumTestMode": False,
        "UserId": authenticated_user.id,
        "ClientTicket": client_ticket,
        "SuperSafeChat": False,
        "PlaceId": target_place_id,
        "MeasurementUrl": "",
        "WaitingForCharacterGuid": str(uuid.uuid4()),
        "BaseUrl": web_config.BaseURL,
        "ChatStyle": place_obj.chat_style.name,
        "VendorId": 0,
        "ScreenShotInfo": "",
        "VideoInfo": "",
        "CreatorId": universe_obj.creator_id,
        "CreatorTypeEnum": universe_obj.creator_type.name,
        "MembershipType": "None",
        "AccountAge": (datetime.utcnow() - authenticated_user.created_at).days,
        "CookieStoreFirstTimePlayKey": "rbx_evt_ftp",
        "CookieStoreFiveMinutePlayKey": "rbx_evt_fmp",
        "CookieStoreEnabled": True,
        "IsRobloxPlace": False,
        "UniverseId": universe_obj.id,
        "GenerateTeleportJoin": False,
        "IsUnknownOrUnder13": False,
        "SessionId": "",
        "DataCenterId": 0,
        "FollowUserId": 0,
        "BrowserTrackerId": 0,
        "UsePortraitMode": False,
        "CharacterAppearance": web_config.BaseURL + "/Asset/CharacterFetch.ashx?userId=" + str(authenticated_user.id)
                            if universe_obj.place_year in [PlaceYear.Fourteen, PlaceYear.Sixteen] else (
                             f"http://avatar.{web_config.BaseDomain}/v1.1/avatar-fetch?userId={str(authenticated_user.id)}&placeId={str(place_obj.place_id)}"
                            if universe_obj.place_year in [PlaceYear.Eighteen] else
                            f"http://avatar.{web_config.BaseDomain}/v1/avatar-fetch?userId={str(authenticated_user.id)}&placeId={str(place_obj.place_id)}" ),
        "GameId": str( target_placeserver.server_uuid ),
        "RobloxLocale": "en_us",
        "GameLocale": "en_us",
        "characterAppearanceId": authenticated_user.id
    })
    
    if universe_obj.place_year == PlaceYear.TwentyOne:
        signed_join_data : str = signUTF8( "\r\n" + client_join_data, addNewLine = False, useNewKey = True)
    
    join_response = await make_response( signed_join_data )
    return join_response