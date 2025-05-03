"""
    auth.roblox.com
"""
import random
import string
from datetime import timedelta
from sqlalchemy import func

from quart import Blueprint, request, make_response, jsonify, abort
from app.services import authentication
from app.extensions import csrf_protect, remote_address_limiter, redis_controller, get_remote_address
from app.util import websiteFeatures

from app.models.user import User
from app.enums.WebsiteFeature import WebsiteFeature

from config import Config

web_config = Config()

AuthRoute = Blueprint('auth_roblox', __name__, url_prefix='/', subdomain='auth')

@AuthRoute.errorhandler(429)
async def _rate_limit_handler(e):
    return await make_response(
        jsonify({ "errors": [
            { "code": 7, "message": "Too many attempts. Please wait a bit."}
        ] }),
        429
    )
@AuthRoute.errorhandler( 503 )
async def _service_unavailable_handler(e):
    return await make_response(
        jsonify({ "errors": [
            { "code": 11, "message": "Service unavailable. Please try again later."}
        ] }),
        503
    )

@AuthRoute.route("/Login/Negotiate.ashx", methods=["POST", "GET"], subdomain = "www")
@csrf_protect.exempt
@remote_address_limiter.limit( "40/minute", deduct_when = lambda response: response.status_code != 200 )
@remote_address_limiter.limit( "10/minute", deduct_when = lambda response: response.status_code == 200 )
async def _authenticate_via_ticket():
    authentication_ticket : str | None = request.args.get( "suggest", type = str, default = None )
    if authentication_ticket is None:
        return "Invalid request", 400
    requesting_address : str = get_remote_address()
    ticket_lookup_result = await redis_controller.get( f"auth_ticket:{authentication_ticket}:{requesting_address}" )
    if ticket_lookup_result is None:
        return "Invalid request", 400
    user_id : int = int( ticket_lookup_result )
    await redis_controller.delete( f"auth_ticket:{authentication_ticket}:{requesting_address}" )
    user_obj : User | None = User.query.filter_by( id = user_id ).first()
    if user_obj is None:
        return "Invalid request", 400
    authenticated_response = await make_response("\{\}", 200)
    authenticated_response.set_cookie(
        key = ".ROBLOSECURITY",
        value = await authentication.create_session_token(
            UserObj = user_obj,
            Requesting_Remote_Address = requesting_address,
            Expiration = timedelta( days = 1 ),
            Creation_Context = "NegotiateLogin"
        ),
        domain = f".{web_config.BaseDomain}",
        max_age = 60 * 60 * 24 * 1
    )
    return authenticated_response

@AuthRoute.route("/v2/login", methods=["POST"])
@remote_address_limiter.limit( "20/minute", deduct_when = lambda response: response.status_code != 200 )
@remote_address_limiter.limit( "2/minute", deduct_when = lambda response: response.status_code == 200 )
async def _auth_login():
    if await websiteFeatures.GetWebsiteFeature( WebsiteFeature.IsLoginEnabled ) is False:
        return abort( 503 )
    
    if await authentication.GetCurrentUser() is not None:
        return await make_response( jsonify({ "errors": [
            { "code": 12, "message": "Existing login session found. Please log out first."}
        ] }), 403 )

    if not request.is_json:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": "An unexpected error occurred."}
        ] }), 400)
    
    json_data = await request.json
    try:
        assert "username" in json_data or "cvalue" in json_data, "Username is required"
        assert "password" in json_data, "Password is required"
        if "username" in json_data:
            assert isinstance( json_data["username"], str), "Username must be a string"
            assert len( json_data["username"]) > 0, "Username must not be empty"
            assert len( json_data["username"]) <= 32, "Username must not be longer than 32 characters"
        if "cvalue" in json_data:
            assert isinstance( json_data["cvalue"], str), "Cvalue must be a string"
            assert len( json_data["cvalue"]) > 0, "Cvalue must not be empty"
            assert len( json_data["cvalue"]) <= 32, "Cvalue must not be longer than 32 characters"
        assert isinstance( json_data["password"], str), "Password must be a string"
        assert len( json_data["password"]) > 0, "Password must not be empty"
        assert len( json_data["password"]) <= 128, "Password must not be longer than 128 characters"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": f"Data validation failed: { str(e) }"}
        ] }), 400)
    
    UsernameInput : str = json_data["username"] if "username" in json_data else json_data["cvalue"]
    PasswordInput : str = json_data["password"]

    try:
        userObj : User = await authentication.HandleUserLogin(
            Username = UsernameInput,
            Password = PasswordInput
        )
    except authentication.AuthenticationExceptions.LoginsAreDisabled:
        return abort( 503 )
    except authentication.AuthenticationExceptions.InvalidUsername:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "Incorrect username or password. Please try again."}
        ]}), 403 )
    except authentication.AuthenticationExceptions.InvalidPassword:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "Incorrect username or password. Please try again."}
        ]}), 403 )
    except authentication.AuthenticationExceptions.UserIsNotInActiveStatus:
        return await make_response( jsonify({ "errors": [
            { "code": 4, "message": "Account issue. Please contact Support."}
        ]}), 403 )
    except authentication.AuthenticationExceptions.RequiresTwoFactor:
        UserObj : User = User.query.filter( func.lower( User.username ) == func.lower( UsernameInput ) ).first()

        TwoFactorSessionTicket : str = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
        await redis_controller.set( f"two_factor_session_{TwoFactorSessionTicket}", UserObj.id, ex = 60 * 5 )

        return await make_response( jsonify({
            "username": UserObj.username,
            "isUnder13": False,
            "userId": UserObj.id,
            "countryCode": "US",
            "membershipType": 4,
            "displayName": UserObj.username,

            "user" : {
                "id": UserObj.id,
                "username": UserObj.username,
                "displayName": UserObj.username
            },
            "twoStepVerificationData": {
                "mediaType": "email",
                "ticket": TwoFactorSessionTicket
            },
            "identityVerificationLoginTicket": TwoFactorSessionTicket
        }), 200)
    
    NewSessionToken : str = await authentication.create_session_token(
        UserObj = userObj,
        Requesting_Remote_Address = get_remote_address(),
        Expiration = timedelta( days = 31 ),
        Creation_Context = "AuthV2Login"
    )
    authenticated_response = await make_response( jsonify({
        "username": userObj.username,
        "isUnder13": False,
        "userId": userObj.id,
        "countryCode": "US",
        "membershipType": 4,
        "displayName": userObj.username,

        "user": {
            "id": userObj.id,
            "name": userObj.username,
            "displayName": userObj.username
        },
        "isBanned": False,
        "accountBlob": ""
    }), 200 )
    authenticated_response.set_cookie(
        key = ".ROBLOSECURITY",
        value = NewSessionToken,
        domain = f".{web_config.BaseDomain}",
        max_age = 60 * 60 * 24 * 31
    )
    return authenticated_response