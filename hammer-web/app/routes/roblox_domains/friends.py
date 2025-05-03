"""
    friends.roblox.com
"""
from datetime import datetime, timedelta
from quart import request, make_response, jsonify, Blueprint
from app.models.user import User
from app.models.friend_request import FriendRequest
from app.models.follow_relationship import FollowRelationship
from app.enums.AccountStatus import AccountStatus
from app.services import user_relationships, authentication, cursor
from app.extensions import remote_address_limiter
from app.util.obj_builder import build_datetime_obj

FriendsRoute = Blueprint( "friends_roblox", __name__ , url_prefix = "/", subdomain = "friends" )

@FriendsRoute.route("/v1/my/friends/count", methods=["GET"])
@authentication.require_authentication
@remote_address_limiter.limit( "100/minute" )
async def _get_authenticated_user_friend_count():
    authenticated_user : User = await authentication.GetCurrentUser()
    user_friend_count : int = await user_relationships.get_user_friend_count( authenticated_user )
    return jsonify({
        "count": user_friend_count
    })
    
@FriendsRoute.route("/v1/my/friends/requests", methods=["GET"])
@authentication.require_authentication
@remote_address_limiter.limit( "100/minute" )
async def _get_authenticated_user_paged_friend_requests():
    authenticated_user : User = await authentication.GetCurrentUser()
    page_cursor : str | None = request.args.get( "cursor", type = str, default = None )
    cursor_discriminator : str = f"friend_requests:self:{authenticated_user.id}"
    if page_cursor is not None:
        try:
            page_cursor_obj : cursor.ExclusiveStartKeyCursor | cursor.CursorBase = cursor.parse_cursor( page_cursor, cursor_discriminator )
            if not isinstance( page_cursor_obj, cursor.ExclusiveStartKeyCursor ):
                raise ValueError()
        except cursor.InvalidCursorException as e:
            return make_response( jsonify({ "errors": [ { "code": 4, "message": f"{str(e)}" } ] }), 400 )
    else:
        cursor_page_size : int = request.args.get( "limit", default = 10, type = int )
        sorting_order : str = request.args.get( "sortOrder", default = "Asc", type = str )
        try:
            assert cursor_page_size in [ 10, 18, 25, 50, 100 ], "Invalid limit"
            assert sorting_order.lower() in [ "asc", "desc" ], "Invalid sortOrder"
        except AssertionError as e:
            return make_response( jsonify({ "errors": [ { "code": 6, "message": str(e) } ] }), 400 )
        sort_order_enum : cursor.SortOrder = cursor.SortOrder.Ascending if sorting_order.lower() == "asc" else cursor.SortOrder.Descending
        page_cursor_obj = cursor.ExclusiveStartKeyCursor(
            discriminator = cursor_discriminator,
            key = 1,
            count = cursor_page_size,
            sort_order = sort_order_enum,
            paging_direction = cursor.CursorPagingDirection.Forward
        )
    friend_req_query = FriendRequest.query.filter_by(
        receiver_id = authenticated_user.id 
    ).order_by( 
        FriendRequest.created_at.desc() if page_cursor_obj.sort_order == cursor.SortOrder.Descending else FriendRequest.created_at.asc() 
    ).paginate( page = page_cursor_obj.key, per_page = page_cursor_obj.count, error_out = False )
    
    response_data : list[dict] = []
    for friend_req in friend_req_query.items:
        friend_req : FriendRequest
        sender_user : User = authentication.get_user_by_id( friend_req.sender_id )
        if sender_user is None or sender_user.account_status == AccountStatus.GDPR_Deleted:
            continue
        response_data.append({
            "friendRequest": {
                "sentAt" : build_datetime_obj( friend_req.created_at ),
                "senderId" : sender_user.id,
                "sourceUniverseId" : 0,
                "originSourceType": "Unknown",
                "contactName": None,
                "senderNickname": ""
            },
            "mutualFriendsList": [],
            "hasVerifiedBadge": False,
            "description": sender_user.description,
            "isBanned": sender_user.account_status != AccountStatus.Active,
            "externalAppDisplayName": None,
            "id": sender_user.id,
            "name": sender_user.username,
            "displayName": sender_user.username
        })
        
    next_cursor : str | None = cursor.fork_cursor( page_cursor_obj, friend_req_query.next_num, cursor.CursorPagingDirection.Forward ) if friend_req_query.has_next else None
    previou_cursor : str | None = cursor.fork_cursor( page_cursor_obj, friend_req_query.prev_num, cursor.CursorPagingDirection.Backward ) if friend_req_query.has_prev else None
    
    return jsonify({
        "previousPageCursor": previou_cursor,
        "nextPageCursor": next_cursor,
        "data": response_data
    })
    
@FriendsRoute.route("/v1/user/friend-requests/count", methods=["GET"])
@authentication.require_authentication
@remote_address_limiter.limit( "100/minute" )
async def _get_authenticated_user_friend_request_count():
    authenticated_user : User = await authentication.GetCurrentUser()
    friend_req_count : int = FriendRequest.query.filter_by( receiver_id = authenticated_user.id ).count()
    return jsonify({
        "count": friend_req_count
    })
    
@FriendsRoute.route("/v1/users/<int:user_id>/friends", methods=["GET"])
@remote_address_limiter.limit( "60/minute" )
async def _get_user_friends_list( user_id : int ):
    requested_user : User = authentication.get_user_by_id( user_id )
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "The target user is invalid or does not exist." } ] }), 400 )
    userSort = request.args.get( "sortOrder", type = int, default = 0 )
    try:
        assert userSort in [ 0, 1 ], "Invalid sortOrder"
    except AssertionError as e:
        return make_response( jsonify({ "errors": [ { "code": 5, "message": str(e) } ] }), 400 )
    user_friends : list[User] = await user_relationships.get_user_friends(
        user_obj = requested_user,
        order_by_last_online = userSort == 1,
        limit = 200
    )
    response_data : list[dict] = []
    for user_friend_obj in user_friends:
        user_friend_obj : User
        if user_friend_obj.account_status == AccountStatus.GDPR_Deleted:
            continue
        response_data.append({
            "isOnline": user_friend_obj.lastonline_at > datetime.utcnow() - timedelta( minutes = 1 ),
            "isDeleted": user_friend_obj.account_status == AccountStatus.Deleted,
            "hasVerifiedBadge": False,
            "description": user_friend_obj.description,
            "created": build_datetime_obj( user_friend_obj.created_at ),
            "isBanned": user_friend_obj.account_status != AccountStatus.Active,
            "id": user_friend_obj.id,
            "name": user_friend_obj.username,
            "displayName": user_friend_obj.username
        })
    return jsonify({
        "data": response_data
    })
    
@FriendsRoute.route("/v1/users/<int:user_id>/friends/count", methods=["GET"])
@remote_address_limiter.limit( "60/minute" )
async def _get_user_friend_count( user_id : int ):
    requested_user : User = authentication.get_user_by_id( user_id )
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "The target user is invalid or does not exist." } ] }), 400 )
    user_friend_count : int = await user_relationships.get_user_friend_count( requested_user )
    return jsonify({
        "count": user_friend_count
    })
    
@FriendsRoute.route("/v1/users/<int:user_id>/followings", methods=["GET"])
@FriendsRoute.route("/v1/users/<int:user_id>/followers", methods=["GET"])
@remote_address_limiter.limit( "60/minute" )
async def _get_user_followers_list( user_id : int ):
    """
        Both followers and followings are basically the same thing,
        just the direction of the relationship is different.
    """
    
    is_followers_request : bool = request.path.endswith( "followers" )

    requested_user : User = authentication.get_user_by_id( user_id )
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "The target user is invalid or does not exist." } ] }), 400 )
    page_cursor : str | None = request.args.get( "cursor", type = str, default = None )
    cursor_discriminator : str = f"followers:{requested_user.id}" if is_followers_request else f"followings:{requested_user.id}"
    if page_cursor is not None:
        try:
            page_cursor_obj : cursor.ExclusiveStartKeyCursor | cursor.CursorBase = cursor.parse_cursor( page_cursor, cursor_discriminator )
            if not isinstance( page_cursor_obj, cursor.ExclusiveStartKeyCursor ):
                raise ValueError()
        except cursor.InvalidCursorException as e:
            return make_response( jsonify({ "errors": [ { "code": 4, "message": f"{str(e)}" } ] }), 400 )
    else:
        cursor_page_size : int = request.args.get( "limit", default = 10, type = int )
        sorting_order : str = request.args.get( "sortOrder", default = "Asc", type = str )
        try:
            assert cursor_page_size in [ 10, 18, 25, 50, 100 ], "Invalid limit"
            assert sorting_order.lower() in [ "asc", "desc" ], "Invalid sortOrder"
        except AssertionError as e:
            return make_response( jsonify({ "errors": [ { "code": 6, "message": str(e) } ] }), 400 )
        sort_order_enum : cursor.SortOrder = cursor.SortOrder.Ascending if sorting_order.lower() == "asc" else cursor.SortOrder.Descending
        page_cursor_obj = cursor.ExclusiveStartKeyCursor(
            discriminator = cursor_discriminator,
            key = 1,
            count = cursor_page_size,
            sort_order = sort_order_enum,
            paging_direction = cursor.CursorPagingDirection.Forward
        )
    
    if is_followers_request:
        follow_relationship_query = FollowRelationship.query.filter_by(
            following_id = requested_user.id
        )
    else:
        follow_relationship_query = FollowRelationship.query.filter_by(
            follower_id = requested_user.id
        )
    
    follow_relationship_query = follow_relationship_query.order_by(
        FollowRelationship.created_at.desc() if page_cursor_obj.sort_order == cursor.SortOrder.Descending else FollowRelationship.created_at.asc()
    ).paginate( page = page_cursor_obj.key, per_page = page_cursor_obj.count, error_out = False )
    
    response_data : list[dict] = []
    for follow_rel in follow_relationship_query.items:
        follow_rel : FollowRelationship
        follower_user : User = authentication.get_user_by_id( follow_rel.follower_id )
        if follower_user is None or follower_user.account_status == AccountStatus.GDPR_Deleted:
            continue
        response_data.append({
            "isOnline": follower_user.lastonline_at > datetime.utcnow() - timedelta( minutes = 1 ),
            "isDeleted": follower_user.account_status == AccountStatus.Deleted,
            "hasVerifiedBadge": False,
            "description": follower_user.description,
            "created": build_datetime_obj( follower_user.created_at ),
            "isBanned": follower_user.account_status != AccountStatus.Active,
            "id": follower_user.id,
            "name": follower_user.username,
            "displayName": follower_user.username
        })
    
    next_cursor : str | None = cursor.fork_cursor( page_cursor_obj, follow_relationship_query.next_num, cursor.CursorPagingDirection.Forward ) if follow_relationship_query.has_next else None
    previou_cursor : str | None = cursor.fork_cursor( page_cursor_obj, follow_relationship_query.prev_num, cursor.CursorPagingDirection.Backward ) if follow_relationship_query.has_prev else None
    
    return jsonify({
        "previousPageCursor": previou_cursor,
        "nextPageCursor": next_cursor,
        "data": response_data
    })
    
@FriendsRoute.route("/v1/users/<int:user_id>/followers/count", methods=["GET"])
@remote_address_limiter.limit( "60/minute" )
async def _get_user_follower_count( user_id : int ):
    requested_user : User = authentication.get_user_by_id( user_id )
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "The target user is invalid or does not exist." } ] }), 400 )
    follower_count : int = FollowRelationship.query.filter_by( following_id = requested_user.id ).count()
    return jsonify({
        "count": follower_count
    })
    
@FriendsRoute.route("/v1/users/<int:user_id>/followings/count", methods=["GET"])
@remote_address_limiter.limit( "60/minute" )
async def _get_user_following_count( user_id : int ):
    requested_user : User = authentication.get_user_by_id( user_id )
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "The target user is invalid or does not exist." } ] }), 400 )
    following_count : int = FollowRelationship.query.filter_by( follower_id = requested_user.id ).count()
    return jsonify({
        "count": following_count
    })
    
@FriendsRoute.route("/v1/user/following-exists", methods=["POST"])
@authentication.require_authentication
@remote_address_limiter.limit( "60/minute" )
async def _check_following_exists():
    authenticated_user : User = await authentication.GetCurrentUser()
    payload_data = await request.json
    try:
        assert "targetUserIds" in payload_data, "Missing targetUserIds"
        assert type( payload_data["targetUserIds"] ) == list, "targetUserIds must be a list"
    except AssertionError as e:
        return make_response( jsonify({ "errors": [ { "code": 0, "message": str(e) } ] }), 400 )
    
    requested_user_ids : list[int] = payload_data["targetUserIds"]
    if len( requested_user_ids ) > 100:
        return make_response( jsonify({ "errors": [ { "code": 2, "message": "Too many targetUserIds" } ] }), 400 )
    response_data : list[dict] = []
    
    for requested_user_id in requested_user_ids:
        if type( requested_user_id ) != int:
            return make_response( jsonify({ "errors": [ { "code": 1, "message": "Invalid targetUserId" } ] }), 400 )
        if requested_user_id == authenticated_user.id:
            continue
        requested_user : User = authentication.get_user_by_id( requested_user_id )
        if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
            return make_response( jsonify({ "errors": [ { "code": 1, "message": "Invalid targetUserId" } ] }), 400 )
        response_data.append({
            "isFollowing": user_relationships.get_follow_relationship( authenticated_user.id, requested_user_id ) is not None,
            "isFollowed": user_relationships.get_follow_relationship( requested_user_id, authenticated_user.id ) is not None,
            "userId": requested_user_id
        })
    
    return jsonify({
        "followings": response_data
    })