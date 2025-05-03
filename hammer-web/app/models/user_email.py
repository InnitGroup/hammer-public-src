from app.extensions import db
from datetime import datetime

class UserEmail( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey('user.id'), primary_key = True )
    email = db.Column( db.String(512), nullable = True )
    is_verified = db.Column( db.Boolean, default = False )
    last_updated = db.Column( db.DateTime, nullable = False, index = True )
    last_verified = db.Column( db.DateTime, nullable = True, index = True )
    last_email_verification_request = db.Column( db.DateTime, nullable = True, index = True )

    def __init__( self, user_id : int, email : str, is_verified : bool = False ):
        self.user_id = user_id
        self.email = email
        self.is_verified = is_verified
        self.last_updated = datetime.utcnow()
        self.last_verified = None 
        self.last_email_verification_request = None

    def __repr__( self ):
        return f"<UserEmail user_id={self.user_id}, email={self.email}, is_verified={self.is_verified}, last_updated={self.last_updated}, last_verified={self.last_verified}, last_email_verification_request={self.last_email_verification_request}>"