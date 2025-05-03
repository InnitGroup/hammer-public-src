from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid


class GameServer( db.Model ):
    id = db.Column( UUID( as_uuid = True ), primary_key = True, nullable = False, unique = True )
    name = db.Column( db.String( 100 ), nullable = False, default = "Unnamed Game Server")

    arbiter_ip = db.Column( db.String( 100 ), nullable = False )
    arbiter_port = db.Column( db.Integer, nullable = False )
    arbiter_access_key = db.Column( db.Text, nullable = False )

    last_heartbeat = db.Column( db.DateTime, nullable = False )
    response_time = db.Column( db.Float, nullable = False, default = 0 )
    memory_usage = db.Column( db.Float, nullable = False, default = 0 ) # MegaBytes
    memory_size = db.Column( db.Float, nullable = False, default = 0 ) # MegaBytes
    processor_usage = db.Column( db.Float, nullable = False, default = 0 ) # Percentage
    processor_cores = db.Column( db.Integer, nullable = False, default = 0 )
    thumbnail_queue_size = db.Column( db.Integer, nullable = False, default = 0 )

    is_thumbnail_renderer = db.Column( db.Boolean, nullable = False, default = False )
    is_game_hoster = db.Column( db.Boolean, nullable = False, default = False )
    is_asset_validator = db.Column( db.Boolean, nullable = False, default = False )

    def __init__(
        self,
        id : UUID | None = None,
        name : str = "Unnamed Game Server",
        arbiter_ip : str = "127.0.0.1",
        arbiter_port : int = 3000,
        arbiter_access_key : str = "",
        last_heartbeat : datetime | None = None,
        response_time : float = 0,
        memory_usage : float = 0,
        memory_size : float = 0,
        processor_usage : float = 0,
        processor_cores : int = 0,
        thumbnail_queue_size : int = 0,

        is_thumbnail_renderer : bool = False,
        is_game_hoster : bool = False,
        is_asset_validator : bool = False
    ):
        self.id = id if id is not None else uuid.uuid4()
        self.name = name
        self.arbiter_ip = arbiter_ip
        self.arbiter_port = arbiter_port
        self.arbiter_access_key = arbiter_access_key
        self.last_heartbeat = last_heartbeat if last_heartbeat is not None else datetime.utcnow()
        self.response_time = response_time
        self.memory_usage = memory_usage
        self.memory_size = memory_size
        self.processor_usage = processor_usage
        self.processor_cores = processor_cores
        self.thumbnail_queue_size = thumbnail_queue_size
        self.is_thumbnail_renderer = is_thumbnail_renderer
        self.is_game_hoster = is_game_hoster
        self.is_asset_validator = is_asset_validator

    def __repr__(self) -> str:
        return f"<GameServer {self.name} - {str(self.id)}>"