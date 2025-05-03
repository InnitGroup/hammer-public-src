import random, string

from quart import Blueprint, request, jsonify, make_response
from app.services import authentication
from app.extensions import redis_controller, user_limiter, remote_address_limiter, get_remote_address

AuthenticationTicketRoute = Blueprint('authentication_ticket', __name__, url_prefix='/')

@AuthenticationTicketRoute.route("/create-authentication-ticket", methods=["POST"])
@remote_address_limiter.limit("20/minute", deduct_when=lambda response: response.status_code == 200)
@authentication.require_authentication
@user_limiter.limit("20/minute", deduct_when=lambda response: response.status_code == 200)
async def _create_authentication_ticket():
    authenticated_user = await authentication.GetCurrentUser()
    ticket = ''.join(random.choices(string.ascii_uppercase + string.digits, k=64))
    requesting_address = get_remote_address()
    await redis_controller.set( f"auth_ticket:{ticket}:{requesting_address}", str(authenticated_user.id), 60 * 3 )
    
    return await make_response( jsonify({ "status": 0, "ticket": ticket }), 200)