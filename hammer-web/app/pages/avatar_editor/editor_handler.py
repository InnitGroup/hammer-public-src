from quart import Blueprint, request, make_response, jsonify, render_template

from app.services import authentication

AvatarEditorPageHandler = Blueprint('avatar_page_editor', __name__, url_prefix='/', subdomain='www')

@AvatarEditorPageHandler.route("/avatar", methods=["GET"])
@authentication.require_authentication
async def _avatar_editor_page():
    return await render_template(
        "avatar_editor/avatar_editor.html"
    )