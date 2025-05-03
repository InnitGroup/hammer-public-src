from quart import request, make_response, jsonify, session, Blueprint

EconomyHandler = Blueprint('economy_web_api', __name__, url_prefix='/economy')

from app.routes.web_api.economy.balance import EconomyBalanceHandler
EconomyHandler.register_blueprint( EconomyBalanceHandler, url_prefix = "/" )