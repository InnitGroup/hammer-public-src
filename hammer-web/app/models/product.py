from datetime import datetime
from app.extensions import db
from app.enums.ProductType import ProductType
from app.enums.RobloxProductType import RobloxProductType
from app.enums.AssetType import AssetType
from app.enums.MembershipType import MembershipType

class Product( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    product_type = db.Column( db.Enum( ProductType ), nullable = False, default = ProductType.UserProduct, index = True )
    is_public_domain = db.Column( db.Boolean, nullable = False, default = False )
    is_for_sale = db.Column( db.Boolean, nullable = False, default = False, index = True )
    price_in_robux = db.Column( db.BigInteger, nullable = True, default = None, index = True )
    price_in_tickets = db.Column( db.BigInteger, nullable = True, default = None, index = True )
    roblox_product_type = db.Column( db.Enum( RobloxProductType ), nullable = True, default = None, index = True )
    asset_id = db.Column( db.BigInteger, nullable = True, default = None, index = True )
    asset_type = db.Column( db.Enum( AssetType ), nullable = True, default = None, index = True )
    
    total_sold = db.Column( db.BigInteger, nullable = False, default = 0, index = True )
    
    """
        is_limited_edition = Limited Unique
        is_resellable = Limited
    """
    is_limited_edition = db.Column( db.Boolean, nullable = False, default = False, index = True )
    is_resellable = db.Column( db.Boolean, nullable = False, default = False, index = True )
    total_available = db.Column( db.BigInteger, nullable = True, default = None )
    number_remaining = db.Column( db.BigInteger, nullable = True, default = None )
    minimum_membership_level = db.Column( db.Enum( MembershipType ), nullable = False, default = MembershipType.None_ )    
    offsale_deadline = db.Column( db.DateTime, nullable = True, default = None )
    
    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )
    
    def __init__(
        self,
        product_type : ProductType = ProductType.UserProduct,
        is_public_domain : bool = False,
        is_for_sale : bool = False,
        price_in_robux : int | None = None,
        price_in_tickets : int | None = None,
        roblox_product_type : int | None = None,
        asset_id : int | None = None,
        asset_type : AssetType | None = None,
        
        total_sold : int = 0,
        
        is_limited_edition : bool = False,
        is_resellable : bool = False,
        total_available : int | None = None,
        number_remaining : int | None = None,
        minimum_membership_level : MembershipType = MembershipType.None_,
        offsale_deadline : datetime | None = None
    ):
        self.product_type = product_type
        self.is_public_domain = is_public_domain
        self.is_for_sale = is_for_sale
        self.price_in_robux = price_in_robux
        self.price_in_tickets = price_in_tickets
        self.roblox_product_type = roblox_product_type
        self.asset_id = asset_id
        self.asset_type = asset_type
        
        self.total_sold = total_sold
        
        self.is_limited_edition = is_limited_edition
        self.is_resellable = is_resellable
        self.total_available = total_available
        self.number_remaining = number_remaining
        self.minimum_membership_level = minimum_membership_level
        self.offsale_deadline = offsale_deadline
        
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def __repr__( self ) -> str:
        return f"<Product {self.id} {self.product_type}>"