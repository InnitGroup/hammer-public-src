from datetime import datetime
from app.models.asset import Asset
from app.models.user import User
from app.enums.CreatorType import CreatorType

def build_datetime_obj( datetime_obj : datetime ) -> str:
    """
        Takes a datetime object and returns a string representation of the object
        in the Roblox format like "2020-11-24T10:47:17.69Z"
    """
    
    return datetime_obj.strftime( "%Y-%m-%dT%H:%M:%S.%fZ" )

async def build_creator_obj( creator_id : int, creator_type : CreatorType = CreatorType.User ) -> dict:
    if creator_type == CreatorType.User:
        creator_obj : User | None = User.query.filter_by( id = creator_id ).first()
        if creator_obj is None:
            return {
                "id": 0,
                "type": "User",
                "name": "Unknown User",
                "hasVerifiedBadge": False
            }
        return {
            "id": creator_obj.id,
            "type": "User",
            "name": creator_obj.username,
            "hasVerifiedBadge": creator_obj.permissions > 0
        }
    else:
        raise NotImplementedError( "Creator type not implemented" )