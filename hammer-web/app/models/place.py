from app.extensions import db
from app.enums.PlaceRigChoice import PlaceRigChoice
from app.enums.ChatStyle import ChatStyle

class Place( db.Model ):
    place_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id"), primary_key = True, nullable = False, index = True, unique = True )
    visit_count = db.Column( db.BigInteger, nullable = False, default = 0 )
    
    max_players = db.Column( db.Integer, nullable = False, default = 10 )
    rig_choice = db.Column( db.Enum( PlaceRigChoice ), nullable = False, default = PlaceRigChoice.UserChoice )
    chat_style = db.Column( db.Enum( ChatStyle ), nullable = False, default = ChatStyle.ClassicAndBubble )
    
    parent_universe_id = db.Column( db.BigInteger, db.ForeignKey( "universe.id" ), nullable = True, index = True )
    asset_obj = db.relationship( "Asset", lazy = "joined", uselist = False )
    universe_obj = db.relationship( "Universe", lazy = "joined", uselist = False )
    
    def __init__(
        self,
        place_id : int,
        visit_count : int = 0,
        max_players : int = 10,
        rig_choice : PlaceRigChoice = PlaceRigChoice.UserChoice,
        chat_style : ChatStyle = ChatStyle.ClassicAndBubble,
        parent_universe_id : int | None = None
    ):
        self.place_id = place_id
        self.visit_count = visit_count
        self.max_players = max_players
        self.rig_choice = rig_choice
        self.chat_style = chat_style
        self.parent_universe_id = parent_universe_id
    
    def __repr__( self ):
        return f"<Place id={self.place_id} visit_count={self.visit_count} max_players={self.max_players} rig_choice={self.rig_choice} chat_style={self.chat_style} parent_universe_id={self.parent_universe_id}>"