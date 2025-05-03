from quart import Blueprint, request, jsonify, make_response, abort, g

from app.extensions import remote_address_limiter
from app.services import authentication, groups
from app.models.user import User
from app.models.groups import Group, GroupMember
from app.enums.AccountStatus import AccountStatus

GroupsRoute = Blueprint("groups_roblox", __name__, url_prefix="/", subdomain="groups")

@GroupsRoute.route("/v2/users/<int:userId>/groups/roles", methods = ["GET"])
@remote_address_limiter.limit( "100/minute", deduct_when = lambda response: response.status != 200 )
@remote_address_limiter.limit( "100/minute", deduct_when = lambda response: response.status == 200 )
async def _get_user_group_roles( userId : int ):
    target_user : User | None = User.query.filter_by( id = userId ).first()
    if target_user is None or target_user.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "errors": [ { "code": 3, "message": "The user is invalid or does not exist." } ] }), 400 )
    user_group_roles : list[groups.UserGroupEntry] = groups.GetUserGroups( target_user )
    formatted_data = []
    for group_role in user_group_roles:
        formatted_data.append({
            "group": {
                "id": group_role.group_id,
                "name": group_role.group_name,
                "memberCount": group_role.group_member_count,
                "hasVerifiedBadge": False
            },
            "role": {
                "id": group_role.user_roleset.id,
                "name": group_role.user_roleset.name,
                "rank": group_role.user_roleset.rank,
            }
        })
    
    return await make_response( jsonify({
        "data": formatted_data
    }), 200 )