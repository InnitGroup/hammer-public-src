from app.extensions import db
from datetime import datetime

class VersionCompatibilityGroup( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    display_name = db.Column( db.String( 255 ), nullable = False, default = "Unnamed Group")
    api_key = db.Column( db.String( 255 ), nullable = False )

    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )

    def __init__( self, display_name : str, api_key : str ):
        self.display_name = display_name
        self.api_key = api_key

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def __repr__( self ):
        return f"<VersionCompatibilityGroup {self.id}>"