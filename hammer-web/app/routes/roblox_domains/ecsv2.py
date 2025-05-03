"""
    ecsv2.roblox.com
"""

from quart import Blueprint, request, jsonify, make_response
from app.extensions import csrf_protect

ECSV2Route = Blueprint('ecsv2_roblox', __name__, url_prefix='/', subdomain='ecsv2')

@ECSV2Route.route('/client/pbe', methods = ["POST"])
@csrf_protect.exempt
async def _client_pbe():
    return await make_response(
        "",
        200
   )

@ECSV2Route.route("/mobile/pbe", methods = ["POST"])
@csrf_protect.exempt
async def _mobile_pbe():
    return await make_response(
        "",
        200
    )