from quart import redirect, Blueprint, render_template
from app.services import authentication
from config import Config

web_config = Config()

LoginHandler = Blueprint( "LoginHandler", __name__, url_prefix = "/" )

@LoginHandler.route( "/login", methods = [ "GET" ] )
async def _login_page():
    if await authentication.GetCurrentUser() is not None:
        return redirect( "/home")
    
    return await render_template( "authentication_pages/login.html" )

@LoginHandler.route( "/register", methods = [ "GET" ] )
async def _register_page():
    if await authentication.GetCurrentUser() is not None:
        return redirect( "/home")
    
    return await render_template( "authentication_pages/register.html", monocle_site_token = web_config.SPUR_US_PUBLIC_SITE_TOKEN)