from quart import Blueprint, render_template, abort, Response, url_for
from app.services import authentication
from app.models.user import User
from app.enums.AdminPermissions import AdminPermissions

from config import Config

web_config = Config()

AdminPageHandler = Blueprint( 'admin', __name__, url_prefix = '/', subdomain = 'simulpong' )

@AdminPageHandler.before_request
async def _before_request():
    AuthenticatedUser : User | None = await authentication.GetCurrentUser()
    if AuthenticatedUser is None:
        raise authentication.AuthenticationExceptions.UserNotAuthenticated
    if AuthenticatedUser.permissions == 0:
        raise authentication.AuthenticationExceptions.InsufficientPermissions

@AdminPageHandler.after_request
async def _after_request( response : Response ):
    AuthenticatedUser : User | None = await authentication.GetCurrentUser()
    if AuthenticatedUser is not None and AuthenticatedUser.permissions > 0:
        response.headers["Access-Control-Allow-Origin"] = f"https://simulpong.{web_config.BaseDomain}"
    return response

@AdminPageHandler.route('/main', methods=['GET'])
async def _main():
    return await render_template('admin/main.html')

from app.pages.admin.gameserver_manager.gameserver_page_handler import GameserverPageHandler
AdminPageHandler.register_blueprint(GameserverPageHandler)