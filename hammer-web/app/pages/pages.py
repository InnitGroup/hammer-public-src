from quart import Blueprint, render_template

PagesRoute = Blueprint( 'pages', __name__, url_prefix='/' )

from app.pages.authentication_pages.auth_pages_handler import LoginHandler
from app.pages.static_pages.static_page_handler import StaticPageHandler
from app.pages.home.home_handler import HomeHandler
from app.pages.admin.admin_page_handler import AdminPageHandler

PagesRoute.register_blueprint( StaticPageHandler, url_prefix = "/", subdomain = "www" )
PagesRoute.register_blueprint( LoginHandler, url_prefix = "/", subdomain = "www" )
PagesRoute.register_blueprint( HomeHandler, url_prefix = "/", subdomain = "www" )
PagesRoute.register_blueprint( AdminPageHandler, url_prefix = "/", subdomain = "simulpong" )