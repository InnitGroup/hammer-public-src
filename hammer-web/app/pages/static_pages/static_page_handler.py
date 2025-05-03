from quart import Blueprint, render_template, redirect

from app.services import authentication

StaticPageHandler = Blueprint( "StaticPageHandler", __name__, url_prefix = "/" )

@StaticPageHandler.route( "/", methods = [ "GET" ] )
async def _index_page():
    if await authentication.GetCurrentUser() is not None:
        return redirect("/home")
    return await render_template( "static_pages/index.html" )

@StaticPageHandler.route("/terms", methods=["GET"])
async def _terms_page():
    return await render_template("static_pages/terms_of_service.html")