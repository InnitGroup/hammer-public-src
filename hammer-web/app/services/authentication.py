import random
import string
import json
import logging
import hashlib
import pyotp
import uuid
import redis_lock
import inspect
import time
import base64
import os

from argon2 import PasswordHasher
from quart import request, jsonify, g, redirect
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import func

from app.extensions import redis_controller, db, sync_redis_controller, get_remote_address
from app.models.user import User
from app.models.session_token import SessionToken
from app.models.user_two_factor import UserTwoFactorSettings
from app.models.user_economy import UserEconomy
from app.models.user_avatar import UserAvatar
from app.models.user_thumbnail import UserThumbnail
from app.models.gameserver import GameServer
from app.models.user_settings import UserSettings
from app.enums.AccountStatus import AccountStatus
from app.enums.WebsiteFeature import WebsiteFeature
from app.enums.AdminPermissions import AdminPermissions
from app.util.websiteFeatures import GetWebsiteFeature
from app.util.validators.username import ValidateUsername, UsernameValidatorExceptions, IsUsernameAvailable

from config import Config

web_config = Config()

class AuthenticationExceptions():
    class InvalidUser( Exception ):
        pass
    class InternalServiceError( Exception ):
        pass
    class InvalidSessionToken( Exception ):
        pass
    class UserNotAuthenticated( Exception ):
        pass
    class InsufficientPermissions( Exception ):
        pass

    class InvalidUsername( Exception ):
        pass
    class InvalidPassword( Exception ):
        pass
    class RequiresTwoFactor( Exception ):
        pass
    class InvalidTwoFactorCode( Exception ):
        pass
    class TwoFactorNotEnabled( Exception ):
        pass
    class UserIsNotInActiveStatus( Exception ):
        pass
    class LoginsAreDisabled( Exception ):
        pass

    class SignupDisabled( Exception ):
        pass
    class RedisLockAcquisitionFailed( Exception ):
        pass
    class UsernameNotAvailable( Exception ):
        pass
    class InviteKeyInvalid( Exception ):
        pass


def get_user_by_id( user_id : int | User, return_none_on_deleted : bool = False ) -> User | None:
    """
        Gets the user by the given id

        :param user_id: The user id or user object to get the user by
        :param return_none_on_deleted: If True, will return None if the user is deleted

        :return: The user object if it exists, otherwise None
    """

    if isinstance( user_id, int ):
        UserObj : User | None = User.query.filter_by( id = user_id ).first()
    elif isinstance( user_id, User ):
        UserObj = user_id
    else:
        raise AuthenticationExceptions.InvalidUser( "Expected User or integer" )
    
    if UserObj is None:
        return None
    if return_none_on_deleted and UserObj.account_status == AccountStatus.GDPR_Deleted:
        return None
    
    return UserObj

async def create_session_token(
    UserObj : User | int,
    Requesting_Remote_Address : str = "",
    Expiration : timedelta = timedelta( days = 31 ),
    Creation_Context : str = "Unknown"
) -> str:
    """
        Creates a session token for the user, and stores it in redis

        :param UserObj: The user object or user id to create a session token for
        :param Requesting_Remote_Address: The remote address of the user requesting the token
        :param Expiration: The expiration time of the token

        :raises AuthenticationExceptions.InvalidUser: If the user object is invalid
        :raises AuthenticationExceptions.InternalServiceError: If an internal error occurs ( This is to prevent leaking information )

        :return: The session token for the user
    """
    
    if isinstance( UserObj, int ):
        UserObj = User.query.filter_by( id = UserObj ).first()
    elif not isinstance( UserObj, User ):
        raise AuthenticationExceptions.InvalidUser( "Expected User or integer" )
    
    if UserObj is None:
        raise AuthenticationExceptions.InvalidUser( "Unknown User" )
    
    try:
        random.seed( uuid.uuid4().bytes )
        NewSessionToken : str = ''.join( random.choices( string.ascii_letters + string.digits, k = random.randint( 128, 196 ) ) )
        await redis_controller.set(
            f"session:{NewSessionToken}",
            value = json.dumps({
                "id": UserObj.id,
                "created": datetime.utcnow().isoformat(),
                "expiration": ( datetime.utcnow() + Expiration ).isoformat(),
                "context": Creation_Context,
                "adddres": Requesting_Remote_Address
            }),
            ex = Expiration
        )

        db.session.add( SessionToken(
            token = NewSessionToken,
            user_id = UserObj.id,
            expiration = datetime.utcnow() + Expiration,
            creation_context = Creation_Context
        ))
        db.session.commit()
    except Exception as e:
        logging.error( f"service.authentication > create_session_token, exception rasied: {e}" )
        raise AuthenticationExceptions.InternalServiceError( "Failed to create session token" )

    return NewSessionToken

async def fetch_session_data( session_token : str ) -> dict | None:
    """
        Fetches the session data from redis

        :param session_token: The session token to fetch the data for

        :return: The session data if it exists, otherwise None
    """

    try:
        SessionData : str = await redis_controller.get( f"session:{session_token}" )
        if SessionData is not None:
            return json.loads( SessionData )
    except Exception as e:
        logging.error( f"service.authentication > fetch_session_data, exception rasied: {e}" )
        return None

async def invalidate_session_token( session_token : str ):
    """
        Invalidates the session token

        :param session_token: The session token to invalidate

        :return: None
    """

    try:
        await redis_controller.delete( f"session:{session_token}" )
        DBSessionToken : SessionToken | None = SessionToken.query.filter_by( token = session_token ).first()
        if DBSessionToken is not None:
            db.session.delete( DBSessionToken )
            db.session.commit()
    except Exception as e:
        logging.error( f"service.authentication > invalidate_session_token, exception rasied: {e}" )
        raise AuthenticationExceptions.InternalServiceError( "Failed to invalidate session token" )

async def GetCurrentUser() -> User | None:
    """
        Gets the current user from the current flask request context

        :return: The user object if the user is logged in, otherwise None
    """

    async def _fetch_authenticated_user():
        UserSessionToken = request.cookies.get(
            key = ".ROBLOSECURITY",
            default = None,
            type = str
        )

        if UserSessionToken is None:
            return None
        
        try:
            SessionData = await fetch_session_data( UserSessionToken )
            if SessionData is not None:
                return User.query.filter_by( id = SessionData["id"] ).first()
        
        except Exception as e:
            logging.error( f"service.authentication > GetCurrentUser, exception rasied: {e}" )
            return None
        return None
        
    if "CurrentUser" not in g:
        g.CurrentUser = await _fetch_authenticated_user()

    return g.CurrentUser

async def _GetArgonSalt( UserObj : User ) -> bytes:
    return ( hashlib.sha512( (web_config.FLASK_SESSION_KEY + str(UserObj.id)).encode("utf-8") ) ).digest()
async def _GetPasswordHasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=16,
        memory_cost=2**14,
        parallelism=2,
        hash_len=32,
        salt_len=16
    )

async def GenerateTwoFactorSecret( UserTwoFactorSettingsObj : UserTwoFactorSettings ) -> str:
    """
        Generates a two factor secret for the user

        :param UserTwoFactorSettingsObj: The user two factor settings object to generate the secret for

        :return: The two factor secret
    """

    try:
        SecretBytes : bytes = UserTwoFactorSettingsObj.two_factor_secret_seed.encode( "utf-8" )
        random.seed( SecretBytes )

        return "".join( random.choices( "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", k = 32 ) )
    except Exception as e:
        logging.error( f"service.authentication > GenerateTwoFactorSecret, exception rasied: {e}" )
        raise AuthenticationExceptions.InternalServiceError( "Failed to generate two factor secret" )

async def VerifyPassword( UserObj : User, Password : str ) -> bool:
    """
        Verifies the password for the user

        :param UserObj: The user object to verify the password for
        :param Password: The password to verify

        :return: True if the password is correct, otherwise False
    """
    try:
        PasswordHasherObj = await _GetPasswordHasher()
        return PasswordHasherObj.verify(
            hash = UserObj.password,
            password = Password
        )
    except Exception as e:
        logging.error( f"service.authentication > VerifyPassword, exception rasied: {e}" )
        return False
    
async def VerifyTwoFactorCode( UserObj : User, TwoFactorCode : str = "" ) -> bool:
    """
        Verifies the two factor code for the given user

        :param UserObj: The user object to verify the two factor code for
        :param TwoFactorCode: The two factor code to verify

        :return: True if the two factor code is correct, otherwise False
    """

    if not UserObj.two_factor_enabled:
        raise AuthenticationExceptions.TwoFactorNotEnabled( "Two factor authentication is not enabled for this user" )
    UserTwoFactorSettingsObj : UserTwoFactorSettings | None = UserTwoFactorSettings.query.filter_by( user_id = UserObj.id ).first()
    if UserTwoFactorSettingsObj is None:
        UserObj.two_factor_enabled = False
        db.session.commit()

        raise AuthenticationExceptions.InternalServiceError( "User does not have two factor settings, enabled" )
    
    try:
        TOTPObj = pyotp.TOTP( await GenerateTwoFactorSecret( UserTwoFactorSettingsObj = UserTwoFactorSettingsObj ) )
        logging.info(f"debug code: {TOTPObj.now()}")
        return TOTPObj.verify( otp = TwoFactorCode )
    except Exception as e:
        logging.error( f"service.authentication > VerifyTwoFactorCode, exception rasied: {e}" )
        return False

async def SetUserPasword( UserObj : User, NewPassword : str ):
    """
        Sets the password for the user

        :param UserObj: The user object to set the password for
        :param NewPassword: The new password for the user

        :return: None
    """

    try:
        PasswordHasherObj = await _GetPasswordHasher()
        UserObj.password = PasswordHasherObj.hash(
            password = NewPassword,
            salt = await _GetArgonSalt( UserObj )
        )

        db.session.commit()
        return
    except Exception as e:
        logging.error( f"service.authentication > SetUserPasword, exception rasied: {e}" )
        raise AuthenticationExceptions.InternalServiceError( "Failed to set user password" )

async def DoesUserHavePermission( UserObj : User, Permission : AdminPermissions ) -> bool:
    """
        Checks if the user has the given permission

        :param UserObj: The user object to check the permission for
        :param Permission: The permission to check for

        :return: True if the user has the permission, otherwise False
    """
    return ( UserObj.permissions >> Permission.value ) & 1 == 1

async def SetUserPermission( UserObj : User, Permission : AdminPermissions, Value : bool ):
    """
        Sets the permission for the user

        :param UserObj: The user object to set the permission for
        :param Permission: The permission to set
        :param Value: The value to set the permission to

        :return: None
    """
    if Value:
        UserObj.permissions = ( UserObj.permissions | ( 1 << Permission.value ) )
    else:
        UserObj.permissions = ( UserObj.permissions & ~( 1 << Permission.value ) )

    db.session.commit()
    return

def require_authentication( func ):
    """
        A decorator to require authentication for a route
        Will raise AuthenticationExceptions.UserNotAuthenticated if the user is not authenticated, this will usually be handled
        by the errorhandler in __init__, but can be overwritten in a blueprint if needed for custom error handling

        :param func: The function to decorate

        :return: The decorated function
    """

    @wraps( func )
    async def decorated_function( *args, **kwargs ):
        if await GetCurrentUser() is None:
            raise AuthenticationExceptions.UserNotAuthenticated( "User is not authenticated" )
        return await func( *args, **kwargs ) if inspect.iscoroutinefunction( func ) else func( *args, **kwargs )
    
    return decorated_function

def require_admin_permission( permissions_required : list[AdminPermissions] = [] ):
    """
        A decorator to require admin permissions for a route

        :param permissions_required: The permissions required to access the route, can be left empty to require any admin permission
        
        :raises AuthenticationExceptions.InsufficientPermissions: If the user does not have the required permissions
        :raises AuthenticationExceptions.UserNotAuthenticated: If the user is not authenticated
    """
    def decorated_function(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            AuthenticatedUser : User = await GetCurrentUser()
            if AuthenticatedUser is None:
                raise AuthenticationExceptions.UserNotAuthenticated( "User is not authenticated" )
            if AuthenticatedUser.permissions == 0:
                raise AuthenticationExceptions.InsufficientPermissions( "User does not have any permissions" )
            if len(permissions_required) > 0:
                for permission in permissions_required:
                    if not await DoesUserHavePermission( AuthenticatedUser, permission ):
                        raise AuthenticationExceptions.InsufficientPermissions( "User does not have the required permissions" )
            
            return await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorated_function

async def GetCurrentGameServer(
    verify_access_key : bool = True
) -> GameServer | None:
    """
        Gets the current game server from the current flask request context

        :return: The game server object if the request is authenticated from a gameserver, otherwise None
    """
    
    async def _fetch_authenticated_gameserver():
        RequestUserAgent = request.user_agent.string
        if "Roblox" not in RequestUserAgent and "HAMMER" not in RequestUserAgent:
            return None
        if verify_access_key:
            RequestAccessKey : str = request.headers.get( key = "AccessKey", default = None, type = str )
            requesting_game_server : GameServer | None = GameServer.query.filter_by(
                arbiter_access_key = RequestAccessKey,
                arbiter_ip = get_remote_address()
            ).first()
        else:
            requesting_game_server : GameServer | None = GameServer.query.filter_by(
                arbiter_ip = get_remote_address()
            ).first()

        if requesting_game_server is None:
            return None
        return requesting_game_server
    
    if "CurrentGameServer" not in g:
        g.CurrentGameServer = await _fetch_authenticated_gameserver()

    return g.CurrentGameServer

async def HandleUserLogin( Username : str, Password : str, TwoFactorCode : str = "", BypassFeatureLock : bool = False ) -> User:
    """
        Handles the user login process

        :param Username: The username of the user to login
        :param Password: The password of the user to login
        :param TwoFactorCode: The two factor code if required, will raise AuthenticationExceptions.RequiresTwoFactor if required

        :return: The user object if the login is successful
    """

    if not BypassFeatureLock:
        isLoginEnabled = await GetWebsiteFeature( WebsiteFeature.IsLoginEnabled )
        if not isLoginEnabled:
            raise AuthenticationExceptions.LoginsAreDisabled( "Logins are disabled" )

    UserObj : User | None = User.query.filter( func.lower( User.username ) == func.lower( Username ) ).first()
    if UserObj is None:
        raise AuthenticationExceptions.InvalidUsername( "Invalid Username" )
    if UserObj.account_status == AccountStatus.GDPR_Deleted:
        raise AuthenticationExceptions.InvalidUsername( "Invalid Username" )
    
    if not await VerifyPassword( UserObj, Password ):
        raise AuthenticationExceptions.InvalidPassword( "Invalid Password" )
    
    if UserObj.two_factor_enabled:
        if TwoFactorCode == "":
            raise AuthenticationExceptions.RequiresTwoFactor( "Two factor code is required" )
        if not await VerifyTwoFactorCode( UserObj, TwoFactorCode ):
            raise AuthenticationExceptions.InvalidTwoFactorCode( "Invalid two factor code" )

    if UserObj.account_status != AccountStatus.Active:
        raise AuthenticationExceptions.UserIsNotInActiveStatus( "User is not in active status" )
    
    return UserObj

async def HandleUserRegister( Username : str, Password : str, InviteKey : str | None, BypassFeatureLock : bool = False ) -> User:
    """
        Handles the user registration process

        :param Username: The username of the user to register
        :param Password: The password of the user to register

        :return: The user object if the registration is successful
    """

    if not BypassFeatureLock:
        isRegistrationEnabled = await GetWebsiteFeature( WebsiteFeature.IsRegistrationEnabled )
        if not isRegistrationEnabled:
            raise AuthenticationExceptions.SignupDisabled( "Signup is disabled" )
    
    if InviteKey is not None and not InviteKey.startswith("hammer-"):
        raise AuthenticationExceptions.InviteKeyInvalid( "Invalid invite key" )
    
    await ValidateUsername( Username )

    try:
        from app.services import invite_keys
        with redis_lock.Lock( redis_client = sync_redis_controller, name = "web_signup", expire = 30, auto_renewal = True, strict = False ):
            if not await IsUsernameAvailable( Username ):
                raise AuthenticationExceptions.UsernameNotAvailable( "Username is not available" )
            if not await invite_keys.is_invite_key_valid( InviteKey ):
                raise AuthenticationExceptions.InviteKeyInvalid( "Invalid invite key" )
            UserObj = User(
                username = Username
            )
            db.session.add( UserObj )
            db.session.commit()
            await invite_keys.redeem_invite_key( InviteKey, UserObj )
        
        await SetUserPasword( UserObj = UserObj, NewPassword = Password )
        UserEconomyObj = UserEconomy(
            user_id = UserObj.id
        )
        db.session.add( UserEconomyObj )
        UserAvatarObj = UserAvatar(
            user_id = UserObj.id
        )
        db.session.add( UserAvatarObj )
        UserThumbnailObj = UserThumbnail(
            user_id = UserObj.id
        )
        db.session.add( UserThumbnailObj )
        UserSettingsObj = UserSettings(
            user_id = UserObj.id
        )
        db.session.add( UserSettingsObj )

        db.session.commit()
    except AssertionError as e:
        raise AuthenticationExceptions.RedisLockAcquisitionFailed( "Failed to acquire redis lock" )
    except AuthenticationExceptions.UsernameNotAvailable as e:
        raise e
    except Exception as e:
        logging.error( f"service.authentication > HandleUserRegister, exception rasied: {e}" )
        raise AuthenticationExceptions.InternalServiceError( "Failed to register user" )
    
    return UserObj

def build_arbiter_registration_key( ) -> str:
    """
        Generates a registration key for automated registration of gameservers
        using the internal installation script. Only lasts for 3 hours.
    """
    creation_time = int( time.time() )
    key_hash = hashlib.sha256( f"{creation_time}:{web_config.FLASK_SESSION_KEY}".encode("utf-8") )
    key_bytes = creation_time.to_bytes( 5, byteorder = "big" ) + key_hash.digest()
    return base64.b64encode( key_bytes ).decode().replace( "+", "-" ).replace( "/", "_" )

def verify_arbiter_registration_key( registration_key : str ) -> bool:
    decoded_key = base64.b64decode( registration_key.replace( "-", "+" ).replace( "_", "/" ) )
    if len( decoded_key ) != 37:
        return False
    creation_time = int.from_bytes( decoded_key[0:5], byteorder = "big" )
    if creation_time < int( time.time() ) - 60 * 60 * 3:
        return False
    if creation_time > int( time.time() ):
        return False
    key_hash = hashlib.sha256( f"{creation_time}:{web_config.FLASK_SESSION_KEY}".encode("utf-8") )
    if key_hash.digest() != decoded_key[5:]:
        return False
    return True

async def create_two_step_login_token( user_obj : User, expiry_seconds : int = 180 ) -> str:
    """
        Creates a two step login token for the user to use while logging in with Two step verification
        
        :param UserObj: The user object to create the token for
        :param expiry_seconds: The amount of seconds the token should be valid for
        
        :return: The two step login token
    """
    
    # 1735660800 is 2025-01-01 00:00:00 in unix time, should be future proof for the next 136 years
    creation_time = (int( time.time() ) - 1735660800).to_bytes( 4, byteorder = "big" )
    expiry_time = (expiry_seconds).to_bytes( 2, byteorder = "big" )
    user_hashed_password_hash = hashlib.sha256( user_obj.password.encode("utf-8") ).digest()
    random_bytes = os.urandom( 16 )
    
    token_bytes = creation_time + expiry_time + user_hashed_password_hash + random_bytes + user_obj.id.to_bytes( 8, byteorder = "big" )
    token_signature = hashlib.md5( token_bytes + web_config.FLASK_SESSION_KEY.encode("utf-8") ).digest()
    
    # token_signature ( 16 bytes ) + token_bytes ( 62 bytes )
    token = base64.b64encode( token_signature + token_bytes ).decode().replace( "+", "-" ).replace( "/", "_" )
    return token

async def verify_two_step_login_token( token : str ) -> User | None:
    """
        Verifies the two step login token
        
        :param token: The token to verify
        
        :return: The user object if the token is valid, otherwise None
    """
    
    try:
        token_bytes = base64.b64decode( token.replace( "-", "+" ).replace( "_", "/" ) )
        token_signature = token_bytes[0:16]
        token_bytes = token_bytes[16:]
        
        if token_signature != hashlib.md5( token_bytes + web_config.FLASK_SESSION_KEY.encode("utf-8") ).digest():
            return None
        
        creation_time = int.from_bytes( token_bytes[0:4], byteorder = "big" ) + 1735660800
        expiry_time = int.from_bytes( token_bytes[4:6], byteorder = "big" )
        if creation_time > int( time.time() ) or creation_time + expiry_time < int( time.time() ):
            return None
        
        target_user_id = int.from_bytes( token_bytes[-8:], byteorder = "big" )
        user_obj = User.query.filter_by( id = target_user_id ).first()
        if user_obj is None:
            return None

        user_hashed_password_hash = hashlib.sha256( user_obj.password.encode("utf-8") ).digest()
        if user_hashed_password_hash != token_bytes[6:38]:
            return None
        
        if await redis_controller.exists( f"two_step_login_token:{token}" ):
            return None
        
        return user_obj
    except Exception as e:
        logging.error( f"service.authentication > verify_two_step_login_token, exception rasied: {e}" )
        return None
    
async def set_two_step_login_token_used( token : str ):
    """
        Sets the two step login token as used
        
        :param token: The token to set as used
    """
    
    await redis_controller.set( f"two_step_login_token:{token}", value = "1", ex = 600 )