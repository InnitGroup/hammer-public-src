from app.models.user import User
from app.models.groups import Group
from app.models.product import Product
from app.models.economy_transaction import EconomyTransaction
from app.enums.TransactionType import TransactionType
from app.enums.CreatorType import CreatorType
from app.enums.CurrencyType import CurrencyType
from app.extensions import db

async def get_default_user() -> User:
    return User.query.filter_by( id = 1 ).first()

async def create_economy_transaction(
    transaction_type : TransactionType = TransactionType.ProductPurchase,
    product_purchaser : User | Group | None = None,
    product_seller : User | Group | None = None,
    related_product : Product | None = None,
    currency_type : CurrencyType = CurrencyType.Robux,
    sale_price : int = 0,
    marketplace_fee : int = 0
) -> EconomyTransaction:
    if product_purchaser is None:
        product_purchaser = await get_default_user()
    if product_seller is None:
        product_seller = await get_default_user()
    
    new_transaction = EconomyTransaction(
        transaction_type = transaction_type,
        purchaser_id = product_purchaser.id,
        purchaser_type = CreatorType.User if isinstance( product_purchaser, User ) else CreatorType.Group,
        seller_id = product_seller.id,
        seller_type = CreatorType.User if isinstance( product_seller, User ) else CreatorType.Group,
        related_product_id = related_product.id if related_product is not None else None,
        currency_type = currency_type,
        sale_price = sale_price,
        marketplace_fee = marketplace_fee
    )
    db.session.add( new_transaction )
    db.session.commit()
    
    return new_transaction