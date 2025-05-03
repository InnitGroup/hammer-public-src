from app.extensions import db
from datetime import datetime
class FriendRequest( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    sender_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    receiver_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    created_at = db.Column( db.DateTime, index = True, nullable = False )
    
    def __init__( self, sender_id : int, receiver_id : int ):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.created_at = datetime.utcnow()
        
    def __repr__( self ):
        return f"<FriendRequest {self.sender_id} -> {self.receiver_id}>"