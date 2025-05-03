import random
import string
from datetime import datetime, timedelta

from app.models.invite_keys import InviteKey
from app.models.user import User
from app.enums.WebsiteFeature import WebsiteFeature
from app.enums.AccountStatus import AccountStatus

from app.extensions import db
from app.services import authentication
from app.util.websiteFeatures import GetWebsiteFeature

class InviteKeyCreationError( Exception ):
    pass
class InviteKeyCreationFeatureDisabled( InviteKeyCreationError ):
    pass
class TooManyUnusedInviteKeys( InviteKeyCreationError ):
    pass
class InviteKeyCreationCooldown( InviteKeyCreationError ):
    pass

async def create_invite_key(
    creator_user : User | None,
    bypass_unused_key_check : bool = False,
    bypass_key_creation_cooldown : bool = False,
    bypass_feature_lock : bool = False
) -> InviteKey:
    if not bypass_feature_lock and not await GetWebsiteFeature( WebsiteFeature.InviteKeyCreation ):
        raise InviteKeyCreationFeatureDisabled("Invite key creation is disabled")
    
    if creator_user is not None:
        if not bypass_unused_key_check:
            total_unused_keys = InviteKey.query.filter_by(
                creator_user_id = creator_user.id,
                redeemed_by_user_id = None
            ).count()
            if total_unused_keys >= 5:
                raise TooManyUnusedInviteKeys("You have too many unused invite keys")
        if not bypass_key_creation_cooldown:
            keys_created_past_day = InviteKey.query.filter_by(
                creator_user_id = creator_user.id
            ).filter(
                InviteKey.created_at >= datetime.utcnow() - timedelta( days = 1 )
            ).count()
            if keys_created_past_day >= 5:
                raise InviteKeyCreationCooldown("You have created too many invite keys in the past 24 hours")
    
    generated_key = 'hammer-' + ''.join(random.choices('abcdef' + string.digits, k=24))
    new_invite_key = InviteKey(
        creator_user_id = creator_user.id if creator_user is not None else None,
        key_string = generated_key
    )
    db.session.add( new_invite_key )
    db.session.commit()
    
    return new_invite_key

async def is_invite_key_valid(
    key_string : str
) -> bool:
    invite_key : InviteKey | None = InviteKey.query.filter_by( key_string = key_string ).first()
    if invite_key is None:
        return False
    creator_user : User | None = authentication.get_user_by_id( invite_key.creator_user_id )
    if creator_user.account_status != AccountStatus.Active:
        return False
    return invite_key.redeemed_by_user_id is None

async def redeem_invite_key(
    key_string : str,
    redeemer_user : User
) -> bool:
    invite_key : InviteKey | None = InviteKey.query.filter_by( key_string = key_string ).first()
    if invite_key is None:
        return False
    if invite_key.redeemed_by_user_id is not None:
        return False
    invite_key.redeemed_by_user_id = redeemer_user.id
    db.session.commit()
    return True