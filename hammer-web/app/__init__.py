import quart_flask_patch
import os
import mimetypes
mimetypes.add_type("application/javascript", ".js")
import logging
import hashlib
import aiofiles
from logging.handlers import TimedRotatingFileHandler

from quart import Quart, request, redirect, make_response, render_template, request, jsonify, Response
from quart.helpers import safe_join
from datetime import datetime

from app.extensions import db, csrf_protect, remote_address_limiter, user_limiter, GameserverHeartbeatTask, UserThumbnailTask, AssetThumbnailTask
from app.services import authentication
from app.models.user import User
from app.enums.AccountStatus import AccountStatus

from config import Config

logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)
logname = "./logs/hammer-web.log"
handler = TimedRotatingFileHandler(logname, when="midnight", backupCount=30)
handler.suffix = "%Y%m%d"

logging.getLogger().addHandler(handler)

def create_app( config_class = Config ):
    quart_app = Quart( __name__, template_folder = "pages", static_folder = None, static_url_path = f"/static" )
    quart_app.config.from_object( config_class )
    quart_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    quart_app.config["SECRET_KEY"] = config_class.FLASK_SESSION_KEY
    quart_app.config["CORS_HEADERS"] = "Content-Type"
    quart_app.config["SESSION_TYPE"] = "redis"
    quart_app.config["SESSION_REDIS"] = config_class.AIO_REDIS_CLIENT
    quart_app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    quart_app.config["SERVER_NAME"] = config_class.BaseDomain
    quart_app.config["WTF_CSRF_ENABLED"] = True
    quart_app.config["WTF_CSRF_CHECK_DEFAULT"] = False
    quart_app.config["WTF_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]
    quart_app.config["WTF_CSRF_FIELD_NAME"] = "csrf_token"
    quart_app.config["WTF_CSRF_HEADERS"] = ["X-CSRFToken", "X-CSRF-Token"]
    quart_app.config["BACKGROUND_TASK_SHUTDOWN_TIMEOUT"] = 0
    quart_app.static_folder = "static"
    quart_app.add_url_rule(
        '/static/<path:filename>',
        endpoint='static',
        subdomain = "www",
        view_func = quart_app.send_static_file
    )

    db.init_app( quart_app )
    user_limiter.init_app( quart_app )
    remote_address_limiter.init_app( quart_app )
    csrf_protect.init_app( quart_app )

    quart_app.jinja_env.globals.update( datetime_utcnow = datetime.utcnow, len = len, round = round )

    def _get_request_main_domain() -> str:
        request_host = request.host.split(".")
        if len(request_host) < 2:
            return request.host
        return ".".join(request_host[-2:])

    def _get_request_subdomain_by_string( full_domain : str ) -> str:
        splitted_domain = full_domain.split(".")
        if len(splitted_domain) < 3:
            return None
        return ".".join(splitted_domain[:-2])

    def _get_request_subdomain() -> str | None:
        return _get_request_subdomain_by_string( request.host )

    @quart_app.errorhandler( authentication.AuthenticationExceptions.UserNotAuthenticated )
    async def _handle_user_not_authenticated( e ):
        if _get_request_subdomain() == "www":
            notauthenticated_response = await make_response( redirect( "/login" ) )
        else:
            notauthenticated_response = await make_response( jsonify({
                "status": 0,
                "message": "This endpoint requires authentication"
            }), 401 )
        
        UserRobloSecurity = request.cookies.get( ".ROBLOSECURITY", None )
        if UserRobloSecurity is not None:
            notauthenticated_response.set_cookie( ".ROBLOSECURITY", "", expires = 0 )
        
        return notauthenticated_response
    
    @quart_app.errorhandler( 429 )
    async def _handle_too_many_requests( e ):
        if _get_request_subdomain() == "www":
            return await render_template( "error_pages/too_many_requests.html"), 429
        return await make_response( jsonify({
            "status": 0,
            "message": "Too many requests"
        }), 429 )
    
    @quart_app.errorhandler( 405 )
    async def _handle_method_not_allowed( e ):
        return await make_response( jsonify({
            "status": 0,
            "message": "Method not allowed"
        }), 405 )
    
    @quart_app.errorhandler( 404 )
    async def _handle_not_found( e ):
        if _get_request_subdomain() == "www":
            return await render_template( "error_pages/not_found.html"), 404
        return await make_response( jsonify({
            "status": 0,
            "message": "Resource not found"
        }), 404)

    @quart_app.errorhandler( authentication.AuthenticationExceptions.InsufficientPermissions )
    @quart_app.errorhandler( 403 )
    async def _handle_not_found( e ):
        if _get_request_subdomain() == "www":
            return await render_template( "error_pages/forbidden.html"), 403
        return await make_response( jsonify({
            "status": 0,
            "message": "Insufficient permissions to access this resource"
        }), 403)

    @quart_app.before_request
    async def _before_request():
        if "Roblox-Id" in request.headers:
            return await make_response( "Forbidden, bad header", 403 )
        RequestAccessKey = request.headers.get( "AccessKey", None )
        if "UserRequest" == RequestAccessKey:
            return await make_response( "Forbidden, bad header", 403 )
        Requester = request.headers.get( "requester", None )
        if "ROBLOX" not in request.user_agent.string and request.method == "GET" and Requester is None:
            CloudflareScheme = request.headers.get( "CF-Visitor", None )
            if CloudflareScheme is not None and "https" not in CloudflareScheme:
                return redirect(request.url.replace("http://", "https://", 1), code=301)
            
        AuthenticatedUser : User = await authentication.GetCurrentUser()
        if AuthenticatedUser is not None:
            if AuthenticatedUser.account_status == AccountStatus.Active:
                AuthenticatedUser.lastonline_at = datetime.utcnow()
                db.session.commit()
    
    @quart_app.after_request
    async def _cors_handler( response : Response ):
        if "ROBLOX" in request.user_agent.string:
            return response
        
        # TODO: debugging for webclient remove later
        response.headers["Access-Control-Allow-Origin"] = f"http://localhost:6931"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, X-CSRF-Token, Cache-Control, Requester"
        
        if _get_request_main_domain() != config_class.BaseDomain:
            return response
        req_referer = request.headers.get("Referer", None)
        if req_referer is None:
            return response
        try:
            req_referer = req_referer.split("//")[1].split("/")[0]
        except Exception:
            return response
        requesting_from_subdomain = _get_request_subdomain_by_string( req_referer )
        if requesting_from_subdomain is None:
            return response
        requested_subdomain = _get_request_subdomain()
        if requested_subdomain is None:
            return response
        if requesting_from_subdomain != requested_subdomain:
            response.headers["Access-Control-Allow-Origin"] = f"https://{requesting_from_subdomain}.{config_class.BaseDomain}"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, X-CSRF-Token, Cache-Control, Requester"
        return response
    
    @quart_app.context_processor
    async def _inject_user():
        return {
            "current_user": await authentication.GetCurrentUser()
        }
    
    @quart_app.before_serving
    async def _before_serving():
        quart_app.add_background_task( GameserverHeartbeatTask )
        quart_app.add_background_task( UserThumbnailTask )
        quart_app.add_background_task( AssetThumbnailTask)
        db.create_all()
        
        async def temp():
            import json
            from app.services import clientsettings
            with open("./ClientAppSettings.json", "r") as f:
                settings = json.load(f)
            await clientsettings.parse_client_settings(
                target_group_obj = await clientsettings.get_client_settings_group_by_name( group_name = "ClientAppSettings", api_key = "D6925E56-BFB9-4908-AAA2-A5B1EC4B2D79" ),
                new_settings = settings
            )
        #quart_app.add_background_task( temp )
    
    @quart_app.after_serving
    async def _after_serving():
        db.session.close()
        db.engine.dispose()
        return

    # https://stackoverflow.com/questions/18092380/serving-changing-files-with-flask
    hash_cache = {}
    @quart_app.url_defaults
    def add_hash_for_static_files(endpoint, values):
        '''
        Add content hash argument for url to make url unique.
        It's have sense for updates to avoid caches.
        '''
        if endpoint != 'static':
            return
        filename = values['filename']
        if config_class.CACHE_STATIC_FILE_HASHES and filename in hash_cache:
            values['ver'] = hash_cache[filename]
            return
        filepath = safe_join(quart_app.static_folder, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'rb') as static_file:
                filehash = hashlib.md5(static_file.read()).hexdigest()
                values['ver'] = hash_cache[filename] = filehash
                
    
    from app.pages.pages import PagesRoute
    from app.routes.web_api.web import WebAPIRoute
    from app.routes.asset import AssetRoute
    from app.routes.clientsettings import ClientSettingsRoute
    from app.routes.versioncompatibility import VersionCompatibilityRoute
    from app.routes.mobileapi import MobileAPIRoute
    from app.routes.roblox_domains.apiroblox import APIRobloxRoute, APIssRobloxRoute
    from app.routes.roblox_domains.ecsv2 import ECSV2Route
    from app.routes.roblox_domains.authentication import AuthRoute
    from app.routes.roblox_domains.locale import LocaleRoute
    from app.routes.roblox_domains.economy import EconomyRoute
    from app.routes.roblox_domains.avatar import AvatarRoute
    from app.routes.roblox_domains.catalog import CatalogRoute
    from app.routes.internal import InternalAPIRoute
    from app.routes.roblox_domains.thumbnails import ThumbnailRoute
    from app.pages.profile.user_profile_handler import UserProfileHandler
    from app.routes.roblox_domains.assetgame import AssetGameRoute
    from app.routes.roblox_domains.gameinstances_api import GameinstancesAPIRoute
    from app.routes.roblox_domains.textfilter import TextFilterRoute
    from app.routes.roblox_domains.groups import GroupsRoute
    from app.routes.roblox_domains.gamepersistence import GamePersistenceRoute
    from app.pages.avatar_editor.editor_handler import AvatarEditorPageHandler
    from app.routes.roblox_domains.inventory import InventoryAPIRoute
    from app.routes.roblox_domains.friends import FriendsRoute
    from app.routes.roblox_domains.presence import PresenceAPIRoute
    quart_app.register_blueprint( PagesRoute, url_prefix = "/" )
    quart_app.register_blueprint( WebAPIRoute, url_prefix = "/web-api", subdomain = "www" )
    quart_app.register_blueprint( AssetRoute, url_prefix = "/" )
    quart_app.register_blueprint( ClientSettingsRoute, url_prefix = "/" )
    quart_app.register_blueprint( VersionCompatibilityRoute, url_prefix = "/", subdomain = "versioncompatibility.api" )
    quart_app.register_blueprint( MobileAPIRoute, url_prefix = "/mobileapi", subdomain = "www" )
    quart_app.register_blueprint( APIRobloxRoute, url_prefix = "/", subdomain = "api")
    quart_app.register_blueprint( APIssRobloxRoute, url_prefix = "/", subdomain = "apis")
    quart_app.register_blueprint( ECSV2Route, url_prefix = "/", subdomain = "ecsv2")
    quart_app.register_blueprint( AuthRoute, url_prefix = "/", subdomain = "auth")
    quart_app.register_blueprint( LocaleRoute, url_prefix = "/", subdomain = "locale")
    quart_app.register_blueprint( EconomyRoute, url_prefix = "/", subdomain = "economy")
    quart_app.register_blueprint( AvatarRoute, url_prefix = "/", subdomain = "avatar")
    quart_app.register_blueprint( InternalAPIRoute, url_prefix = "/", subdomain = "internal")
    quart_app.register_blueprint( ThumbnailRoute, url_prefix = "/", subdomain = "thumbnails")
    quart_app.register_blueprint( CatalogRoute, url_prefix = "/", subdomain = "catalog")
    quart_app.register_blueprint( UserProfileHandler, url_prefix = "/", subdomain = "www" )
    quart_app.register_blueprint( AssetGameRoute, url_prefix = "/", subdomain = "assetgame" )
    quart_app.register_blueprint( GameinstancesAPIRoute, url_prefix = "/", subdomain = "gameinstances.api" )
    quart_app.register_blueprint( TextFilterRoute, url_prefix = "/", subdomain = "textfilter" )
    quart_app.register_blueprint( GroupsRoute, url_prefix = "/", subdomain = "groups" )
    quart_app.register_blueprint( GamePersistenceRoute, url_prefix = "/", subdomain = "gamepersistence" )
    quart_app.register_blueprint( AvatarEditorPageHandler, url_prefix = "/", subdomain = "www" )
    quart_app.register_blueprint( InventoryAPIRoute, url_prefix = "/", subdomain = "inventory" )
    quart_app.register_blueprint( FriendsRoute, url_prefix = "/", subdomain = "friends" )
    quart_app.register_blueprint( PresenceAPIRoute, url_prefix = "/", subdomain = "presence" )

    return quart_app

if __name__ == "__main__":
    app = create_app()
    app.run( host = "127.0.0.1", port = 3008, debug = True )