
import logging
from quart import Blueprint, request, make_response, jsonify
from datetime import timedelta

from app.services import authentication
from app.models.user import User
from app.extensions import remote_address_limiter, get_remote_address
from app.util.validators.username import UsernameValidatorExceptions

from config import Config

web_config = Config()

RegistrationHandler = Blueprint('register', __name__, url_prefix='/')

@RegistrationHandler.route("/register", methods = [ "POST" ])
@remote_address_limiter.limit( "1/hour", deduct_when = lambda response: response.status_code == 200 )
@remote_address_limiter.limit( "30/minute", deduct_when = lambda response: response.status_code != 200 )
async def _handle_register():
    if await authentication.GetCurrentUser() is not None:
        return await make_response( jsonify({ "status": 1, "message": "Cannot register while logged in"}), 403 )
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    
    json_data = await request.json

    try:
        assert "username" in json_data, "Username is required"
        assert "password" in json_data, "Password is required"
        assert "invite_key" in json_data, "Invite key is required"
        assert "agree_to_terms" in json_data, "Agree to terms is required"
        assert "agree_meet_age_requirements" in json_data, "Agree to meet age requirements is required"
        assert isinstance( json_data["username"], str), "Username must be a string"
        assert isinstance( json_data["password"], str), "Password must be a string"
        assert isinstance( json_data["invite_key"], str), "Invite key must be a string"
        assert isinstance( json_data["agree_to_terms"], bool), "Agree to terms must be a boolean"
        assert isinstance( json_data["agree_meet_age_requirements"], bool), "Agree to meet age requirements must be a boolean"
        assert len( json_data["username"]) > 0, "Username must not be empty"
        assert len( json_data["password"]) > 0, "Password must not be empty"
        assert len( json_data["invite_key"]) > 0, "Invite key must not be empty"
        assert json_data["agree_to_terms"], "You must agree to the terms"
        assert json_data["agree_meet_age_requirements"], "You must agree to meet the age requirements"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 2, "message": f"Validation failed, {str(e)}"}), 400)
    
    try:
        NewUserObj : User = await authentication.HandleUserRegister(
            Username = json_data["username"],
            Password = json_data["password"],
            BypassFeatureLock = False
        )
    except UsernameValidatorExceptions.UsernameTooShort:
        return await make_response( jsonify({ "status": 2, "message": "Username is too short"}), 400)
    except UsernameValidatorExceptions.UsernameTooLong:
        return await make_response( jsonify({ "status": 2, "message": "Username is too long"}), 400)
    except UsernameValidatorExceptions.UsernameInvalidCharacters:
        return await make_response( jsonify({ "status": 2, "message": "Username contains invalid characters"}), 400)
    except UsernameValidatorExceptions.UsernameMustStartWithLetter:
        return await make_response( jsonify({ "status": 2, "message": "Username must start with a letter"}), 400)
    except UsernameValidatorExceptions.UsernameMustEndWithLetterOrNumber:
        return await make_response( jsonify({ "status": 2, "message": "Username must end with a letter or number"}), 400)
    except UsernameValidatorExceptions.UsernameCanOnlyContainOneUnderscore:
        return await make_response( jsonify({ "status": 2, "message": "Username can only contain one underscore"}), 400)
    except UsernameValidatorExceptions.UsernameMustContainAtLeastOneLetter:
        return await make_response( jsonify({ "status": 2, "message": "Username must contain at least one letter"}), 400)
    except UsernameValidatorExceptions.UsernameIsModerated:
        return await make_response( jsonify({ "status": 2, "message": "Username is moderated"}), 400)
    except authentication.AuthenticationExceptions.InternalServiceError:
        return await make_response( jsonify({ "status": 3, "message": "Internal service error"}), 500)
    except authentication.AuthenticationExceptions.SignupDisabled:
        return await make_response( jsonify({ "status": 4, "message": "Registrations are disabled"}), 500)
    except authentication.AuthenticationExceptions.UsernameNotAvailable:
        return await make_response( jsonify({ "status": 5, "message": "Username is not available"}), 400)
    except Exception as e:
        logging.error( f"pages.authentication_pages.auth_handler > _handle_register unhandled exception: {str(e)}")
        return await make_response( jsonify({ "status": 3, "message": "Internal service error"}), 500)
    
    register_rep = await make_response( jsonify({ "status": 1, "data": {
        "redirect_url": "/home",
        "user_id": NewUserObj.id
    }}), 200)
    register_rep.set_cookie(
        key = ".ROBLOSECURITY",
        value = await authentication.create_session_token(
            UserObj = NewUserObj,
            Requesting_Remote_Address = get_remote_address(),
            Expiration = timedelta( days = 31 ),
            Creation_Context = "WebRegister"
        ),
        max_age = timedelta( days = 31 ),
        domain = f".{web_config.BaseDomain}"
    )

    return register_rep