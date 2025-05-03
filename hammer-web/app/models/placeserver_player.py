from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
class PlaceServerPlayer( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), primary_key = True, nullable = False, unique = True )
    parent_placeserver_uuid = db.Column( UUID( as_uuid=True ), nullable = False, index = True )
    joined_at = db.Column( db.DateTime, nullable = False, index = True )
    last_heartbeat = db.Column( db.DateTime, nullable = False, index = True )
    
    def __init__(
        self,
        user_id : int,
        parent_placeserver_uuid : UUID,
        joined_at : datetime | None = None,
        last_heartbeat : datetime | None = None
    ):
        self.user_id = user_id
        self.parent_placeserver_uuid = parent_placeserver_uuid
        self.joined_at = joined_at or datetime.utcnow()
        self.last_heartbeat = last_heartbeat or datetime.utcnow()
    
    def __repr__( self ):
        return f"<PlaceServerPlayer user_id={self.user_id} parent_placeserver_uuid={self.parent_placeserver_uuid} joined_at={self.joined_at} last_heartbeat={self.last_heartbeat}>"