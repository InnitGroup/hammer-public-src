from quart import Blueprint, request, jsonify, make_response, abort
from app.services import text_moderation, authentication
from app.extensions import csrf_protect

TextFilterRoute = Blueprint("textfilter_roblox", __name__, url_prefix="/", subdomain="textfilter")

@TextFilterRoute.route("/v2/moderation/textfilter", methods = ["POST"])
@csrf_protect.exempt
async def _internal_text_filter():
    if await authentication.GetCurrentGameServer() is None:
        return make_response( jsonify({ "errors": [ { "code": 1, "message": "Unauthorized" } ] }), 401 )
    payload_data = await request.form
    requested_filter_text : str = payload_data.get( "text", default = "", type = str )
    filtered_text : str = text_moderation.filter_text( requested_filter_text )
    return jsonify({
        "success": True,
        "message": "",
        "data": {
            "AgeUnder13": filtered_text,
            "Age13OrOver": filtered_text
        }
    })