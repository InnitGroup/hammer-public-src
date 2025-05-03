from app.extensions import db
from datetime import datetime

class FriendRelationship( db.Model ):
    id = db.Column( db.Integer, primary_key = True, autoincrement = True )
    """
        !IMPORTANT!
        first_user_id should always be the lowest of the two userIDS of the relationship
        this is to ease the process of finding relationships between two users
    """
    first_user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    second_user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    created_at = db.Column( db.DateTime, index = True, nullable = False )
    
    def __init__( self, first_user_id : int, second_user_id : int ):
        if first_user_id < second_user_id:
            self.first_user_id = first_user_id
            self.second_user_id = second_user_id
        else:
            self.first_user_id = second_user_id
            self.second_user_id = first_user_id
        self.created_at = datetime.utcnow()
    
    def __repr__( self ):
        return f"<FriendRelationship {self.first_user_id} -> {self.second_user_id}>"