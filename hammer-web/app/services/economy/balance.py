import redis_lock
import logging

from app.models.user_economy import UserEconomy
from app.models.user import User
from app.models.groups import Group, GroupEconomy
from app.enums.CurrencyType import CurrencyType

from app.extensions import db, redis_controller

class EconomyBalanceExceptions:
    class LockAcquisitionFailed( Exception ):
        pass
    class InvalidCurrencyType( Exception ):
        pass
    class InsufficientBalance( Exception ):
        pass
    class InternalServiceError( Exception ):
        pass

async def _get_lock_name( TargetObj : User | Group ):
    if isinstance( TargetObj, User ):
        return f"economy_lock_user_{TargetObj.id}"
    if isinstance( TargetObj, Group ):
        return f"economy_lock_group_{TargetObj.id}"
    raise ValueError( f"Invalid type for TargetObj: {type(TargetObj)}" )

async def GetTargetEconomyObject( TargetObj : User | Group ) -> UserEconomy:
    if isinstance( TargetObj, User ):
        UserEconomyObj : UserEconomy | None = UserEconomy.query.filter_by( user_id = TargetObj.id ).first()
        if UserEconomyObj is not None:
            return UserEconomyObj
        UserEconomyObj = UserEconomy( user_id = TargetObj.id )
        db.session.add( UserEconomyObj )
        db.session.commit()
        
        return UserEconomyObj
    if isinstance( TargetObj, Group ):
        GroupEconomyObj : GroupEconomy | None = GroupEconomy.query.filter_by( group_id = TargetObj.id ).first()
        if GroupEconomyObj is not None:
            return GroupEconomyObj
        GroupEconomyObj = GroupEconomy( group_id = TargetObj.id )
        db.session.add( GroupEconomyObj )
        db.session.commit()
        
        return GroupEconomyObj
    
    raise ValueError( f"Invalid type for TargetObj: {type(TargetObj)}" )

async def IncrementTargetBalance( TargetObj : User | Group, Currency : CurrencyType, Amount : int ):
    lock_name = _get_lock_name( TargetObj )
    try:
        with redis_lock.Lock( redis_client = redis_controller, name = lock_name, expire = 10, auto_renewal = True ):
            await _UnsafeIncrementBalance( TargetObj, Currency, Amount )
    except AssertionError:
        raise EconomyBalanceExceptions.LockAcquisitionFailed( f"Failed to acquire lock {lock_name}" )
    except Exception as e:
        logging.error( f"services.economy.balance > IncrementTargetBalance, exception raised: {e}" )
        raise EconomyBalanceExceptions.InternalServiceError( f"Failed to increment balance for user {TargetObj.id}" )
    
async def DecrementTargetBalance( TargetObj : User | Group, Currency : CurrencyType, Amount : int ):
    lock_name = _get_lock_name( TargetObj )
    try:
        with redis_lock.Lock( redis_client = redis_controller, name = lock_name, expire = 10, auto_renewal = True ):
            TargetEconomyObj : UserEconomy = await GetTargetEconomyObject( TargetObj = TargetObj )
            if Currency == CurrencyType.Robux and TargetEconomyObj.robux_bal < Amount:
                raise EconomyBalanceExceptions.InsufficientBalance( f"User {TargetObj.id} has insufficient balance for currency {Currency}" )
            elif Currency == CurrencyType.Tickets and TargetEconomyObj.tickets_bal < Amount:
                raise EconomyBalanceExceptions.InsufficientBalance( f"User {TargetObj.id} has insufficient balance for currency {Currency}" )

            await _UnsafeDecrementBalance( TargetObj, Currency, Amount )
    except AssertionError:
        raise EconomyBalanceExceptions.LockAcquisitionFailed( f"Failed to acquire lock {lock_name}" )
    except EconomyBalanceExceptions.InsufficientBalance as e:
        raise e
    except Exception as e:
        logging.error( f"services.economy.balance > DecrementTargetBalance, exception raised: {e}" )
        raise EconomyBalanceExceptions.InternalServiceError( f"Failed to decrement balance for user {TargetObj.id}" )

async def _UnsafeIncrementBalance( TargetObj : User | Group, Currency : CurrencyType, Amount : int ):
    TargetEconomyObj : UserEconomy = await GetTargetEconomyObject( TargetObj = TargetObj )

    if Currency == CurrencyType.Robux:
        TargetEconomyObj.robux_bal += Amount
    elif Currency == CurrencyType.Tickets:
        TargetEconomyObj.tickets_bal += Amount
    else:
        raise EconomyBalanceExceptions.InvalidCurrencyType( f"Invalid currency type: {Currency}" )
    
    db.session.commit()

async def _UnsafeDecrementBalance( TargetObj : User | Group, Currency : CurrencyType, Amount : int ):
    TargetEconomyObj : UserEconomy = await GetTargetEconomyObject( TargetObj = TargetObj )

    if Currency == CurrencyType.Robux:
        if TargetEconomyObj.robux_bal < Amount:
            raise EconomyBalanceExceptions.InsufficientBalance( f"User {TargetObj.id} has insufficient balance for currency {Currency}" )
        TargetEconomyObj.robux_bal -= Amount
    elif Currency == CurrencyType.Tickets:
        if TargetEconomyObj.tickets_bal < Amount:
            raise EconomyBalanceExceptions.InsufficientBalance( f"User {TargetObj.id} has insufficient balance for currency {Currency}" )
        TargetEconomyObj.tickets_bal -= Amount
    else:
        raise EconomyBalanceExceptions.InvalidCurrencyType( f"Invalid currency type: {Currency}" )
    
    db.session.commit()