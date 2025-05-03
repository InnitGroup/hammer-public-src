from datetime import datetime

from app.extensions import db

class SessionToken( db.Model ):
    token = db.Column( db.Text, primary_key = True, unique = True, nullable = False )
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False )
    created_at = db.Column( db.DateTime, nullable = False )
    expiration = db.Column( db.DateTime, nullable = False )

    creation_context = db.Column( db.Text, nullable = False, default = "Unknown" )

    def __init__( self, token : str, user_id : int, expiration : datetime, creation_context : str = "Unknown" ):
        self.token = token
        self.user_id = user_id
        self.created_at = datetime.utcnow()
        self.expiration = expiration
        self.creation_context = creation_context

    def __repr__( self ):
        return f"<SessionToken {self.token}, {self.user_id}, {self.expiration}>"