"""
    presence.roblox.com
"""
from quart import Blueprint, request, jsonify

from app.services import authentication, user_presence, privacy
from app.enums.UserPresence import UserPresence
from app.enums.AccountStatus import AccountStatus
from app.models.user import User

from app.extensions import remote_address_limiter
from app.util.obj_builder import build_datetime_obj

PresenceAPIRoute = Blueprint('presence_roblox', __name__, url_prefix='/', subdomain='presence')

@PresenceAPIRoute.route("/v1/presence/users", methods=["POST"])
@remote_address_limiter.limit("40/minute", deduct_when=lambda response: response.status_code == 200)
async def _batch_fetch_user_presnece():
    try:
        assert request.is_json, "Invalid request"
        json_data = await request.json
        assert isinstance(json_data, dict), "Invalid request"
        assert "userIds" in json_data, "UserIds is required"
        assert isinstance(json_data["userIds"], list), "UserIds must be a list"
        assert len(json_data["userIds"]) > 0, "UserIds must not be empty"
        assert len(json_data["userIds"]) <= 50, "UserIds must not exceed 50"
    except AssertionError as e:
        return jsonify({ "errors": [ { "code": 0, "message": str(e) } ] }), 400
    
    authenticated_user : User | None = await authentication.GetCurrentUser()
    
    requested_user_ids = json_data["userIds"]
    processed_users : list[int] = []
    response_data : list[dict] = []
    
    for user_id in requested_user_ids:
        if user_id in processed_users:
            continue
        user_obj : User | None = authentication.get_user_by_id(user_id, return_none_on_deleted=True)
        if user_obj is None or user_obj.account_status == AccountStatus.GDPR_Deleted:
            return jsonify({ "errors": [ { "code": 1, "message": "Invalid User." } ] }), 400
        user_presence_obj : UserPresence = await user_presence.get_user_presence(user_obj)
        can_requester_view_game_location : bool = await privacy.can_join_game( target_user = user_obj, viewer = authenticated_user )
        if can_requester_view_game_location:
            user_game_location : user_presence.UserGameLocation | None = await user_presence.get_user_game_location(user_obj)
        else:
            user_game_location = None
        
        response_data.append({
            "userPresenceType": user_presence_obj.value,
            "lastLocation": user_game_location.universe.name if user_game_location is not None else "Website",
            "placeId": user_game_location.place.place_id if user_game_location is not None else None,
            "rootPlaceId": user_game_location.universe.root_place_id if user_game_location is not None else None,
            "gameId": str( user_game_location.place_server.server_uuid ) if user_game_location is not None else None,
            "universeId": user_game_location.universe.id if user_game_location is not None else None,
            "userId": user_obj.id,
            "lastOnline": build_datetime_obj(user_obj.lastonline_at)
        })
        processed_users.append(user_id)
    
    return jsonify({ "userPresences": response_data }), 200