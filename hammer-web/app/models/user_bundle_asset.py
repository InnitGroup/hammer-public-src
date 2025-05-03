from app.extensions import db
from datetime import datetime

class UserBundleAsset( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    bundle_id = db.Column( db.BigInteger, db.ForeignKey( "bundle.id" ), nullable = False, index = True )
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    created_at = db.Column( db.DateTime, nullable = False )
    
    def __init__( self, bundle_id : int, user_id : int ):
        self.bundle_id = bundle_id
        self.user_id = user_id
        self.created_at = datetime.utcnow()
        
    def __repr__( self ):
        return f"<UserBundleAsset {self.bundle_id} -> {self.user_id}>"