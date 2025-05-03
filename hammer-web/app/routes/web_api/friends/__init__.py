from quart import request, make_response, jsonify, session, Blueprint

FriendsHandler = Blueprint('friends_web_api', __name__, url_prefix='/friends')
from app.routes.web_api.friends.friend_relationship import FriendsRelationshipHandler
from app.routes.web_api.friends.follow_relationship import FollowRelationshipHandler
FriendsHandler.register_blueprint( FriendsRelationshipHandler, url_prefix = "/" )
FriendsHandler.register_blueprint( FollowRelationshipHandler, url_prefix = "/" )