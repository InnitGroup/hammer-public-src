from app.extensions import db
from datetime import datetime

class UserAvatarItem( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    asset_id = db.Column( db.BigInteger, nullable = False, index = True )
    created_at = db.Column( db.DateTime, nullable = False )
    
    def __init__( self, user_id : int, asset_id : int ):
        self.user_id = user_id
        self.asset_id = asset_id
        self.created_at = datetime.utcnow()