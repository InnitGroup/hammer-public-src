import redis_lock
import logging
import asyncio
import math
from datetime import datetime

from app.services import assets, groups
from app.services.economy import balance, transactions

from app.models.groups import Group
from app.models.user import User
from app.models.user_asset import UserAsset
from app.models.asset import Asset
from app.models.product import Product
from app.models.economy_transaction import EconomyTransaction
from app.enums.ProductType import ProductType
from app.enums.CurrencyType import CurrencyType
from app.enums.WebsiteFeature import WebsiteFeature
from app.enums.CreatorType import CreatorType
from app.enums.RobloxProductType import RobloxProductType
from app.enums.TransactionType import TransactionType

from app.extensions import db, redis_controller, sync_redis_controller
from app.util.websiteFeatures import GetWebsiteFeature
from app.util.default_rbx_product_prices import DefaultPrices

class CatchAllEconomyPurchaseExceptions( Exception ):
    pass
class EconomyPurchaseExceptions:
    class LockAcquisitionFailed( CatchAllEconomyPurchaseExceptions ):
        pass
    class InvalidCurrencyType( CatchAllEconomyPurchaseExceptions ):
        pass
    class InsufficientBalance( CatchAllEconomyPurchaseExceptions ):
        pass
    class InternalServiceError( CatchAllEconomyPurchaseExceptions ):
        pass
    class EconomyDisabled( CatchAllEconomyPurchaseExceptions ):
        pass
    class ItemIsLimited( CatchAllEconomyPurchaseExceptions ):
        pass
    class ItemIsNotForSale( CatchAllEconomyPurchaseExceptions ):
        pass
    class ItemIsNotForSaleInGivenCurrency( CatchAllEconomyPurchaseExceptions ):
        pass
    class ItemAlreadyOwned( CatchAllEconomyPurchaseExceptions ):
        pass
    class RobloxProductUnavailable( CatchAllEconomyPurchaseExceptions ):
        pass

def CalculateMarketplaceFee( currency_amount : int ) -> int:
    return math.floor( currency_amount * 0.3 )

async def GetProductByRbxProductType( product_type : RobloxProductType ) -> Product:
    product_query : Product | None = Product.query.filter_by( product_type = ProductType.RobloxProduct, roblox_product_type = product_type ).first()
    if product_query is not None:
        return product_query
    if product_type not in DefaultPrices:
        raise EconomyPurchaseExceptions.RobloxProductUnavailable( f"Roblox Product Type {product_type} is not available" )
    robux_price = DefaultPrices[ product_type ][ CurrencyType.Robux ]
    tickets_price = DefaultPrices[ product_type ][ CurrencyType.Tickets ]
    new_product = Product(
        product_type = ProductType.RobloxProduct,
        is_for_sale = robux_price >= 0 or tickets_price >= 0,
        price_in_robux = robux_price if robux_price >= 0 else None,
        price_in_tickets = tickets_price if tickets_price >= 0 else None,
        roblox_product_type = product_type
    )
    db.session.add( new_product )
    db.session.commit()
    
    return new_product

async def DoesUserOwnAsset( user : User, asset : Asset ) -> bool:
    return UserAsset.query.filter_by( owner_user_id = user.id, asset_id = asset.id ).first() is not None

async def GetProductById( product_id : int ) -> Product:
    return Product.query.filter_by( id = product_id ).first()

async def CreditItemCreator(
    item : Asset,
    currency : CurrencyType,
    amount : int
) -> None:
    creator_obj : User | Group = None
    if item.creator_type == CreatorType.User:
        creator_obj = User.query.filter_by( id = item.creator_id ).first()
    else:
        creator_obj = groups.GetGroupFromId( item.creator_id )
    try:
        await balance.IncrementTargetBalance(
            TargetObj = creator_obj,
            Currency = currency,
            Amount = amount
        )
    except balance.EconomyBalanceExceptions.LockAcquisitionFailed:
        raise EconomyPurchaseExceptions.LockAcquisitionFailed( f"Failed to acquire lock for {item.creator_type} {item.creator_id}" )
    except balance.EconomyBalanceExceptions.InternalServiceError:
        raise EconomyPurchaseExceptions.InternalServiceError( f"Failed to credit creator {item.creator_type} {item.creator_id} for item {item.id}" )

async def GetProductCreator( product : Product ) -> User | Group:
    if product.product_type == ProductType.UserProduct:
        product_asset_obj : Asset = await assets.GetAssetById( product.asset_id )
        if product_asset_obj.creator_type == CreatorType.User:
            return User.query.filter_by( id = product_asset_obj.creator_id ).first()
        else:
            return groups.GetGroupFromId( product_asset_obj.creator_id )
    elif product.product_type == ProductType.RobloxProduct:
        return User.query.filter_by( id = 1 ).first()
    else:
        raise NotImplementedError( f"Product Type { product.product_type} is not supported yet" )

async def CreditProductCreator(
    product : Product,
    currency : CurrencyType,
    amount : int
) -> None:
    creator_obj : User | Group = await GetProductCreator( product )
    target_creator_type = "User" if isinstance( creator_obj, User ) else "Group"
    target_id = creator_obj.id
    try:
        await balance.IncrementTargetBalance(
            TargetObj = creator_obj,
            Currency = currency,
            Amount = amount
        )
    except balance.EconomyBalanceExceptions.LockAcquisitionFailed:
        raise EconomyPurchaseExceptions.LockAcquisitionFailed( f"Failed to acquire lock for {target_creator_type} {target_id}" )
    except balance.EconomyBalanceExceptions.InternalServiceError:
        raise EconomyPurchaseExceptions.InternalServiceError( f"Failed to credit creator {target_creator_type} {target_id} for product {product.id}" )

async def PurchaseProduct(
    purchaser : User,
    product : Product,
    currency : CurrencyType,
    
    expected_price : int | None = None,
    allow_limited_purchase : bool = False,
    allow_resellable_purchase : bool = False,
    bypass_feature_lock : bool = False
) -> bool:
    if not await GetWebsiteFeature( WebsiteFeature.EconomyPurchases ) and not bypass_feature_lock:
        raise EconomyPurchaseExceptions.EconomyDisabled
    lock_name = f"economy_purchase_lock_user:{purchaser.id}"
    product_purchase_lock_name = f"economy_purchase_lock_product:{product.id}"
    try:
        with redis_lock.Lock( redis_client = sync_redis_controller, name = lock_name, expire = 10, auto_renewal = True ):
            if currency == CurrencyType.Robux and product.price_in_robux is None:
                raise EconomyPurchaseExceptions.ItemIsNotForSaleInGivenCurrency( f"Product {product.id} is not for sale in currency {currency}" )
            elif currency == CurrencyType.Tickets and product.price_in_tickets is None:
                raise EconomyPurchaseExceptions.ItemIsNotForSaleInGivenCurrency( f"Product {product.id} is not for sale in currency {currency}" )
            elif product.is_limited_edition and product.product_type == ProductType.UserProduct and not allow_limited_purchase:
                raise EconomyPurchaseExceptions.ItemIsLimited( f"Product {product.id} is limited" )
            elif product.product_type == ProductType.ResellableProduct and not allow_resellable_purchase:
                raise EconomyPurchaseExceptions.ItemIsLimited( f"Product {product.id} is limited" )
            
            if product.product_type == ProductType.UserProduct and product.asset_id is not None:
                product_asset_obj : Asset = await assets.GetAssetById( product.asset_id )
                if await DoesUserOwnAsset( user = purchaser, asset = product_asset_obj ):
                    raise EconomyPurchaseExceptions.ItemAlreadyOwned( f"User {purchaser.id} already owns asset {product_asset_obj.id}" )
            
            with redis_lock.Lock( redis_client = sync_redis_controller, name = product_purchase_lock_name, expire = 10, auto_renewal = True ):
                if not product.is_for_sale:
                    raise EconomyPurchaseExceptions.ItemIsNotForSale( f"Product {product.id} is not for sale" )
                if product.price_in_robux is not None and currency == CurrencyType.Robux:
                    if expected_price is not None and product.price_in_robux != expected_price:
                        raise EconomyPurchaseExceptions.InsufficientBalance( f"Product {product.id} has a different price than expected" )
                elif product.price_in_tickets is not None and currency == CurrencyType.Tickets:
                    if expected_price is not None and product.price_in_tickets != expected_price:
                        raise EconomyPurchaseExceptions.InsufficientBalance( f"Product {product.id} has a different price than expected" )
                
                if product.offsale_deadline is not None and product.offsale_deadline < datetime.utcnow():
                    product.offsale_deadline = None
                    product.is_for_sale = False
                    db.session.commit()
                    raise EconomyPurchaseExceptions.ItemIsNotForSale( f"Product {product.id} is offsale" )
            
                try:
                    await balance.DecrementTargetBalance(
                        TargetObj = purchaser,
                        Currency = currency,
                        Amount = product.price_in_robux if currency == CurrencyType.Robux else product.price_in_tickets
                    )
                except balance.EconomyBalanceExceptions.InsufficientBalance:
                    raise EconomyPurchaseExceptions.InsufficientBalance( f"User {purchaser.id} has insufficient balance for currency {currency}" )
                except balance.EconomyBalanceExceptions.LockAcquisitionFailed:
                    raise EconomyPurchaseExceptions.LockAcquisitionFailed( f"Failed to acquire lock for user {purchaser.id}" )
                except balance.EconomyBalanceExceptions.InternalServiceError:
                    raise EconomyPurchaseExceptions.InternalServiceError( f"Failed to decrement balance for user {purchaser.id}" )
                
                product.total_sold += 1
                
                serial_number = None
                if product.number_remaining is not None:
                    product.number_remaining -= 1
                    serial_number = product.total_sold
                    if product.number_remaining <= 0:
                        product.is_for_sale = False
                        if product.is_limited_edition and not product.is_resellable:
                            product.is_resellable = True
                db.session.commit()
            
            if product.product_type == ProductType.UserProduct:
                newUserAsset = UserAsset(
                    owner_user_id = purchaser.id,
                    asset_id = product.asset_id,
                    serial_number = serial_number
                )
                db.session.add( newUserAsset )
                db.session.commit()
            
            marketplace_fee = CalculateMarketplaceFee( product.price_in_robux if currency == CurrencyType.Robux else product.price_in_tickets )
            
            asyncio.create_task( CreditProductCreator(
                product = product,
                currency = currency,
                amount = (product.price_in_robux if currency == CurrencyType.Robux else product.price_in_tickets) - marketplace_fee
            ) )
            await transactions.create_economy_transaction(
                product_purchaser = purchaser,
                product_seller = await GetProductCreator( product ),
                related_product = product,
                currency_type = currency,
                sale_price = product.price_in_robux if currency == CurrencyType.Robux else product.price_in_tickets,
                marketplace_fee = marketplace_fee
            )
                
            return True
    except AssertionError:
        raise EconomyPurchaseExceptions.LockAcquisitionFailed( f"Failed to acquire lock {lock_name}" )
    except CatchAllEconomyPurchaseExceptions as e:
        raise e
    except Exception as e:
        logging.error( f"services.economy.purchase > PurchaseItem, exception raised: {e}" )
        raise EconomyPurchaseExceptions.InternalServiceError( f"Failed to purchase item for user {purchaser.id}" )