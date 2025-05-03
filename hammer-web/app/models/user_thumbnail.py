from app.extensions import db
from datetime import datetime

class UserThumbnail( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey('user.id'), primary_key = True, index = True )
    
    fullbody_content_hash = db.Column( db.Text, nullable = True, index = True )
    last_fullbody_updated = db.Column( db.DateTime, nullable = True )
    headshot_content_hash = db.Column( db.Text, nullable = True, index = True )
    last_headshot_updated = db.Column( db.DateTime, nullable = True )
    body_3d_content_hash = db.Column( db.Text, nullable = True, index = True )
    last_body_3d_updated = db.Column( db.DateTime, nullable = True )
    
    def __init__( self, user_id : int ):
        self.user_id = user_id
        self.fullbody_content_hash = None
        self.last_fullbody_updated = None
        self.headshot_content_hash = None
        self.last_headshot_updated = None
        self.body_3d_content_hash = None
        self.last_body_3d_updated = None
        
    def __repr__( self ):
        return f"<UserThumbnail {self.user_id}>"