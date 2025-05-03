from datetime import datetime

from app.extensions import db
from app.enums.AccountStatus import AccountStatus

class User( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    username = db.Column( db.Text, nullable = False, index = True )
    password = db.Column( db.Text, nullable = False, default = "") # Authentication service will handle the hashing once the user is created

    description = db.Column( db.Text, nullable = False, default = "")

    created_at = db.Column( db.DateTime, nullable = False, index = True )
    lastonline_at = db.Column( db.DateTime, nullable = False, index = True )

    account_status = db.Column( db.Enum( AccountStatus ), nullable = False, default = AccountStatus.Active )
    permissions = db.Column( db.BigInteger, nullable = False, default = 0 ) # Bitmask for admin permissions
    two_factor_enabled = db.Column( db.Boolean, nullable = False, default = False )

    def __init__(
        self,
        username : str,
        description : str = "Hi, I'm new here!",
        permissions : int = 0,
        two_factor_enabled : bool = False
    ):
        self.username = username
        self.description = description
        self.created_at = datetime.utcnow()
        self.lastonline_at = datetime.utcnow()
        self.permissions = permissions
        self.two_factor_enabled = two_factor_enabled

    def __repr__( self ):
        return f"<User {self.id}, {self.username}>"