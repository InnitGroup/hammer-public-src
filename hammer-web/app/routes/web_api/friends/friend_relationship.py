from quart import request, make_response, jsonify, Blueprint

from app.extensions import user_limiter, db, remote_address_limiter
from app.services import user_relationships, authentication
from app.models.friend_relationship import FriendRelationship
from app.models.follow_relationship import FollowRelationship
from app.models.friend_request import FriendRequest
from app.models.user import User
from app.enums.AccountStatus import AccountStatus

FriendsRelationshipHandler = Blueprint('friends_relationship', __name__, url_prefix='/')

@FriendsRelationshipHandler.route("/users/friend-status", methods = [ "GET" ])
@authentication.require_authentication
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code == 200 )
async def _get_friend_status():
    authenticated_user : User = await authentication.GetCurrentUser()
    target_user_id : int | None = request.args.get(
        key = "userId",
        default = None,
        type = int
    )
    if target_user_id is None:
        return await make_response( jsonify({ "status": 0, "message": "Missing parameter"}), 400)
    if target_user_id <= 0:
        return await make_response( jsonify({ "status": 1, "message": "Invalid parameter"}), 400)
    target_user_obj : User | None = User.query.filter_by( id = target_user_id ).first()
    if target_user_obj is None:
        return await make_response( jsonify({ "status": 2, "message": "User does not exist"}), 400)
    if target_user_obj.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "status": 2, "message": "User does not exist"}), 400)
    if user_relationships.get_friend_relationship( authenticated_user.id, target_user_obj.id ) is not None:
        return await make_response( jsonify({ "status": 3, "relationship_status": "Friends"}), 200)
    if user_relationships.get_friend_request( authenticated_user.id, target_user_obj.id ) is not None:
        return await make_response( jsonify({ "status": 4, "relationship_status": "RequestSentPending"}), 200)
    if user_relationships.get_friend_request( target_user_obj.id, authenticated_user.id ) is not None:
        return await make_response( jsonify({ "status": 5, "relationship_status": "RequestReceivedPending"}), 200)
    return await make_response( jsonify({ "status": 6, "relationship_status": "NoRelationship"}), 200)

@FriendsRelationshipHandler.route("/users/request-friendship", methods = [ "POST" ])
@remote_address_limiter.limit("5/minute", deduct_when = lambda response: response.status_code == 200 )
@authentication.require_authentication
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code != 200 )
@user_limiter.limit("5/minute", deduct_when = lambda response: response.status_code == 200 )
async def _request_friendship():
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    json_payload = await request.json
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        assert "target_user_id" in json_payload, "Target user ID is required"
        assert isinstance( json_payload["target_user_id"], int), "Target user ID must be an integer"
        assert json_payload["target_user_id"] > 0, "Target user ID must be greater than 0"
        target_user_obj : User | None = User.query.filter_by( id = json_payload["target_user_id"] ).first()
        assert target_user_obj is not None, "Target user does not exist"
        assert target_user_obj.id != authenticated_user.id, "Cannot send friend request to self"
        assert target_user_obj.account_status == AccountStatus.Active, "Target user is not active"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 0, "message": f"Validation failed, {str(e)}"}), 400)

    try:
        func_results : FriendRequest | FriendRelationship = await user_relationships.send_friend_request( authenticated_user.id, target_user_obj.id )
    except user_relationships.Exceptions.UserAlreadySentFriendRequest:
        return await make_response( jsonify({ "status": 1, "message": "You have already sent a friend request to this user"}), 400)
    except user_relationships.Exceptions.UserAlreadyFriends:
        return await make_response( jsonify({ "status": 2, "message": "You are already friends with this user"}), 400)
    except user_relationships.Exceptions.ExceededFriendLimit:
        return await make_response( jsonify({ "status": 4, "message": "Either user has already reached their friend limit of 200"}), 400)
    return await make_response( jsonify({ "status": 3, "message": "Friend request sent"}), 200)

@FriendsRelationshipHandler.route("/users/unfriend", methods = [ "POST" ])
@authentication.require_authentication
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code != 200 )
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code == 200 )
async def _unfriend_user():
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    json_payload = await request.json
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        assert "target_user_id" in json_payload, "Target user ID is required"
        assert isinstance( json_payload["target_user_id"], int), "Target user ID must be an integer"
        assert json_payload["target_user_id"] > 0, "Target user ID must be greater than 0"
        target_user_obj : User | None = User.query.filter_by( id = json_payload["target_user_id"] ).first()
        assert target_user_obj is not None, "Target user does not exist"
        assert target_user_obj.id != authenticated_user.id, "Cannot unfriend self"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 0, "message": f"Validation failed, {str(e)}"}), 400)
    
    friend_relationship_obj : FriendRelationship | None = user_relationships.get_friend_relationship( authenticated_user.id, target_user_obj.id )
    if friend_relationship_obj is None:
        return await make_response( jsonify({ "status": 1, "message": "User is not currently friends with the target"}), 400)
    db.session.delete( friend_relationship_obj )
    db.session.commit()
    
    return await make_response( jsonify({ "status": 2, "message": "Unfriended"}), 200)

@FriendsRelationshipHandler.route("/users/revoke-friend-request", methods = [ "POST" ])
@authentication.require_authentication
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code == 200 )
async def _revoke_friend_request():
    if not request.is_json:
        return await make_response( jsonify({ "status": 0, "message": "Invalid request"}), 400)
    json_payload = await request.json
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        assert "target_user_id" in json_payload, "Target user ID is required"
        assert isinstance( json_payload["target_user_id"], int), "Target user ID must be an integer"
        assert json_payload["target_user_id"] > 0, "Target user ID must be greater than 0"
        target_user_obj : User | None = User.query.filter_by( id = json_payload["target_user_id"] ).first()
        assert target_user_obj is not None, "Target user does not exist"
        assert target_user_obj.id != authenticated_user.id, "Target cannot be self"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 0, "message": f"Validation failed, {str(e)}"}), 400)
    
    friend_request_obj : FriendRequest = user_relationships.get_friend_request( authenticated_user.id, target_user_obj.id )
    if friend_request_obj is None:
        return await make_response( jsonify({ "status": 1, "message": "No friend request found"}), 400)
    db.session.delete( friend_request_obj )
    db.session.commit()
    
    return await make_response( jsonify({ "status": 2, "message": "Friend request revoked"}), 200)