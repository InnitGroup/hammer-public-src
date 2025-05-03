from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

class PlaceServer( db.Model ):
    server_uuid = db.Column( UUID( as_uuid = True ), primary_key = True, nullable = False, unique = True )
    parent_gameserver_uuid = db.Column( UUID( as_uuid = True ), nullable = False, index = True )
    place_id = db.Column( db.BigInteger, db.ForeignKey("place.place_id"), nullable = False, index = True )
    place_asset_version = db.Column( db.BigInteger, nullable = False, default = 1 )
    
    server_ip = db.Column( db.Text, nullable = False )
    server_port = db.Column( db.Integer, nullable = False )
    
    created_at = db.Column( db.DateTime, nullable = False )
    last_heartbeat = db.Column( db.DateTime, nullable = True )
    
    player_count = db.Column( db.Integer, nullable = False, default = 0 )
    max_players = db.Column( db.Integer, nullable = False, default = 10 )
    
    reserved_server_access_code = db.Column( db.Text, nullable = True )
    
    def __init__(
        self,
        server_uuid,
        parent_gameserver_uuid,
        server_ip : str,
        server_port : int,
        place_id : int,
        place_asset_version : int = 1,
        created_at : datetime | None = None,
        last_heartbeat : datetime | None = None,
        player_count : int = 0,
        max_players : int = 10,
        reserved_server_access_code : str = None
    ):
        self.server_uuid = server_uuid
        self.parent_gameserver_uuid = parent_gameserver_uuid
        self.server_ip = server_ip
        self.server_port = server_port
        self.place_id = place_id
        self.place_asset_version = place_asset_version
        self.created_at = created_at or datetime.utcnow()
        self.last_heartbeat = last_heartbeat
        self.player_count = player_count
        self.max_players = max_players
        self.reserved_server_access_code = reserved_server_access_code
    
    def __repr__( self ):
        return f"<PlaceServer server_uuid={self.server_uuid} parent_gameserver_uuid={self.parent_gameserver_uuid} server_ip={self.server_ip} server_port={self.server_port} place_id={self.place_id} place_asset_version={self.place_asset_version} created_at={self.created_at} last_heartbeat={self.last_heartbeat} player_count={self.player_count} max_players={self.max_players} reserved_server_access_code={self.reserved_server_access_code}>"