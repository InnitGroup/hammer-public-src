from app.extensions import db
from datetime import datetime

class VersionCompatibilityKey( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    parent_group_id = db.Column( db.BigInteger, db.ForeignKey( "version_compatibility_group.id" ), nullable = False, index = True )
    display_name = db.Column( db.String( 255 ), nullable = False, default = "Unnamed Key")
    key_value = db.Column( db.String( 512 ), nullable = False, index = True )

    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )

    def __init__( self, parent_group_id : int, key_value : str, display_name : str = "Unnamed Key"):
        self.parent_group_id = parent_group_id
        self.key_value = key_value
        self.display_name = display_name

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def __repr__( self ):
        return f"<VersionCompatibilityKey {self.id}>"