import string

from app.services import text_moderation
from app.models.user import User
from sqlalchemy import func

class UsernameValidatorExceptions( ):
    class UsernameTooShort( Exception ):
        pass
    class UsernameTooLong( Exception ):
        pass
    class UsernameInvalidCharacters( Exception ):
        pass
    class UsernameMustStartWithLetter( Exception ):
        pass
    class UsernameMustEndWithLetterOrNumber( Exception ):
        pass
    class UsernameCanOnlyContainOneUnderscore( Exception ):
        pass
    class UsernameMustContainAtLeastOneLetter( Exception ):
        pass
    class UsernameIsModerated( Exception ):
        pass

async def ValidateUsername( input_username : str ) -> bool:
    if len( input_username ) < 3:
        raise UsernameValidatorExceptions.UsernameTooShort( "Username is too short" )
    if len( input_username ) > 20:
        raise UsernameValidatorExceptions.UsernameTooLong( "Username is too long" )
    if not all( char in string.ascii_letters + string.digits + "_" for char in input_username ):
        raise UsernameValidatorExceptions.UsernameInvalidCharacters( "Username contains invalid characters" )
    if not input_username[0].isalpha():
        raise UsernameValidatorExceptions.UsernameMustStartWithLetter( "Username must start with a letter" )
    if not input_username[-1].isalnum():
        raise UsernameValidatorExceptions.UsernameMustEndWithLetterOrNumber( "Username must end with a letter or number" )
    if input_username.count( "_" ) > 1:
        raise UsernameValidatorExceptions.UsernameCanOnlyContainOneUnderscore( "Username can only contain one underscore" )
    if not any( char.isalpha() for char in input_username ):
        raise UsernameValidatorExceptions.UsernameMustContainAtLeastOneLetter( "Username must contain at least one letter" )
    try:
        text_moderation.filter_text( input_username, raise_exception = True )
    except text_moderation.TextNotAllowed:
        raise UsernameValidatorExceptions.UsernameIsModerated( "Username is moderated" )
    
    return True

async def IsUsernameAvailable( input_username : str ) -> bool:
    return User.query.filter( func.lower( User.username ) == input_username.lower() ).count() == 0