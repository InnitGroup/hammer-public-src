from app.extensions import db
from datetime import datetime

class BundleItem( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    bundle_id = db.Column( db.BigInteger, db.ForeignKey( "bundle.id" ), nullable = False, index = True )
    asset_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id" ), nullable = False, index = True )
    created_at = db.Column( db.DateTime, nullable = False )
    
    def __init__( self, bundle_id : int, asset_id : int ):
        self.bundle_id = bundle_id
        self.asset_id = asset_id
        self.created_at = datetime.utcnow()
        
    def __repr__( self ):
        return f"<BundleItem {self.bundle_id} -> {self.asset_id}>"