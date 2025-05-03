import logging
from quart import Blueprint, render_template, make_response, jsonify, request, redirect
from app.models.user import User
from app.services import authentication

HomeHandler = Blueprint( "HomeHandler", __name__, url_prefix = "/" )

@HomeHandler.route( "/home", methods = [ "GET" ] )
@authentication.require_authentication
async def _home_page():
    AuthenticatedUser : User = await authentication.GetCurrentUser()
    return await render_template( "home/home.html", userObj = AuthenticatedUser )