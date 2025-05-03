from app.extensions import db
from datetime import datetime

class AssetVersion( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True, nullable = False )
    asset_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id" ), nullable = False, index = True )
    version_number = db.Column( db.Integer, nullable = False, default = 1 )
    created_at = db.Column( db.DateTime, nullable = False, index = True )
    content_hash = db.Column( db.Text, nullable = False, index = True )

    uploader_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = True, index = True )

    def __init__( self, asset_id : int, version_number : int, content_hash : str, uploader_id : int = None ):
        self.asset_id = asset_id
        self.version_number = version_number
        self.content_hash = content_hash
        self.created_at = datetime.utcnow()
        self.uploader_id = uploader_id

    def __repr__( self ):
        return f"<AssetVersion {self.id}, asset_id={self.asset_id}, version_number={self.version_number}, created_at={self.created_at}>"