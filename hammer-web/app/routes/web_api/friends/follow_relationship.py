from quart import request, make_response, jsonify, Blueprint

from app.services import user_relationships, authentication
from app.extensions import user_limiter, remote_address_limiter, db

from app.models.user import User
from app.models.follow_relationship import FollowRelationship
from app.enums.AccountStatus import AccountStatus

FollowRelationshipHandler = Blueprint('follow_relationship', __name__, url_prefix='/')

@FollowRelationshipHandler.route("/users/follow-status", methods = [ "GET" ])
@authentication.require_authentication
@user_limiter.limit("30/minute", deduct_when = lambda response: response.status_code == 200 )
async def _get_follow_status():
    authenticated_user = await authentication.GetCurrentUser()
    follower_user_id = request.args.get(
        key = "followerUserId",
        default = None,
        type = int
    )
    target_user_id = request.args.get(
        key = "targetUserId",
        default = None,
        type = int
    )
    if target_user_id is None or follower_user_id is None:
        return await make_response( jsonify({ "status": 0, "message": "Missing parameter"}), 400)
    if target_user_id <= 0 or follower_user_id <= 0:
        return await make_response( jsonify({ "status": 1, "message": "Invalid parameter"}), 400)
    if target_user_id != authenticated_user.id and follower_user_id != authenticated_user.id:
        return await make_response( jsonify({ "status": 2, "message": "Unauthorized"}), 403)
    
    if target_user_id == follower_user_id:
        target_user_obj : User | None = User.query.filter_by( id = target_user_id ).first()
        if target_user_obj is None:
            return await make_response( jsonify({ "status": 2, "message": "Target User does not exist"}), 400)
        if target_user_obj.account_status == AccountStatus.GDPR_Deleted:
            return await make_response( jsonify({ "status": 2, "message": "Target User does not exist"}), 400)
    else:
        follower_user_obj : User | None = User.query.filter_by( id = follower_user_id ).first()
        if follower_user_obj is None:
            return await make_response( jsonify({ "status": 2, "message": "Follower User does not exist"}), 400)
        if follower_user_obj.account_status == AccountStatus.GDPR_Deleted:
            return await make_response( jsonify({ "status": 2, "message": "Follower User does not exist"}), 400)
    
    if user_relationships.get_follow_relationship( follower_user_id, target_user_id ) is not None:
        return await make_response( jsonify({ "status": 3, "relationship_status": "Following"}), 200)
    return await make_response( jsonify({ "status": 4, "relationship_status": "NotFollowing"}), 200)

@FollowRelationshipHandler.route("/users/follow", methods = [ "POST" ])
@remote_address_limiter.limit("20/minute", deduct_when = lambda response: response.status_code != 200 )
@remote_address_limiter.limit("3/minute", deduct_when = lambda response: response.status_code == 200 )
@authentication.require_authentication
@user_limiter.limit("3/minute", deduct_when = lambda response: response.status_code == 200 )
async def _follow_user():
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
        assert target_user_obj.id != authenticated_user.id, "Cannot follow self"
        assert target_user_obj.account_status == AccountStatus.Active, "Target user is not active"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 0, "message": f"Validation failed, {str(e)}"}), 400)
    
    if user_relationships.get_follow_relationship( authenticated_user.id, target_user_obj.id ) is not None:
        return await make_response( jsonify({ "status": 1, "message": "Already following user"}), 200)
    
    await user_relationships.create_follow_relationship( authenticated_user.id, target_user_obj.id )
    return await make_response( jsonify({ "status": 2, "message": "Successfully followed user"}), 200)

@FollowRelationshipHandler.route("/users/unfollow", methods = [ "POST" ])
@authentication.require_authentication
@user_limiter.limit("20/minute", deduct_when = lambda response: response.status_code == 200 )
async def _unfollow_user():
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
        assert target_user_obj.id != authenticated_user.id, "Cannot unfollow self"
    except AssertionError as e:
        return await make_response( jsonify({ "status": 0, "message": f"Validation failed, {str(e)}"}), 400)
    
    follow_relationship : FollowRelationship | None = user_relationships.get_follow_relationship( authenticated_user.id, target_user_obj.id )
    if follow_relationship is None:
        return await make_response( jsonify({ "status": 1, "message": "Not following user"}), 200)
    
    db.session.delete( follow_relationship )
    db.session.commit()
    return await make_response( jsonify({ "status": 2, "message": "Successfully unfollowed user"}), 200)