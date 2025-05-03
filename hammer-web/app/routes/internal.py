import json
import hashlib
import logging
import random
import string

from quart import Blueprint, render_template, jsonify, request, make_response
from app.extensions import csrf_protect, redis_controller, get_remote_address, db
from app.services import authentication, thumbnailer, s3manager, assets, avatar
from app.util import ipapi

from app.models.gameserver import GameServer
from app.models.user import User
from app.models.asset import Asset
from app.models.asset_version import AssetVersion
from app.enums.ThumbnailRequestTypes import ThumbnailRequestTypes
from app.enums.CreatorType import CreatorType

InternalAPIRoute = Blueprint('internal', __name__, url_prefix='/', subdomain = "internal")

@InternalAPIRoute.route("/v1/register-arbiter", methods=["POST"])
@csrf_protect.exempt
async def _register_arbiter():
    if request.is_json is False:
        return await make_response(jsonify({ "status": 0, "message": "Invalid request" }), 400)
    registration_key : str | None = request.headers.get( key = "Authorization", default = None, type = str )
    if registration_key is None:
        return await make_response(jsonify({ "status": 0, "message": "Missing parameter" }), 400)
    if authentication.verify_arbiter_registration_key( registration_key ) is False:
        return await make_response(jsonify({ "status": 0, "message": "Unauthorized" }), 403)
    json_payload : dict = await request.json
    try:
        assert "port" in json_payload, "Missing parameter"
        assert "flags" in json_payload, "Missing parameter"
        assert type( json_payload["port"] ) == int, "Invalid port number"
        assert type( json_payload["flags"] ) == int, "Invalid flags"
        assert json_payload["port"] > 0 and json_payload["port"] < 65535, "Invalid port number"
    except AssertionError as e:
        return await make_response(jsonify({ "status": 0, "message": str(e) }), 400)
    port_number : int = json_payload["port"]
    server_flags : int = json_payload["flags"]
    if await authentication.GetCurrentGameServer( verify_access_key = False ) is not None:
        return await make_response(jsonify({ "status": 0, "message": "Already registered" }), 400)
    
    server_remote_address : str = get_remote_address()
    try:
        ip_info : dict = await ipapi.fetch_ip_info( server_remote_address )
    except ipapi.InvalidIPAddress:
        return await make_response(jsonify({ "status": 0, "message": "Invalid IP address" }), 400)
    except ipapi.InternalServiceError:
        return await make_response(jsonify({ "status": 0, "message": "Internal service error" }), 500)
    server_location_info : dict = ip_info["location"]
    server_continent : str = server_location_info["continent"]
    server_country : str = server_location_info["country"]
    server_city : str = ip_info["state"]
    new_access_key : str = ''.join(random.choices(string.ascii_letters + string.digits, k = 64))
    server_hash : str = hashlib.md5( f"{server_remote_address}:{port_number}".encode() ).hexdigest()[0:5]
    
    new_gameserver : GameServer = GameServer(
        name = f"{server_continent}/{server_country}/{server_city} {server_hash}",
        arbiter_ip = server_remote_address,
        arbiter_port = port_number,
        arbiter_access_key = new_access_key,
        is_thumbnail_renderer = ( server_flags & 1 ) == 1,
        is_game_hoster = ( server_flags & 2 ) == 2,
        is_asset_validator = ( server_flags & 4 ) == 4,
    )
    db.session.add( new_gameserver )
    db.session.commit()
    
    return await make_response(jsonify({ "status": 1, "message": "Registration successful", "access_key": new_access_key, "server_ip": server_remote_address }), 200)
        
@InternalAPIRoute.route('/v1/thumbnail-render-complete', methods=['POST'])
@csrf_protect.exempt
async def _thumbnail_render_complete():
    current_gameserver : GameServer = await authentication.GetCurrentGameServer( verify_access_key = True )
    if current_gameserver is None:
        return await make_response(jsonify({ "status": 0, "message": "Unauthorized" }), 403)
    
    thumbnail_request_id : str = request.headers.get( key = "X-Hammer-Request-Id", default = None )
    if thumbnail_request_id is None:
        return await make_response(jsonify({ "status": 0, "message": "Missing parameter" }), 400)
    
    thumbnail_info_key_name : str = f"thumbnail_render_info:{thumbnail_request_id}"
    if await redis_controller.exists( thumbnail_info_key_name ) == 0:
        return await make_response(jsonify({ "status": 0, "message": "Thumbnail request not found" }), 404)
    
    thumbnail_info : dict = json.loads( await redis_controller.get( name = thumbnail_info_key_name ) )
    render_format : str = thumbnail_info["format"]
    render_result : bytes = await request.data
    if render_format.lower() == "obj":
        rendered_content_hash : str = await thumbnailer.handle_3d_obj_processing( render_result)
    else:
        rendered_content_hash : str = hashlib.sha512( render_result ).hexdigest()
    
    thumbnail_render_type : ThumbnailRequestTypes = ThumbnailRequestTypes( thumbnail_info["thumbnail_request_type"] )
    await redis_controller.delete( thumbnail_info_key_name )
    if thumbnail_render_type in [ ThumbnailRequestTypes.UserFullBody, ThumbnailRequestTypes.UserHeadshot, ThumbnailRequestTypes.Avatar_R15_Action ]:
        if thumbnail_info["user_id"] and thumbnail_info["user_id"] > 0:
            user_obj : User | None = User.query.filter_by( id = thumbnail_info["user_id"] ).first()
            user_avatar_hash : str = await avatar.generate_user_avatar_hash( user_obj)
            if user_avatar_hash == thumbnail_info["avatar_hash"]:
                """
                    Handles the possibility of the user changing their avatar while the thumbnail is being processed.
                """
                await thumbnailer.update_user_thumbnail_hash( user_obj = user_obj, render_type = thumbnail_render_type, content_hash = rendered_content_hash, is_3d_obj_hash = render_format.lower() == "obj" )
        await thumbnailer.set_avatar_thumbnail_cache(
            avatar_hash = thumbnail_info["avatar_hash"],
            render_format = render_format.lower(),
            thumbnail_request_type = thumbnail_render_type,
            content_hash = rendered_content_hash
        )
    else:
        asset_obj : Asset = Asset.query.filter_by( id = thumbnail_info["asset_id"] ).first()
        latest_asset_version : AssetVersion = await assets.GetLatestAssetVersion( AssetObj = asset_obj )
        await thumbnailer.update_asset_thumbnail_hash( asset_version_obj = latest_asset_version, content_hash = rendered_content_hash, bypass_moderation = True if asset_obj.creator_type == CreatorType.User and asset_obj.creator_id <= 2 else False, is_3d_obj_hash = render_format.lower() == "obj" )
        thumbnail_cache_lookup_name : str = f"thumbnail_render_cache:{ asset_obj.id }:{ thumbnail_render_type }:{ render_format.lower()}"
        await redis_controller.set( name = thumbnail_cache_lookup_name, value = rendered_content_hash, ex = 60 * 60 * 24 * 7 )
    
    if render_format.lower() != "obj":
        await s3manager.upload_bytes_to_s3(
            content = render_result,
            content_type = "image/png",
        )
    
    return await make_response(jsonify({ "status": 1, "message": "Thumbnail processing complete" }), 200)