import logging
from quart import Blueprint, render_template, make_response, jsonify, request, redirect, abort
from datetime import datetime, timedelta
from app.models.user import User
from app.models.user_avatar_item import UserAvatarItem
from app.services import authentication, avatar, user_relationships, user_presence
from app.enums.UserPresence import UserPresence

UserProfileHandler = Blueprint( "user_profile_handler", __name__, url_prefix = "/", subdomain = "www" )

@UserProfileHandler.route( "/users/<int:userId>/profile", methods = [ "GET" ] )
@authentication.require_authentication
async def _profile_page( userId : int ):
    TargetUserObj : User | None = User.query.filter_by( id = userId ).first()
    if TargetUserObj is None:
        abort( 404 )
    WearingItems : list[UserAvatarItem] = await avatar.get_user_avatar_items( user_obj = TargetUserObj )
    user_friends : list[User] = await user_relationships.get_user_friends(
        user_obj = TargetUserObj,
        order_by_last_online = True,
        limit = 8
    )
    UserFriends : list[dict] = []
    for friend_user_obj in user_friends:
        friend_user_presence : UserPresence = await user_presence.get_user_presence( friend_user_obj )
        UserFriends.append({
            "id" : friend_user_obj.id,
            "username" : friend_user_obj.username,
            "is_online" : friend_user_presence != UserPresence.Offline,
            "is_ingame" : friend_user_presence == UserPresence.InGame
        })
    FriendCount : int = await user_relationships.get_user_friend_count( user_obj = TargetUserObj )
    TargetUserPresence : UserPresence = await user_presence.get_user_presence( TargetUserObj )
    return await render_template(
        "profile/user_profile.html", 
        userObj = TargetUserObj,
        is_user_online = TargetUserPresence != UserPresence.Offline,
        is_user_ingame = TargetUserPresence == UserPresence.InGame,
        user_join_date = TargetUserObj.created_at.strftime("%d/%m/%Y"),
        
        WearingItems = WearingItems, 
        UserFriends = UserFriends, 
        FriendCount = FriendCount
    )