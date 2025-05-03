from quart import request, make_response, Blueprint, jsonify, redirect

from app.services import authentication, versioncompatibility
from app.models.version_compatiblity_group import VersionCompatibilityGroup

VersionCompatibilityRoute = Blueprint('versioncompatibility', __name__, url_prefix='/', subdomain = "versioncompatibility.api")

@VersionCompatibilityRoute.route('/GetAllowedMD5Hashes/', methods=['GET'])
async def _get_allowed_md5_hashes():
    requestApiKey = request.args.get(
        key = "apiKey",
        default = None,
        type = str
    )
    if requestApiKey is None or len(requestApiKey) > 255:
        return await make_response(
            jsonify({ "status": 0, "message": "Invalid parameter" }),
            400
        )
    
    parent_group : VersionCompatibilityGroup | None = await versioncompatibility.get_group_by_apikey( api_key = requestApiKey )
    if parent_group is None:
        return await make_response(
            jsonify({ "status": 0, "message": "Unknown API Key" }),
            404
        )
    
    key_list = await versioncompatibility.generate_group_keys( parent_group = parent_group )
    return await make_response(
        jsonify({
            "data": key_list
        }),
        200
    )