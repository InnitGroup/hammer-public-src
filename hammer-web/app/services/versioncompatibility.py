from sqlalchemy import func
from app.extensions import db

from app.models.version_compatiblity_group import VersionCompatibilityGroup
from app.models.version_compatibility_key import VersionCompatibilityKey

async def get_group_by_apikey( api_key : str ) -> VersionCompatibilityGroup | None:
    """
        Gets a version compatibility group by its API key

        :param api_key: The API key to check for

        :return: VersionCompatibilityGroup | None
    """

    return VersionCompatibilityGroup.query.filter(
        func.lower( VersionCompatibilityGroup.api_key ) == func.lower( api_key )
    ).first()

async def get_key_by_value( parent_group : VersionCompatibilityGroup, key_value : str ) -> VersionCompatibilityKey | None:
    """
        Gets a version compatibility key by its value

        :param parent_group: The parent group of the key
        :param key_value: The value of the key to check for

        :return: VersionCompatibilityKey | None
    """

    return VersionCompatibilityKey.query.filter_by(
        parent_group_id = parent_group.id,
        key_value = key_value
    ).first()

async def create_version_compatibility_group( display_name : str, api_key : str ) -> VersionCompatibilityGroup:
    """
        Creates a new version compatibility group

        :param display_name: The display name of the group
        :param api_key: The API key of the group

        :return: VersionCompatibilityGroup
    """

    if await get_group_by_apikey( api_key = api_key ) is not None:
        raise ValueError( "A group with that API key already exists" )

    new_group = VersionCompatibilityGroup(
        display_name = display_name,
        api_key = api_key
    )

    db.session.add( new_group )
    db.session.commit()
    return new_group

async def create_new_key(
    parent_group : VersionCompatibilityGroup,
    key_value : str,
    display_name : str = "Unnamed Key"
) -> VersionCompatibilityKey:
    """
        Creates a new version compatibility key

        :param parent_group: The parent group of the key
        :param key_value: The value of the key
        :param display_name: The display name of the key

        :return: VersionCompatibilityKey
    """

    if await get_key_by_value( parent_group = parent_group, key_value = key_value ) is not None:
        raise ValueError( "A key with that value already exists in the given group" )

    new_key = VersionCompatibilityKey(
        parent_group_id = parent_group.id,
        key_value = key_value,
        display_name = display_name
    )

    db.session.add( new_key )
    db.session.commit()
    return new_key

async def generate_group_keys( parent_group : VersionCompatibilityGroup ) -> list[str]:
    """
        Generates all the keys for the given group

        :param parent_group: The group to generate the keys for

        :return: list[str]
    """

    generated_keys : list[str] = []
    all_keys = VersionCompatibilityKey.query.filter_by(
        parent_group_id = parent_group.id
    ).all()

    for key in all_keys:
        key : VersionCompatibilityKey
        generated_keys.append( key.key_value )

    return generated_keys