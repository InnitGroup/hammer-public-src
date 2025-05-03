from quart import Blueprint, render_template, request, redirect, url_for
from app.services import authentication
from app.models.gameserver import GameServer
from app.enums.AdminPermissions import AdminPermissions

GameserverPageHandler = Blueprint( 'admin_gameserver', __name__, url_prefix = '/gameserver')

@GameserverPageHandler.route('/', methods=['GET'])
@authentication.require_admin_permission([ AdminPermissions.ManageGameservers ])
async def _view_gameserver_list():
    all_gameservers = GameServer.query.all()
    
    return await render_template('admin/gameserver_manager/gameserver_list.html', all_gameservers = all_gameservers )