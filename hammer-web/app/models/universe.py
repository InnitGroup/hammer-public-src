from datetime import datetime
from app.extensions import db
from app.enums.CreatorType import CreatorType
from app.enums.PlaceYear import PlaceYear
from app.enums.ModerationStatus import ModerationStatus

class Universe( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    name = db.Column( db.String( 255 ), nullable = False, default = "Untitled Place", index = True )
    description = db.Column( db.Text, nullable = False, default = "" )
    root_place_id = db.Column( db.BigInteger, nullable = False, index = True )
    
    creator_id = db.Column( db.BigInteger, nullable = False, index = True )
    creator_type = db.Column( db.Enum( CreatorType ), nullable = False, default = CreatorType.User )
    
    place_year = db.Column( db.Enum( PlaceYear ), nullable = False, default = PlaceYear.TwentyOne )
    is_featured = db.Column( db.Boolean, nullable = False, default = False )
    minimum_account_age = db.Column( db.Integer, nullable = False, default = 0 )
    membership_required = db.Column( db.Boolean, nullable = False, default = False )
    is_public = db.Column( db.Boolean, nullable = False, default = True )
    moderation_status = db.Column( db.Enum( ModerationStatus ), nullable = False, default = ModerationStatus.Approved )
    visit_count = db.Column( db.BigInteger, nullable = False, default = 0, index = True )
    active_player_count = db.Column( db.Integer, nullable = False, default = 0, index = True )
    
    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )
    
    def __init__(
        self,
        root_place_id : int,
        creator_id : int,
        creator_type : CreatorType = CreatorType.User,
        
        name : str = "Untitled Place",
        description : str = "",
        place_year : PlaceYear = PlaceYear.TwentyOne,
        is_featured : bool = False,
        minimum_account_age : int = 0,
        membership_required : bool = False,
        is_public : bool = True,
        moderation_status : ModerationStatus = ModerationStatus.Approved,
        visit_count : int = 0,
        
        created_at : datetime | None = None,
        updated_at : datetime | None = None
    ):
        self.root_place_id = root_place_id
        self.creator_id = creator_id
        self.creator_type = creator_type
        
        self.name = name
        self.description = description
        self.place_year = place_year
        self.is_featured = is_featured
        self.minimum_account_age = minimum_account_age
        self.membership_required = membership_required
        self.is_public = is_public
        self.moderation_status = moderation_status
        self.visit_count = visit_count
        
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def __repr__( self ):
        return f"<{self.__class__.__name__} id={self.id} creator_id={self.creator_id} name={self.name}>"