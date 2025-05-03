import logging
from quart import request, make_response, Blueprint, jsonify, redirect

from app.services import authentication, clientsettings
from app.models.client_settings_group import ClientSettingsGroup

ClientSettingsRoute = Blueprint('clientsettings', __name__, url_prefix='/')

@ClientSettingsRoute.route('/Setting/QuietGet/<group_name>', methods=['GET'], subdomain = "clientsettings.api")
@ClientSettingsRoute.route('/Setting/QuietGet/<group_name>/', methods=['GET'], subdomain = "clientsettings.api")
@ClientSettingsRoute.route('/Setting/QuietGet/<group_name>', methods=['GET'], subdomain = "clientsettings")
@ClientSettingsRoute.route('/Setting/QuietGet/<group_name>/', methods=['GET'], subdomain = "clientsettings")
async def _quiet_get_settings( group_name : str ):
    requestApiKey = request.args.get(
        key = "apiKey",
        default = None,
        type = str
    )

    if requestApiKey is not None and len(requestApiKey) > 255:
        return await make_response(
            jsonify({ "status": 0, "message": "Unknown group" }),
            404
        )
        
    group_obj : ClientSettingsGroup | None = await clientsettings.get_client_settings_group_by_name( group_name = group_name, api_key = requestApiKey )
    if group_obj is None:
        return await make_response(
            jsonify({ "status": 0, "message": "Unknown group" }),
            404
        )
    
    if group_obj.gameserver_only and await authentication.GetCurrentGameServer( verify_access_key = False ) is None:
        return await make_response(
            jsonify({ "status": 1, "message": "This group is only accessible by game servers" }),
            403
        )
    
    client_settings : dict = await clientsettings.generate_client_settings( 
        group_obj = group_obj 
    )

    return await make_response(
        jsonify( client_settings ),
        200
    )

@ClientSettingsRoute.route('/v1/settings/application', methods=['GET'], subdomain = "clientsettingscdn")
@ClientSettingsRoute.route('/v1/settings/application/', methods=['GET'], subdomain = "clientsettingscdn")
async def _get_application_settings():
    requestedApplicationName : str = request.args.get(
        key = "applicationName",
        default = None,
        type = str
    )
    if requestedApplicationName is None:
        return await make_response(
            jsonify({ "status": 0, "message": "Missing parameter" }),
            400
        )
    if len(requestedApplicationName) > 255:
        return await make_response(
            jsonify({ "status": 0, "message": "Invalid parameter" }),
            400
        )

    group_obj : ClientSettingsGroup | None = await clientsettings.get_client_settings_group_by_name( group_name = f"application_{requestedApplicationName}", api_key = None )
    if group_obj is None:
        return await make_response(
            jsonify({ "status": 0, "message": "Unknown application" }),
            404
        )
    
    client_settings : dict = await clientsettings.generate_client_settings(
        group_obj = group_obj,
        skip_cache = False
    )

    return await make_response(
        jsonify({
            "applicationSettings": client_settings,
        }),
        200
    )

@ClientSettingsRoute.route('/v2/settings/application/<application_name>', methods=['GET'], subdomain = "clientsettingscdn")
async def _get_application_settings_v2( application_name : str ):
    group_obj : ClientSettingsGroup | None = await clientsettings.get_client_settings_group_by_name( group_name = f"application_{application_name}", api_key = None )
    if group_obj is None:
        return await make_response(
            jsonify({ "status": 0, "message": "Unknown application" }),
            404
        )
    
    client_settings : dict = await clientsettings.generate_client_settings(
        group_obj = group_obj,
        skip_cache = False
    )

    return await make_response(
        jsonify({
            "applicationSettings": client_settings,
        }),
        200
    )