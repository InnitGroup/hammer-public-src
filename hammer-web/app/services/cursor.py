import base64
import hashlib
import time
from enum import Enum
from config import Config

web_config = Config()

class InvalidCursorException(Exception):
    pass

class CursorPagingDirection(Enum):
    Forward = 1
    Backward = 2
    
class SortOrder(Enum):
    Ascending = 0
    Descending = 1

seperator_bytes = b"\x0F\xF0"
class CursorBase():
    """
        The cursor discriminator is intended to make sure a cursor can only be
        parsed for the request it was intended to.
        
        The discriminator should contain unique information about the request
        that is also common across all pages for the paged item.
    
        If paging through a users badges a valid discriminator would be the user id (e.g. "48103520")
            The user id will be the same across all pages of the users badges, but the cursor
            verification will fail if the same cursor is attempted to be used for another user.
        
        - Second example -
        If paging through a users assets by asset type a valid discriminator 
        could be a comination of both the asset type and user id (e.g. "Hat_48103520")
            The user id and asset type will be the same across all pages of the users hat inventory
            but would fail verification if the same cursor was then used on the same users models.
    """
    discriminator : str = None
    
    """
        The number of items to be requested.
    """
    count : int = 10
    
    """
        Unix timestamp of when the cursor was created.
    """
    created_at : int = int(time.time())
    
    def __init__( self, discriminator : str, count : int, created_at : int = None ):
        self.discriminator = discriminator
        self.count = count
        self.cursor_type = self.__class__.__name__
        self.created_at = int(time.time()) if created_at is None else created_at
    
    def format_to_bytes( self ) -> bytes:
        formatted_bytes = b"\x01" + self.discriminator.encode() + self.count.to_bytes(2, 'little') + self.created_at.to_bytes(5, 'little')
        return formatted_bytes

class ExclusiveStartKeyCursor( CursorBase ):
    """
        The exclusive start key value.
    """
    key : int = None
    sort_order : SortOrder = SortOrder.Ascending
    paging_direction : CursorPagingDirection = CursorPagingDirection.Forward
    
    def __init__( self, discriminator : str, key : str, count : int, sort_order : SortOrder = SortOrder.Ascending, paging_direction : CursorPagingDirection = CursorPagingDirection.Forward, created_at : int = None ):
        super().__init__( discriminator, count, created_at )
        self.key = key
        self.sort_order = sort_order
        self.paging_direction = paging_direction
        self.cursor_type = self.__class__.__name__
        
    def format_to_bytes( self ) -> bytes:
        formatted_bytes = b"\x02" + self.discriminator.encode() + self.count.to_bytes(2, 'little') + self.key.to_bytes(2, 'little') + self.sort_order.value.to_bytes(1, 'little') + self.paging_direction.value.to_bytes(1, 'little') + self.created_at.to_bytes(5, 'little')
        return formatted_bytes

def parse_base_cursor( cursor_string : bytes ) -> CursorBase:
    cursor_discriminator_length = len( cursor_string ) - 7
    if cursor_discriminator_length < 1:
        raise InvalidCursorException("Invalid cursor, discriminator length too short")
    cursor_discriminator = cursor_string[1:cursor_discriminator_length].decode()
    cursor_count = int.from_bytes( cursor_string[cursor_discriminator_length:cursor_discriminator_length+2], 'little' )
    cursor_created_at = int.from_bytes( cursor_string[cursor_discriminator_length+2:cursor_discriminator_length+7], 'little' )
    return CursorBase( cursor_discriminator, cursor_count, cursor_created_at )

def parse_exclusive_start_key_cursor( cursor_string : bytes ) -> ExclusiveStartKeyCursor:
    cursor_discriminator_length = len( cursor_string ) - 11
    if cursor_discriminator_length < 1:
        raise InvalidCursorException("Invalid cursor, discriminator length too short")
    cursor_discriminator = cursor_string[1:cursor_discriminator_length].decode()
    cursor_count = int.from_bytes( cursor_string[cursor_discriminator_length:cursor_discriminator_length+2], 'little' )
    cursor_key = int.from_bytes( cursor_string[cursor_discriminator_length+2:cursor_discriminator_length+4], 'little' )
    cursor_sort_order = SortOrder( int.from_bytes( cursor_string[cursor_discriminator_length+4:cursor_discriminator_length+5], 'little' ) )
    cursor_paging_direction = CursorPagingDirection( int.from_bytes( cursor_string[cursor_discriminator_length+5:cursor_discriminator_length+6], 'little' ) )
    cursor_created_at = int.from_bytes( cursor_string[cursor_discriminator_length+6:cursor_discriminator_length+11], 'little' )
    return ExclusiveStartKeyCursor( cursor_discriminator, cursor_key, cursor_count, cursor_sort_order, cursor_paging_direction, cursor_created_at )

def handle_cursor( cursor_bytes : bytes ) -> CursorBase | ExclusiveStartKeyCursor:
    if cursor_bytes[0] == 1:
        return parse_base_cursor( cursor_bytes )
    elif cursor_bytes[0] == 2:
        return parse_exclusive_start_key_cursor( cursor_bytes )
    else:
        raise InvalidCursorException("Invalid cursor, unknown cursor type")

def fork_cursor( original_information : ExclusiveStartKeyCursor, new_key : int | None, new_paging_direction : CursorPagingDirection | None ) -> str:
    original_information.key = new_key if new_key is not None else original_information.key
    original_information.paging_direction = new_paging_direction if new_paging_direction is not None else original_information.paging_direction
    original_information.created_at = int(time.time())
    return create_cursor( original_information )

def create_cursor( cursor_information : CursorBase | ExclusiveStartKeyCursor ) -> str:
    serialized_cursor = cursor_information.format_to_bytes()
    cursor_hash : bytes = hashlib.sha1( serialized_cursor + (f"_{web_config.CURSOR_SALT}".encode()) ).digest()
    encoded_signed_cursor = base64.b64encode(
        serialized_cursor + cursor_hash + len(serialized_cursor).to_bytes(2, 'little')
    ).decode()
    encoded_signed_cursor = encoded_signed_cursor.replace("+", "-").replace("/", "_")
    return encoded_signed_cursor

def parse_cursor( cursor_string : str, discriminator : str = "" ) -> CursorBase | ExclusiveStartKeyCursor:
    try:
        cursor_string = cursor_string.replace("-", "+").replace("_", "/")
        decoded_cursor = base64.b64decode(cursor_string)
        if decoded_cursor[0] not in [ 1, 2 ]:
            raise InvalidCursorException("Invalid cursor, unknown cursor type")
        encoded_data_length = int.from_bytes( decoded_cursor[-2:], 'little' )
        serialized_cursor = decoded_cursor[0:encoded_data_length]
        cursor_hash = decoded_cursor[encoded_data_length:-2]
        
        if cursor_hash != hashlib.sha1( serialized_cursor + (f"_{web_config.CURSOR_SALT}".encode()) ).digest():
            raise InvalidCursorException("Invalid cursor, hash mismatch")
        cursor_obj = handle_cursor( serialized_cursor )
    except InvalidCursorException as e:
        raise e
    except Exception as e:
        raise InvalidCursorException("Invalid cursor")
    
    if cursor_obj.discriminator != discriminator:
        raise InvalidCursorException("Invalid cursor, discriminator mismatch")
    if cursor_obj.created_at < int(time.time()) - 60 * 60 * 24:
        raise InvalidCursorException("Cursor expired, cursor is older than 24 hours")
    return cursor_obj

def is_cursor_valid( cursor_string : str, discriminator : str = "" ) -> bool:
    try:
        parse_cursor( cursor_string, discriminator )
        return True
    except:
        return False