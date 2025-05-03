from datetime import datetime, timedelta

from app.enums.UserPresence import UserPresence
from app.models.user import User
from app.models.placeserver_player import PlaceServerPlayer
from app.models.placeserver import PlaceServer
from app.models.universe import Universe
from app.models.place import Place

def get_user_by_id( user_id : User | int ) -> User | None:
    if isinstance( user_id, User ):
        return user_id
    return User.query.filter_by( id = user_id ).first()

class UserGameLocation():
    place_server : PlaceServer = None
    universe : Universe = None
    place : Place = None
    place_server_player : PlaceServerPlayer = None
    
    def __init__( self, place_server : PlaceServer = None, universe : Universe = None, place : Place = None, place_server_player : PlaceServerPlayer = None ):
        self.place_server = place_server
        self.universe = universe
        self.place = place
        self.place_server_player = place_server_player

async def get_user_presence( target_user : User | int ) -> UserPresence:
    target_user = get_user_by_id( target_user )
    if target_user is None:
        return UserPresence.Offline
    if PlaceServerPlayer.query.filter_by( user_id = target_user.id ).count() > 0:
        return UserPresence.InGame
    if target_user.lastonline_at > datetime.utcnow() - timedelta( minutes = 1 ):
        return UserPresence.Website
    return UserPresence.Offline

async def get_user_game_location( target_user : User | int ) -> UserGameLocation | None:
    target_user = get_user_by_id( target_user )
    if target_user is None:
        return None
    place_server_player : PlaceServerPlayer | None = PlaceServerPlayer.query.filter_by( user_id = target_user.id ).first()
    if place_server_player is None:
        return None
    place_server : PlaceServer | None = PlaceServer.query.filter_by( server_uuid = place_server_player.parent_placeserver_uuid ).first()
    if place_server is None:
        return None
    place_obj : Place | None = Place.query.filter_by( place_id = place_server.place_id ).first()
    if place_obj is None:
        return None
    universe_obj : Universe | None = Universe.query.filter_by( id = place_obj.parent_universe_id ).first()
    if universe_obj is None:
        return None
    
    return UserGameLocation(
        place_server = place_server,
        universe = universe_obj,
        place = place_obj,
        place_server_player = place_server_player
    )