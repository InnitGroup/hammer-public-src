from app.extensions import db
from app.enums.CreatorType import CreatorType
from app.enums.BundleType import BundleType
from datetime import datetime

class Bundle( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    rbx_bundle_id = db.Column( db.BigInteger, nullable = True, default = None )
    name = db.Column( db.Text, nullable = False, index = True )
    description = db.Column( db.Text, nullable = False )
    bundle_type = db.Column( db.Enum( BundleType ), nullable = False, index = True, default = BundleType.BodyParts )
    created_at = db.Column( db.DateTime, index = True, nullable = False )
    updated_at = db.Column( db.DateTime, index = True, nullable = False )
    
    creator_id = db.Column( db.BigInteger, nullable = False, index = True, default = 1 )
    creator_type = db.Column( db.Enum( CreatorType ), nullable = False, index = True, default = CreatorType.User )
    
    product_id = db.Column( db.BigInteger, db.ForeignKey( "product.id" ), nullable = True, index = True )
    
    def __init__( 
        self, 
        name : str, 
        description : str, 
        bundle_type : BundleType = BundleType.BodyParts, 
        rbx_bundle_id : int | None = None, 
        creator_id : int = 1, 
        creator_type : CreatorType = CreatorType.User,
        
        bundle_id_override : int | None = None,
    ):
        self.name = name
        self.description = description
        self.bundle_type = bundle_type
        self.rbx_bundle_id = rbx_bundle_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.creator_id = creator_id
        self.creator_type = creator_type
    
        if bundle_id_override is not None:
            self.id = bundle_id_override
    
    def __repr__( self ):
        return f"<Bundle {self.id}, name={self.name}, created_at={self.created_at}>"