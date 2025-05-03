from datetime import datetime
from app.extensions import db
from app.enums.InventoryPrivacy import InventoryPrivacy
from app.enums.MessagePrivacy import MessagePrivacy
from app.enums.GameJoinPrivacy import GameJoinPrivacy

class UserSettings( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey('user.id'), primary_key = True, nullable = False, index = True )
    last_modified = db.Column( db.DateTime, nullable = False )
    inventory_privacy = db.Column( db.Enum( InventoryPrivacy ), nullable = False, default = InventoryPrivacy.FriendsandFollowing )
    message_privacy = db.Column( db.Enum( MessagePrivacy ), nullable = False, default = MessagePrivacy.FriendsandFollowing )
    game_join_privacy = db.Column( db.Enum( GameJoinPrivacy ), nullable = False, default = GameJoinPrivacy.FriendsandFollowing )
    
    def __init__( self, user_id : int ):
        self.user_id = user_id
        self.last_modified = datetime.utcnow()
        self.inventory_privacy = InventoryPrivacy.FriendsandFollowing
        self.message_privacy = MessagePrivacy.FriendsandFollowing
        self.game_join_privacy = GameJoinPrivacy.FriendsandFollowing
        
    def __repr__( self ):
        return f"<UserSettings user_id={self.user_id}, last_modified={self.last_modified}, inventory_privacy={self.inventory_privacy}, message_privacy={self.message_privacy}, game_join_privacy={self.game_join_privacy}>"