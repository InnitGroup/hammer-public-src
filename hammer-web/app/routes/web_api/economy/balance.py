from quart import request, make_response, jsonify, session, Blueprint
from app.services import authentication
from app.services.economy import balance as economy_balance_service
from app.models.user_economy import UserEconomy
from app.models.user import User

EconomyBalanceHandler = Blueprint('economy_balance', __name__, url_prefix='/balance')

@EconomyBalanceHandler.route("/balance", methods = [ "GET" ])
@authentication.require_authentication
async def _get_user_balance():
    userObj : User = await authentication.GetCurrentUser()
    balance : UserEconomy = await economy_balance_service.GetTargetEconomyObject( userObj )
    return await make_response( jsonify({ "status": 1, "data": {
        "robux_bal": balance.robux_bal,
        "tickets_bal": balance.tickets_bal
    }}), 200)