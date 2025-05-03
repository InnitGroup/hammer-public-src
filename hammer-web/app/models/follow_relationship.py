from app.extensions import db
from datetime import datetime

class FollowRelationship( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    follower_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    following_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    created_at = db.Column( db.DateTime, index = True, nullable = False )
    
    def __init__( self, follower_id : int, following_id : int ):
        self.follower_id = follower_id
        self.following_id = following_id
        self.created_at = datetime.utcnow()
        
    def __repr__( self ):
        return f"<FollowRelationship {self.follower_id} -> {self.following_id}>"