from datetime import datetime
from app.extensions import db

class InviteKey( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    creator_user_id = db.Column( db.BigInteger, nullable = True, index = True )
    key_string = db.Column( db.Text, nullable = False, index = True )
    created_at = db.Column( db.DateTime, nullable = False )
    redeemed_at = db.Column( db.DateTime, nullable = True )
    redeemed_by_user_id = db.Column( db.BigInteger, nullable = True )
    
    def __init__( self, creator_user_id : int | None, key_string : str ):
        self.creator_user_id = creator_user_id
        self.key_string = key_string
        self.created_at = datetime.utcnow()
        self.redeemed_at = None
        self.redeemed_by_user_id = None
    
    def __repr__( self ):
        return f"<InviteKey {self.key_string}>"