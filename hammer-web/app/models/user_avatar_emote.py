from app.extensions import db
from datetime import datetime

class UserAvatarEmote( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey('user.id'), primary_key = True, index = True, unique = True, nullable = False )
    emote_position = db.Column( db.SmallInteger, primary_key = True, unique = True, nullable = False )
    emote_id = db.Column( db.BigInteger, db.ForeignKey('asset.id'), nullable = False )
    created_at = db.Column( db.DateTime, nullable = False )
    
    def __init__( self, user_id, emote_position, emote_id ):
        self.user_id = user_id
        self.emote_position = emote_position
        self.emote_id = emote_id
        self.created_at = datetime.utcnow()
        
    def __repr__( self ):
        return f"<UserAvatarEmote {self.user_id} {self.emote_position} {self.emote_id}>"