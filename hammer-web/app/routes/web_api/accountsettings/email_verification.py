from quart import request, make_response, jsonify, session, Blueprint
from app.services import authentication
from app.models.user_economy import UserEconomy
from app.models.user import User
from app.models.user_email import UserEmail

AccountSettingsEmailVerificationHandler = Blueprint('account_settings_email', __name__, url_prefix='/email')