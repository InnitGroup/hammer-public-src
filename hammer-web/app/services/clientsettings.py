import json
from datetime import datetime
from app.extensions import db, redis_controller

from app.models.client_settings_group import ClientSettingsGroup
from app.models.client_settings_value import ClientSettingsValue
from app.enums.FlagValueType import FlagValueType

async def get_client_settings_group_by_name( group_name : str, api_key : str | None = None ) -> ClientSettingsGroup | None:
    """
        Gets a client settings group by its name

        :param group_name: The name of the group to get
        :param api_key: The API key to check for

        :return: ClientSettingsGroup | None
    """

    return ClientSettingsGroup.query.filter_by(
        name = group_name,
        api_key = api_key
    ).first()

async def clear_client_settings_cache( group_obj : ClientSettingsGroup ) -> None:
    """
        Clears the client settings cache for the given group

        :param group_obj: The group to clear the cache for
    """

    key_name : str = f"client_settings_cache_{group_obj.id}"
    await redis_controller.delete( key_name )

async def generate_client_settings(
    group_obj : ClientSettingsGroup,
    skip_cache : bool = False
) -> dict:
    """
        Generates a dictionary of client settings for the given group

        :param group_obj: The group to generate the settings for
        :param skip_cache: Whether or not to skip the cache

        :return: dict
    """

    key_name : str = f"client_settings_cache_{group_obj.id}"
    if not skip_cache and await redis_controller.exists( key_name ) > 0:
        cached_data = await redis_controller.get( key_name )
        return json.loads(
            cached_data
        )

    built_client_settings : dict = {}
    group_setting_values : list[ ClientSettingsValue ] = ClientSettingsValue.query.filter_by(
        parent_group_id = group_obj.id
    ).order_by( ClientSettingsValue.id.asc() ).all()

    for setting in group_setting_values:
        if setting.value_type == FlagValueType.Boolean:
            built_client_settings[ setting.key_name ] = setting.value == "1"
        elif setting.value_type == FlagValueType.Integer:
            built_client_settings[ setting.key_name ] = int( setting.value )
        else:
            built_client_settings[ setting.key_name ] = setting.value
    
    await redis_controller.set( key_name, json.dumps( built_client_settings ), ex = 60 * 60 * 24 )
    return built_client_settings

async def parse_client_settings(
    target_group_obj : ClientSettingsGroup,
    new_settings : dict,
    invalidate_cache : bool = True
) -> None:
    """
        Parses the given client settings and updates the database

        :param target_group_obj: The group to update the settings for
        :param new_settings: The new settings to parse
        :param invalidate_cache: Whether or not to invalidate the cache
    """

    # We generate the previous flags first so its guaranteed to be in the cache
    # before we clear all the old flags as it mightget requested during the process
    await generate_client_settings(
        group_obj = target_group_obj,
        skip_cache = True
    )

    ClientSettingsValue.query.filter_by(
        parent_group_id = target_group_obj.id
    ).delete()
    db.session.commit()

    for key, value in new_settings.items():
        ValueType : FlagValueType = FlagValueType.String if isinstance( value, str ) else FlagValueType.Boolean if isinstance( value, bool ) else FlagValueType.Integer if isinstance( value, int ) else None
        if FlagValueType is None:
            continue
        if ValueType == FlagValueType.Boolean:
            value = "1" if value else "0"

        new_setting = ClientSettingsValue(
            parent_group_id = target_group_obj.id,
            key_name = key,
            value = str(value),
            value_type = ValueType
        )
        db.session.add( new_setting )
    target_group_obj.updated_at = datetime.utcnow()

    db.session.commit()
    if invalidate_cache:
        await clear_client_settings_cache( target_group_obj )
        await generate_client_settings( target_group_obj, skip_cache = True )
    
    return

async def create_new_settings_group(
    group_name : str,
    group_description : str = "No description provided",
    group_settings : dict = {},
    api_key : str | None = None,
    is_application_group : bool = False,
    gameserver_only : bool = False
) -> ClientSettingsGroup:
    """
        Creates a new client settings group

        :param group_name: The name of the group
        :param api_key: The API key to use
        :param is_application_group: Whether or not this is an application group
        :param gameserver_only: Whether or not this is only accessible by game servers

        :return: ClientSettingsGroup
    """
    if is_application_group:
        group_name = f"application_{group_name}"

    new_group = ClientSettingsGroup(
        name = group_name,
        description = group_description,
        api_key = api_key,
        gameserver_only = gameserver_only
    )
    db.session.add( new_group )
    db.session.commit()

    if len( group_settings ) > 0:
        await parse_client_settings( target_group_obj = new_group, new_settings = group_settings )
    
    return new_group