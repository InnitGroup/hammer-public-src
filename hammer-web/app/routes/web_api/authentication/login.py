import logging
from datetime import timedelta, datetime
from quart import request, make_response, jsonify, session, Blueprint
from sqlalchemy import func

from app.models.user import User
from app.enums.AccountStatus import AccountStatus

from app.extensions import remote_address_limiter, db, get_remote_address
from app.services import authentication
from config import Config

web_config = Config()

LoginHandler = Blueprint('login', __name__, url_prefix='/')

@LoginHandler.route("/login", methods = [ "POST" ])
@remote_address_limiter.limit( "20/minute", deduct_when = lambda response: response.status_code != 200 )
@remote_address_limiter.limit( "2/minute", deduct_when = lambda response: response.status_code == 200 )
async def _login():
    if await authentication.GetCurrentUser() is not None:
        return await make_response( jsonify({ "status": 1, "message": "Already logged in"}) , 400 )
    
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    
    json_data = await request.json

    try:
        assert "username" in json_data, "Username is required"
        assert "password" in json_data, "Password is required"
        assert "remember_me" in json_data, "Remember me is required"
        assert isinstance( json_data["username"], str), "Username must be a string"
        assert isinstance( json_data["password"], str), "Password must be a string"
        assert isinstance( json_data["remember_me"], bool), "Remember me must be a boolean"
        assert len( json_data["username"]) > 0, "Username must not be empty"
        assert len( json_data["password"]) > 0, "Password must not be empty"
        assert len( json_data["username"]) <= 32, "Username must not be longer than 32 characters"
        assert len( json_data["password"]) <= 128, "Password must not be longer than 128 characters"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 2, "message": f"Validation failed, {str(e)}"}), 400)
    
    # TwoFactorCode = ""
    # if "two_factor_code" in json_data:
    #     try:
    #         assert isinstance( json_data["two_factor_code"], str), "Two factor code must be a string"
    #         assert len( json_data["two_factor_code"]) > 0, "Two factor code must not be empty"
    #         assert len( json_data["two_factor_code"]) == 6, "Two factor code must be 6 characters long"
    #         TwoFactorCode = json_data["two_factor_code"]
    #     except AssertionError as e:
    #         return await make_response( jsonify({ "status": 2, "message": f"Validation failed, {str(e)}"}), 400)
    
    try:
        userObj : User = await authentication.HandleUserLogin( Username = json_data["username"], Password = json_data["password"]) #, TwoFactorCode = TwoFactorCode)
    except authentication.AuthenticationExceptions.LoginsAreDisabled:
        return await make_response( jsonify({ "status": 3, "message": "Logins are disabled"}), 500)
    except authentication.AuthenticationExceptions.InvalidUsername:
        return await make_response( jsonify({ "status": 4, "message": "Invalid username or password"}), 400)
    except authentication.AuthenticationExceptions.InvalidPassword:
        return await make_response( jsonify({ "status": 4, "message": "Invalid username or password"}), 400)
    except authentication.AuthenticationExceptions.UserIsNotInActiveStatus:
        userObj : User = User.query.filter( func.lower( User.username ) == func.lower( json_data["username"] ) ).first()
        session["not-approved"] = True
        session["id"] = userObj.id

        return await make_response( jsonify({ "status": 6, "data": {
            "is_suspended": True,
            "redirect_url": "/not-approved",
            "user_id": userObj.id
        }}), 200)
    except authentication.AuthenticationExceptions.RequiresTwoFactor:
        """
            8/3/2024
            We don't return a 200 status code here because the user is not actually logged in, and it will count against their rate limit.
            - something.else
        """
        userObj : User = User.query.filter( func.lower( User.username ) == func.lower( json_data["username"] ) ).first()
        two_step_token = await authentication.create_two_step_login_token( userObj )
        return await make_response( jsonify({ "status": 5, "message": "Requires two factor authenticaiton", "next_step_token": two_step_token}), 400)
    except authentication.AuthenticationExceptions.InvalidTwoFactorCode:
        return await make_response( jsonify({ "status": 7, "message": "Invalid two factor code"}), 400)
    
    NewSessionToken : str = await authentication.create_session_token(
        UserObj = userObj,
        Requesting_Remote_Address = get_remote_address(),
        Expiration = timedelta( days = 31 ) if json_data["remember_me"] else timedelta( days = 1 ),
        Creation_Context = "WebLogin"
    )

    response = await make_response( jsonify({ "status": 1, "data": {
        "is_suspended": False,
        "redirect_url": "/home",
        "user_id": userObj.id
    }}), 200)

    response.set_cookie(
        key = ".ROBLOSECURITY",
        value = NewSessionToken,
        max_age = 60 * 60 * 24 * 30 if json_data["remember_me"] else None,
        domain = f".{web_config.BaseDomain}"
    )

    return response

@LoginHandler.route("/login/two-factor", methods = [ "POST" ])
@remote_address_limiter.limit( "20/minute", deduct_when = lambda response: response.status_code != 200 )
@remote_address_limiter.limit( "2/minute", deduct_when = lambda response: response.status_code == 200 )
async def _login_two_factor():
    if await authentication.GetCurrentUser() is not None:
        return await make_response( jsonify({ "status": 1, "message": "Already logged in"}) , 400 )
    
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    
    json_data = await request.json

    try:
        assert "next_step_token" in json_data, "Next step token is required"
        assert "two_factor_code" in json_data, "Two factor code is required"
        assert "remember_me" in json_data, "Remember me is required"
        assert isinstance( json_data["next_step_token"], str), "Next step token must be a string"
        assert isinstance( json_data["two_factor_code"], str), "Two factor code must be a string"
        assert isinstance( json_data["remember_me"], bool), "Remember me must be a boolean"
        assert len( json_data["next_step_token"]) > 0, "Next step token must not be empty"
        assert len( json_data["two_factor_code"]) > 0, "Two factor code must not be empty"
        assert len( json_data["next_step_token"]) < 256, "Next step token is too long"
        assert len( json_data["two_factor_code"]) == 6, "Two factor code must be 6 characters long"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 2, "message": f"Validation failed, {str(e)}"}), 400)
    
    next_step_token = json_data["next_step_token"]
    two_factor_code = json_data["two_factor_code"]
    remember_me = json_data["remember_me"]
    
    try:
        target_user_obj : User | None = await authentication.verify_two_step_login_token( next_step_token )
        assert target_user_obj is not None, "Invalid next step token"
        if await authentication.VerifyTwoFactorCode( target_user_obj, two_factor_code ) is False:
            raise authentication.AuthenticationExceptions.InvalidTwoFactorCode()
    except AssertionError as e:
        return await make_response( jsonify({ "status": 3, "message": str(e)}), 400)
    except authentication.AuthenticationExceptions.InvalidTwoFactorCode:
        return await make_response( jsonify({ "status": 4, "message": "Invalid two factor code"}), 400)
    
    if target_user_obj.account_status != AccountStatus.Active:
        session["not-approved"] = True
        session["id"] = target_user_obj.id

        return await make_response( jsonify({ "status": 6, "data": {
            "is_suspended": True,
            "redirect_url": "/not-approved",
            "user_id": target_user_obj.id
        }}), 200)
    
    NewSessionToken : str = await authentication.create_session_token(
        UserObj = target_user_obj,
        Requesting_Remote_Address = get_remote_address(),
        Expiration = timedelta( days = 31 ) if remember_me else timedelta( days = 1 ),
        Creation_Context = "WebLogin"
    )
    response = await make_response( jsonify({ "status": 1, "data": {
        "is_suspended": False,
        "redirect_url": "/home",
        "user_id": target_user_obj.id
    }}), 200)

    response.set_cookie(
        key = ".ROBLOSECURITY",
        value = NewSessionToken,
        max_age = 60 * 60 * 24 * 30 if json_data["remember_me"] else None,
        domain = f".{web_config.BaseDomain}"
    )

    return response
    

@LoginHandler.route("/logout", methods = [ "POST" ])
@authentication.require_authentication
async def _logout():
    sessionToken = request.cookies.get( ".ROBLOSECURITY", None )
    if sessionToken is not None:
        await authentication.invalidate_session_token( sessionToken )
    
    response = await make_response( jsonify({ "status": 1, "message": "Logged out"}), 200)
    response.set_cookie( ".ROBLOSECURITY", "", expires = 0 )
    return response