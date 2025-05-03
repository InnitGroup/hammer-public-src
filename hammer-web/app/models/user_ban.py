from app.extensions import db
from app.enums.BanType import BanType
from datetime import datetime

class UserBan( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    user_id = db.Column( db.BigInteger, nullable = False, index = True )
    ban_type = db.Column( db.Enum( BanType ), nullable = False, index = True )
    
    user_facing_reason = db.Column( db.Text, nullable = False )
    admin_facing_reason = db.Column( db.Text, nullable = False )
    administrator_user_id = db.Column( db.BigInteger, nullable = False, index = True )
    
    created_at = db.Column( db.DateTime, nullable = False )
    expires_at = db.Column( db.DateTime, nullable = True )
    
    acknowledged_at = db.Column( db.DateTime, nullable = True, default = None )
    has_been_acknowledged = db.Column( db.Boolean, nullable = False, default = False )
    
    def __init__(
        self,
        user_id : int,
        ban_type : BanType,
        user_facing_reason : str,
        admin_facing_reason : str,
        administrator_user_id : int,
        expires_at : datetime | None
    ):
        self.user_id = user_id
        self.ban_type = ban_type
        self.user_facing_reason = user_facing_reason
        self.admin_facing_reason = admin_facing_reason
        self.administrator_user_id = administrator_user_id
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at
    
    def __repr__( self ):
        return f"<UserBan user_id={self.user_id}, ban_type={self.ban_type}, expires_at={self.expires_at}>"