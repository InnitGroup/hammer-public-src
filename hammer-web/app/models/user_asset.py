from app.extensions import db
from datetime import datetime

class UserAsset( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True, nullable = False )
    owner_user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), nullable = False, index = True )
    asset_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id" ), nullable = False, index = True )

    created_at = db.Column( db.DateTime, nullable = False, index = True )
    updated_at = db.Column( db.DateTime, nullable = False, index = True )

    serial_number = db.Column( db.BigInteger, nullable = True, default = None )
    product_id = db.Column( db.BigInteger, db.ForeignKey( "product.id" ), nullable = True, index = True )

    def __init__( self, owner_user_id : int, asset_id : int, serial_number : int | None ):
        self.owner_user_id = owner_user_id
        self.asset_id = asset_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.serial_number = serial_number

    def __repr__( self ):
        return f"<UserAsset {self.id}, owner_user_id={self.owner_user_id}, asset_id={self.asset_id}, serial_number={self.serial_number}, created_at={self.created_at}>"