"""
    Handles all APIs used by the frontend
"""
import logging
from quart_wtf.csrf import CSRFError, generate_csrf
from quart import Blueprint, request, jsonify, make_response, url_for, Response, websocket
from app.services.authentication import AuthenticationExceptions, GetCurrentUser
from app.extensions import csrf_protect, redis_controller
from app.models.user import User

from config import Config

web_config = Config()

WebAPIRoute = Blueprint('web_api', __name__, url_prefix='/web-api')

@WebAPIRoute.before_request
async def before_request():
    if request.method in ["POST", "PUT", "DELETE"]:
        await csrf_protect.protect()

@WebAPIRoute.errorhandler( AuthenticationExceptions.UserNotAuthenticated )
async def handle_user_not_authenticated( error ):
    return jsonify({
        "status": 0,
        "message": "This endpoint requires authentication"
    }), 401

@WebAPIRoute.errorhandler( 429 )
async def handle_429( error ):
    return jsonify({
        "status": 11,
        "message": "Too many requests"
    }), 429

@WebAPIRoute.errorhandler( 405 )
async def handle_405( error ):
    return jsonify({
        "status": 12,
        "message": "Method not allowed"
    }), 405

@WebAPIRoute.errorhandler( CSRFError )
async def handle_csrf_error( error ):
    resp = await make_response(jsonify({
        "status": 13,
        "message": "CSRF Token Validation Failed"
    }), 400)
    resp.headers["X-CSRFToken"] = generate_csrf()
    return resp

from app.routes.web_api.authentication.login import LoginHandler
WebAPIRoute.register_blueprint( LoginHandler, url_prefix = "/" )
from app.routes.web_api.authentication.register import RegistrationHandler
WebAPIRoute.register_blueprint( RegistrationHandler, url_prefix = "/" )
from app.routes.web_api.authentication.auth_ticket import AuthenticationTicketRoute
WebAPIRoute.register_blueprint( AuthenticationTicketRoute, url_prefix = "/" )
from app.routes.web_api.economy import EconomyHandler
WebAPIRoute.register_blueprint( EconomyHandler, url_prefix = "/" )
from app.routes.web_api.accountsettings import AccountSettingsHandler
WebAPIRoute.register_blueprint( AccountSettingsHandler, url_prefix = "/" )
from app.routes.web_api.friends import FriendsHandler
WebAPIRoute.register_blueprint( FriendsHandler, url_prefix = "/friends" )

@WebAPIRoute.route("/endpoints-lookup", methods=["GET"])
async def _endpoints_lookup():
    endpoint_resp = await make_response( jsonify({
        "success": True,
        "endpoints": {
            "login": url_for("web_api.login._login", _scheme = "https", _external = True),
            "login_two_factor": url_for("web_api.login._login_two_factor", _scheme = "https", _external = True),
            "register": url_for("web_api.register._handle_register", _scheme = "https", _external = True),
            "logout": url_for("web_api.login._logout", _scheme = "https", _external = True),
            "economy_get_balance": url_for("web_api.economy_web_api.economy_balance._get_user_balance", _scheme = "https", _external = True),
            "friend_status": url_for("web_api.friends_web_api.friends_relationship._get_friend_status", _scheme = "https", _external = True),
            "friends_request_friendship": url_for("web_api.friends_web_api.friends_relationship._request_friendship", _scheme = "https", _external = True),
            "unfriend_user": url_for("web_api.friends_web_api.friends_relationship._unfriend_user", _scheme = "https", _external = True),
            "revoke_friend_request": url_for("web_api.friends_web_api.friends_relationship._revoke_friend_request", _scheme = "https", _external = True),
            "following_status": url_for("web_api.friends_web_api.follow_relationship._get_follow_status", _scheme = "https", _external = True),
            "follow_user": url_for("web_api.friends_web_api.follow_relationship._follow_user", _scheme = "https", _external = True),
            "unfollow_user": url_for("web_api.friends_web_api.follow_relationship._unfollow_user", _scheme = "https", _external = True),
            "create_auth_ticket": url_for("web_api.authentication_ticket._create_authentication_ticket", _scheme = "https", _external = True),
            "user_3d_avatar_thumb": url_for("thumbnails_roblox._user_avatar_3d", _scheme = "https", _external = True),
            "user_2d_avatar_thumb": url_for("thumbnails_roblox._fullbody_avatar", _scheme = "https", _external = True),
            "user_inventory_sort_assettype": url_for("inventory_roblox._get_user_inventory_by_assettype", _scheme = "https", _external = True, asset_type = 1234, user_id = 5678).replace("5678", "<user_id>").replace("1234", "<asset_type>"),
            "thumbnail_asset": url_for("thumbnails_roblox._asset_thumbnail", _scheme = "https", _external = True),
            "thumbnail_user_status": url_for("thumbnails_roblox._user_thumbnail_status", _scheme = "https", _external = True, user_id = 1234 ).replace("1234", "<user_id>"),
            "avatar_rules": url_for("avatar_roblox._v1_avatar_rules", _scheme = "https", _external = True),
            "avatar_self": url_for("avatar_roblox._v1_fetch_authenticated_avatar", _scheme = "https", _external = True),
            "avatar_set_rig_type": url_for("avatar_roblox._set_avatar_rig_type", _scheme = "https", _external = True),
            "avatar_set_body_scales": url_for("avatar_roblox._set_avatar_scales", _scheme = "https", _external = True),
            "avatar_set_body_colors": url_for("avatar_roblox._set_avatar_body_colors", _scheme = "https", _external = True),
            "avatar_set_wearing_assets": url_for("avatar_roblox._set_avatar_wearing_assets", _scheme = "https", _external = True),
            "avatar_set_emote_position": url_for("avatar_roblox._set_avatar_emote", _scheme = "https", _external = True, emote_id = 1234, position = 5678).replace("1234", "<emote_id>").replace("5678", "<position>"),
            "base_url": f"{web_config.BaseURL}",
            "cdn_url": f"{web_config.CDN_URL}",
        }
    }), 200 )
    endpoint_resp.headers["Cache-Control"] = "public, max-age=300, must-revalidate"

    return endpoint_resp