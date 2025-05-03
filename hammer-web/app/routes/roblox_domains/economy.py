"""
    economy.roblox.com
"""

from quart import Blueprint, request, make_response, jsonify, redirect
from app.services.economy import balance, purchase
from app.services import authentication
from app.models.user import User
from app.models.user_economy import UserEconomy

EconomyRoute = Blueprint('economy_roblox', __name__, url_prefix='/', subdomain='economy')

@EconomyRoute.errorhandler( authentication.AuthenticationExceptions.UserNotAuthenticated )
async def _handle_user_not_authenticated( e ):
    return await make_response( jsonify({ "errors": [
        { "code": 0, "message": "Authorization has been denied for this request." }
    ] }), 401 )

@EconomyRoute.route("/v1/user/currency", methods=["GET"])
@authentication.require_authentication
async def _get_user_currency():
    AuthenticatedUser : User = await authentication.GetCurrentUser()
    UserEconomyObj : UserEconomy = await balance.GetTargetEconomyObject( TargetObj = AuthenticatedUser )
    return await make_response( jsonify({
        "robux": UserEconomyObj.robux_bal
    }), 200 )

@EconomyRoute.route("/v1/users/<int:userid>/currency", methods=["GET"])
@authentication.require_authentication
async def _get_target_user_currency( userid : int ):
    if userid < 1:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The user is invalid." }
        ] }), 400 )
    AuthenticatedUser : User = await authentication.GetCurrentUser()
    if AuthenticatedUser.id != userid:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The user is invalid." }
        ] }), 400 )
    
    TargetUserEconomyObj : UserEconomy = await balance.GetTargetEconomyObject( TargetObj = AuthenticatedUser )
    return await make_response( jsonify({
        "robux": TargetUserEconomyObj.robux_bal
    }), 200 )