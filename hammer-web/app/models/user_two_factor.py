from app.extensions import db
from datetime import datetime

class UserTwoFactorSettings( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), primary_key = True )
    two_factor_secret_seed = db.Column( db.Text, nullable = False )
    two_factor_enabled = db.Column( db.Boolean, nullable = False )
    last_updated = db.Column( db.DateTime, nullable = False )

    def __init__( self, user_id : int, two_factor_secret_seed : str, two_factor_enabled : bool, last_updated : datetime | None ):
        self.user_id = user_id
        self.two_factor_secret_seed = two_factor_secret_seed
        self.two_factor_enabled = two_factor_enabled
        self.last_updated = last_updated if last_updated is not None else datetime.utcnow()

    def __repr__( self ):
        return f"<UserTwoFactor user_id={self.user_id}, two_factor_enabled={self.two_factor_enabled}, last_updated={self.last_updated}>"