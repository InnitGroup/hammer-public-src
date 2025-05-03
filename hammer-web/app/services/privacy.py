from app.services import authentication, user_relationships

from app.models.user_settings import UserSettings
from app.models.user import User
from app.enums.InventoryPrivacy import InventoryPrivacy
from app.enums.MessagePrivacy import MessagePrivacy
from app.enums.GameJoinPrivacy import GameJoinPrivacy

from app.extensions import db, redis_controller

async def get_user_settings(
    target_user : User
) -> UserSettings:
    user_settings : UserSettings | None = UserSettings.query.filter_by( user_id = target_user.id ).first()
    if user_settings is None:
        user_settings = UserSettings( user_id = target_user.id )
        db.session.add( user_settings )
        db.session.commit()
    return user_settings

async def can_view_inventory(
    target_user : User,
    viewer : User | None,
    bypass_cache : bool = False
) -> bool:
    if viewer is not None and viewer.id == target_user.id:
        return True
    async def _actual_query() -> bool:
        target_user_settings : UserSettings = await get_user_settings( target_user )
        if target_user_settings.inventory_privacy == InventoryPrivacy.Everyone:
            return True
        elif target_user_settings.inventory_privacy == InventoryPrivacy.NoOne:
            return False
        if viewer is None:
            return False
        is_viewer_friend : bool = user_relationships.get_friend_relationship( user1_id = viewer.id, user2_id = target_user.id ) is not None
        if is_viewer_friend:
            return True
        elif target_user_settings.inventory_privacy == InventoryPrivacy.FriendsOnly:
            return False
        is_viewing_followed_by_target : bool = user_relationships.get_follow_relationship( follower_id = target_user.id, followee_id = viewer.id ) is not None
        if is_viewing_followed_by_target:
            return True
        elif target_user_settings.inventory_privacy == InventoryPrivacy.FriendsandFollowing:
            return False
        is_viewer_follower : bool = user_relationships.get_follow_relationship( follower_id = viewer.id, followee_id = target_user.id ) is not None
        if is_viewer_follower:
            return True
        return False
    cache_key = f"can_view_inventory:{target_user.id}:{viewer.id if viewer is not None else 0}"
    if not bypass_cache and await redis_controller.exists( cache_key ) > 0:
        return bool( await redis_controller.get( cache_key ) )
    query_result = await _actual_query()
    await redis_controller.set( cache_key, int( query_result ), ex = 60 )
    
    return query_result

async def can_message_user(
    target_user : User,
    viewer : User | None,
    bypass_cache : bool = False
) -> bool:
    if viewer is not None and viewer.id == target_user.id:
        return True
    async def _actual_query() -> bool:
        target_user_settings : UserSettings = await get_user_settings( target_user )
        if target_user_settings.message_privacy == MessagePrivacy.Everyone:
            return True
        elif target_user_settings.message_privacy == MessagePrivacy.NoOne:
            return False
        if viewer is None:
            return False
        is_viewer_friend : bool = user_relationships.get_friend_relationship( user1_id = viewer.id, user2_id = target_user.id ) is not None
        if is_viewer_friend:
            return True
        elif target_user_settings.message_privacy == MessagePrivacy.FriendsOnly:
            return False
        is_viewing_followed_by_target : bool = user_relationships.get_follow_relationship( follower_id = target_user.id, followee_id = viewer.id ) is not None
        if is_viewing_followed_by_target:
            return True
        elif target_user_settings.message_privacy == MessagePrivacy.FriendsandFollowing:
            return False
        is_viewer_follower : bool = user_relationships.get_follow_relationship( follower_id = viewer.id, followee_id = target_user.id ) is not None
        if is_viewer_follower:
            return True
        return False
    cache_key = f"can_message_user:{target_user.id}:{viewer.id if viewer is not None else 0}"
    if not bypass_cache and await redis_controller.exists( cache_key ) > 0:
        return bool( await redis_controller.get( cache_key ) )
    query_result = await _actual_query()
    await redis_controller.set( cache_key, int( query_result ), ex = 60 )
    
    return query_result

async def can_join_game(
    target_user : User,
    viewer : User | None,
    bypass_cache : bool = False
) -> bool:
    if viewer is not None and viewer.id == target_user.id:
        return True
    async def _actual_query() -> bool:
        target_user_settings : UserSettings = await get_user_settings( target_user )
        if target_user_settings.game_join_privacy == GameJoinPrivacy.Everyone:
            return True
        elif target_user_settings.game_join_privacy == GameJoinPrivacy.NoOne:
            return False
        if viewer is None:
            return False
        is_viewer_friend : bool = user_relationships.get_friend_relationship( user1_id = viewer.id, user2_id = target_user.id ) is not None
        if is_viewer_friend:
            return True
        elif target_user_settings.game_join_privacy == GameJoinPrivacy.FriendsOnly:
            return False
        is_viewing_followed_by_target : bool = user_relationships.get_follow_relationship( follower_id = target_user.id, followee_id = viewer.id ) is not None
        if is_viewing_followed_by_target:
            return True
        elif target_user_settings.game_join_privacy == GameJoinPrivacy.FriendsandFollowing:
            return False
        is_viewer_follower : bool = user_relationships.get_follow_relationship( follower_id = viewer.id, followee_id = target_user.id ) is not None
        if is_viewer_follower:
            return True
        return False
    cache_key = f"can_join_game:{target_user.id}:{viewer.id if viewer is not None else 0}"
    if not bypass_cache and await redis_controller.exists( cache_key ) > 0:
        return bool( await redis_controller.get( cache_key ) )
    query_result = await _actual_query()
    await redis_controller.set( cache_key, int( query_result ), ex = 60 )
    
    return query_result