from quart import request, make_response, jsonify, session, Blueprint

AccountSettingsHandler = Blueprint('accountsettings_web_api', __name__, url_prefix='/account_settings')
