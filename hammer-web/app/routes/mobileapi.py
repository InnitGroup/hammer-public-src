from quart import Blueprint, render_template, jsonify, request

MobileAPIRoute = Blueprint('mobileapi', __name__, url_prefix='/mobileapi', subdomain = "www")

@MobileAPIRoute.route('/check-app-version', methods=['GET'])
async def _check_app_version():
    return jsonify({"data":{"UpgradeAction":"None"}})