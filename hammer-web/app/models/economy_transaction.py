from datetime import datetime, timezone
from app.extensions import db
from app.enums.TransactionType import TransactionType
from app.enums.CreatorType import CreatorType
from app.enums.CurrencyType import CurrencyType

class EconomyTransaction( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    transaction_type = db.Column( db.Enum( TransactionType ), nullable = False, index = True, default = TransactionType.ProductPurchase )
    
    purchaser_id = db.Column( db.BigInteger, nullable = False, index = True, default = 1 )
    purchaser_type = db.Column( db.Enum( CreatorType ), nullable = False, index = True, default = CreatorType.User )
    seller_id = db.Column( db.BigInteger, nullable = False, index = True, default = 1)
    seller_type = db.Column( db.Enum( CreatorType ), nullable = False, index = True, default = CreatorType.User )
    
    related_product_id = db.Column( db.BigInteger, nullable = True, index = True )
    
    currency_type = db.Column( db.Enum( CurrencyType ), nullable = False, index = True, default = CurrencyType.Robux )
    sale_price = db.Column( db.BigInteger, nullable = False, index = True, default = 0 )
    marketplace_fee = db.Column( db.BigInteger, nullable = False, index = True, default = 0 )
    
    created_at = db.Column( db.DateTime, nullable = False, index = True )
    
    def __init__(
        self,
        transaction_type : TransactionType = TransactionType.ProductPurchase,
        purchaser_id : int = 1,
        purchaser_type : CreatorType = CreatorType.User,
        seller_id : int = 1,
        seller_type : CreatorType = CreatorType.User,
        related_product_id : int | None = None,
        currency_type : CurrencyType = CurrencyType.Robux,
        sale_price : int = 0,
        marketplace_fee : int = 0
    ):
        self.transaction_type = transaction_type
        self.purchaser_id = purchaser_id
        self.purchaser_type = purchaser_type
        self.seller_id = seller_id
        self.seller_type = seller_type
        self.related_product_id = related_product_id
        self.currency_type = currency_type
        self.sale_price = sale_price
        self.marketplace_fee = marketplace_fee
        self.created_at = datetime.now( timezone.utc )
    
    def __repr__( self ):
        return f"<EconomyTransaction { self.id }>"