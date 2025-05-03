import hashlib
import json
from datetime import datetime

from app.models.user import User
from app.models.user_avatar import UserAvatar
from app.models.user_avatar_item import UserAvatarItem
from app.models.outfit import Outfit
from app.models.outfit_item import OutfitItem
from app.models.asset import Asset
from app.models.user_avatar_emote import UserAvatarEmote
from app.models.asset_version import AssetVersion

from app.extensions import db, redis_controller
from app.services.economy.purchase import DoesUserOwnAsset
from app.services import assets, thumbnailer

from app.util.avatar_rules import AvatarRules, get_asset_type_rule, wearableAssetType, ScalingRule

from app.enums.ModerationStatus import ModerationStatus
from app.enums.AssetType import AssetType
from app.enums.RigType import RigType

avatar_rules : AvatarRules = AvatarRules()

class AvatarServiceException( Exception ):
    pass
class InvalidAvatarScale( AvatarServiceException ):
    pass
class InvalidBodyColor( AvatarServiceException ):
    pass
class AssetCouldNotBeEquipped( AvatarServiceException ):
    pass

def generate_avatar_hash(
    rig_type : RigType,
    head_color_id : int,
    torso_color_id : int,
    right_arm_color_id : int,
    left_arm_color_id : int,
    right_leg_color_id : int,
    left_leg_color_id : int,
    
    height_scale : float,
    width_scale : float,
    head_scale : float,
    proportion_scale : float,
    body_type_scale : float,
    
    asset_ids : list[ int ]
) -> str:
    hash_str : str = f"""
{rig_type}.
{head_color_id}.
{torso_color_id}.
{right_arm_color_id}.
{left_arm_color_id}.
{right_leg_color_id}.
{left_leg_color_id}
{height_scale}.
{width_scale}.
{head_scale}.
{proportion_scale}.
{body_type_scale}    
"""
    for asset_id in asset_ids:
        hash_str += f"{asset_id}.\n"
    return hashlib.sha256( hash_str.encode() ).hexdigest()
    

async def generate_user_avatar_hash( user_obj : User ) -> str:
    user_avatar_item_list : list[UserAvatarItem] = await get_user_avatar_items( user_obj )
    user_avatar_obj : UserAvatar = await get_user_avatar_obj( user_obj )
    return generate_avatar_hash(
        user_avatar_obj.rig_type,
        user_avatar_obj.head_color_id,
        user_avatar_obj.torso_color_id,
        user_avatar_obj.right_arm_color_id,
        user_avatar_obj.left_arm_color_id,
        user_avatar_obj.right_leg_color_id,
        user_avatar_obj.left_leg_color_id,
        
        user_avatar_obj.height_scale,
        user_avatar_obj.width_scale,
        user_avatar_obj.head_scale,
        user_avatar_obj.proportion_scale,
        user_avatar_obj.body_type_scale,
        
        [ x.asset_id for x in user_avatar_item_list ]
    )

async def generate_outfit_hash( outfit_obj : Outfit ) -> str:
    outfit_items_list : list[OutfitItem] = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    return generate_avatar_hash(
        outfit_obj.rig_type,
        outfit_obj.head_color_id,
        outfit_obj.torso_color_id,
        outfit_obj.right_arm_color_id,
        outfit_obj.left_arm_color_id,
        outfit_obj.right_leg_color_id,
        outfit_obj.left_leg_color_id,
        
        outfit_obj.height_scale,
        outfit_obj.width_scale,
        outfit_obj.head_scale,
        outfit_obj.proportion_scale,
        outfit_obj.body_type_scale,
        
        [ x.asset_id for x in outfit_items_list ]
    )

async def get_user_avatar_obj( user_obj : User ) -> UserAvatar:
    user_avatar_obj : UserAvatar | None = UserAvatar.query.filter_by( user_id = user_obj.id ).first()
    if user_avatar_obj is None:
        user_avatar_obj = UserAvatar( user_obj.id )
        db.session.add( user_avatar_obj )
        db.session.commit()
    return user_avatar_obj

async def get_user_avatar_items( user_obj : User, block_asset_types : list[ AssetType ] = [], allow_moderated_items : bool = False ) -> list[UserAvatarItem]:
    user_avatar_item_list : list[UserAvatarItem] = UserAvatarItem.query.filter_by( user_id = user_obj.id ).order_by( UserAvatarItem.asset_id.asc() ).all()
    if len( block_asset_types ) > 0:
        for user_avatar_item in user_avatar_item_list:
            asset_obj : Asset = await assets.GetAssetById( user_avatar_item.asset_id )
            if asset_obj.asset_type in block_asset_types or ( not allow_moderated_items and asset_obj.moderation_status != ModerationStatus.Approved ):
                user_avatar_item_list.remove( user_avatar_item )
    
    return user_avatar_item_list

async def set_user_emote(
    user_obj : User,
    emote_id : int,
    emote_position : int 
):
    asset_obj : Asset = await assets.GetAssetById( emote_id )
    if await DoesUserOwnAsset( user = user_obj, asset = asset_obj ) is False:
        raise AssetCouldNotBeEquipped( "User does not own the emote" )
    
    user_avatar_emote : UserAvatarEmote | None = UserAvatarEmote.query.filter_by( user_id = user_obj.id, emote_position = emote_position ).first()
    if user_avatar_emote is None:
        user_avatar_emote = UserAvatarEmote( user_obj.id, emote_id, emote_position )
        db.session.add( user_avatar_emote )
    else:
        user_avatar_emote.emote_id = emote_id
        user_avatar_emote.created_at = datetime.utcnow()
    db.session.commit()
    
async def remove_user_emote(
    target_user : User,
    emote_position : int
):
    user_avatar_emote : UserAvatarEmote | None = UserAvatarEmote.query.filter_by( user_id = target_user.id, emote_position = emote_position ).first()
    if user_avatar_emote is not None:
        db.session.delete( user_avatar_emote )
        db.session.commit()

async def set_user_avatar_rig( user_obj : User, rig_type : RigType, render_thumbnail : bool = False ) -> None:
    user_avatar_obj : UserAvatar = await get_user_avatar_obj( user_obj )
    user_avatar_obj.rig_type = rig_type
    db.session.commit()
    if render_thumbnail:
        await thumbnailer.queue_full_user_render( user_obj )

async def verify_user_avatar_scaling(
    height_scale : float | int,
    width_scale : float | int,
    head_scale : float | int,
    proportion_scale : float | int,
    body_type_scale : float | int
) -> None:
    try:
        avatar_scaling_rules : dict = avatar_rules.characterScales
        height_scale_rule : ScalingRule = avatar_scaling_rules["height"]
        width_scale_rule : ScalingRule = avatar_scaling_rules["width"]
        head_scale_rule : ScalingRule = avatar_scaling_rules["head"]
        proportion_scale_rule : ScalingRule = avatar_scaling_rules["proportion"]
        body_type_scale_rule : ScalingRule = avatar_scaling_rules["bodyType"]
        
        assert height_scale_rule.minimum <= height_scale <= height_scale_rule.maximum, "Height scale out of bounds"
        assert width_scale_rule.minimum <= width_scale <= width_scale_rule.maximum, "Width scale out of bounds"
        assert head_scale_rule.minimum <= head_scale <= head_scale_rule.maximum, "Head scale out of bounds"
        assert proportion_scale_rule.minimum <= proportion_scale <= proportion_scale_rule.maximum, "Proportion scale out of bounds"
        assert body_type_scale_rule.minimum <= body_type_scale <= body_type_scale_rule.maximum, "Body type scale out of bounds"
        
        assert height_scale % height_scale_rule.increment < height_scale_rule.increment, "Height scale not a multiple of step"
        assert width_scale % width_scale_rule.increment < width_scale_rule.increment, "Width scale not a multiple of step"
        assert head_scale % head_scale_rule.increment < head_scale_rule.increment, "Head scale not a multiple of step"
        assert proportion_scale % proportion_scale_rule.increment < proportion_scale_rule.increment, "Proportion scale not a multiple of step"
        assert body_type_scale % body_type_scale_rule.increment < body_type_scale_rule.increment, "Body type scale not a multiple of step"
    except AssertionError as e:
        raise InvalidAvatarScale( str( e ) )

async def verify_user_avatar_colors(
    head_color_id : int,
    torso_color_id : int,
    right_arm_color_id : int,
    left_arm_color_id : int,
    right_leg_color_id : int,
    left_leg_color_id : int
) -> None:
    allowed_body_color_ids : list[int] = [ x.brickColorId for x in avatar_rules.bodyColorsPalette ]
    try:
        assert head_color_id in allowed_body_color_ids, "headColorId is invalid"
        assert torso_color_id in allowed_body_color_ids, "torsoColorId is invalid"
        assert right_arm_color_id in allowed_body_color_ids, "rightArmColorId is invalid"
        assert left_arm_color_id in allowed_body_color_ids, "leftArmColorId is invalid"
        assert right_leg_color_id in allowed_body_color_ids, "rightLegColorId is invalid"
        assert left_leg_color_id in allowed_body_color_ids, "leftLegColorId is invalid"
    except AssertionError as e:
        raise InvalidBodyColor( str( e ) )

async def set_user_avatar_scales(
    user_obj : User,
    height_scale : float | int,
    width_scale : float | int,
    head_scale : float | int,
    proportion_scale : float | int,
    body_type_scale : float | int,
    render_thumbnail : bool = False
) -> None:
    await verify_user_avatar_scaling( height_scale, width_scale, head_scale, proportion_scale, body_type_scale )
    
    user_avatar_obj : UserAvatar = await get_user_avatar_obj( user_obj )
    user_avatar_obj.height_scale = float( height_scale )
    user_avatar_obj.width_scale = float( width_scale )
    user_avatar_obj.head_scale = float( head_scale )
    user_avatar_obj.proportion_scale = float( proportion_scale )
    user_avatar_obj.body_type_scale = float( body_type_scale )
    db.session.commit()
    if render_thumbnail:
        await thumbnailer.queue_full_user_render( user_obj )

async def set_user_body_colors(
    user_obj : User,
    head_color_id : int,
    torso_color_id : int,
    right_arm_color_id : int,
    left_arm_color_id : int,
    right_leg_color_id : int,
    left_leg_color_id : int,
    render_thumbnail : bool = False
):
    await verify_user_avatar_colors( head_color_id, torso_color_id, right_arm_color_id, left_arm_color_id, right_leg_color_id, left_leg_color_id )
    
    user_avatar_obj : UserAvatar = await get_user_avatar_obj( user_obj )
    user_avatar_obj.head_color_id = head_color_id
    user_avatar_obj.torso_color_id = torso_color_id
    user_avatar_obj.right_arm_color_id = right_arm_color_id
    user_avatar_obj.left_arm_color_id = left_arm_color_id
    user_avatar_obj.right_leg_color_id = right_leg_color_id
    user_avatar_obj.left_leg_color_id = left_leg_color_id
    db.session.commit()
    if render_thumbnail:
        await thumbnailer.queue_full_user_render( user_obj )

async def verify_user_avatar_items(
    user_obj : User,
    asset_ids : list[ int ],
    raise_exception_on_invalid_asset : bool = False
) -> list[ int ]:
    """
        Verifies that the user can equip the provided asset IDs.
        Returns a list of asset IDs that are not allowed to be equipped.
        
        :param user_obj: The user to verify the avatar items for
        :param asset_ids: The asset IDs to verify
    """
    allowed_assets_ids : list[ int ] = []
    removed_asset_ids : list[ int ] = []
    asset_type_counter : dict[ AssetType, int ] = {}
    for asset_id in asset_ids:
        if asset_id < 1:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because it does not exist or is moderated" )
            removed_asset_ids.append( asset_id )
            continue
        asset_obj : Asset = await assets.GetAssetById( asset_id )
        if asset_obj is None or asset_obj.moderation_status != ModerationStatus.Approved:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because it does not exist or is moderated" )
            removed_asset_ids.append( asset_id )
            continue
        if not await DoesUserOwnAsset( user = user_obj, asset = asset_obj ):
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because the user does not own it" )
            removed_asset_ids.append( asset_id )
            continue
        if asset_obj.id in allowed_assets_ids:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because its a duplicate" )
            removed_asset_ids.append( asset_id )
            continue
        allowed_assets_ids.append( asset_obj.id )
        if asset_obj.asset_type not in asset_type_counter:
            asset_type_counter[ asset_obj.asset_type ] = 0
        asset_type_rule : wearableAssetType | None = get_asset_type_rule( asset_obj.asset_type, avatar_rules )
        if asset_type_rule is None:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because its type is not wearable" )
            removed_asset_ids.append( asset_id )
            continue
        if asset_type_counter[ asset_obj.asset_type ] >= asset_type_rule.max_wearable:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because the asset type limit was reached" )
            removed_asset_ids.append( asset_id )
            continue
        asset_type_counter[ asset_obj.asset_type ] += 1
    return removed_asset_ids

async def set_user_avatar_items(
    user_obj : User,
    asset_ids : list[ int ],
    render_thumbnail : bool = False,
    
    raise_exception_on_invalid_asset : bool = False
) -> list[int]:
    """
        Sets the user's avatar items to the provided asset IDs.
        Will remove any existing items and add the new ones, unless
        an exception is raised. Returns a list of asset IDs that were
        removed from the user's avatar.
        
        :param user_obj: The user to set the avatar items for
        :param asset_ids: The asset IDs to set
        :param render_thumbnail: Whether to queue a thumbnail render
        :param raise_exception_on_invalid_asset: Whether to raise an exception on invalid asset IDs
        
        :return: The asset IDs that were removed from the user's avatar
    """
    
    if len( asset_ids ) > avatar_rules.max_wearables:
        raise AssetCouldNotBeEquipped( f"Requested assets exceed the limit of {avatar_rules.max_wearables} max assets" )
    
    allowed_assets_ids : list[ int ] = []
    removed_asset_ids : list[ int ] = []
    asset_type_counter : dict[ AssetType, int ] = {}
    for asset_id in asset_ids:
        asset_obj : Asset = await assets.GetAssetById( asset_id )
        if asset_obj is None or asset_obj.moderation_status != ModerationStatus.Approved:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because it does not exist or is moderated" )
            removed_asset_ids.append( asset_id )
            continue
        if not await DoesUserOwnAsset( user = user_obj, asset = asset_obj ):
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because the user does not own it" )
            removed_asset_ids.append( asset_id )
            continue
        if asset_obj.id in allowed_assets_ids:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because its a duplicate" )
            removed_asset_ids.append( asset_id )
            continue
        allowed_assets_ids.append( asset_obj.id )
        if asset_obj.asset_type not in asset_type_counter:
            asset_type_counter[ asset_obj.asset_type ] = 0
        asset_type_rule : wearableAssetType | None = get_asset_type_rule( asset_obj.asset_type, avatar_rules )
        if asset_type_rule is None:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because its type is not wearable" )
            removed_asset_ids.append( asset_id )
            continue
        if asset_type_counter[ asset_obj.asset_type ] >= asset_type_rule.max_wearable:
            if raise_exception_on_invalid_asset:
                raise AssetCouldNotBeEquipped( f"Asset {asset_id} could not be equipped because the asset type limit was reached" )
            removed_asset_ids.append( asset_id )
            continue
        asset_type_counter[ asset_obj.asset_type ] += 1
    
    # Remove existing items
    user_avatar_item_list : list[UserAvatarItem] = await get_user_avatar_items( user_obj, allow_moderated_items = True )
    for user_avatar_item in user_avatar_item_list:
        db.session.delete( user_avatar_item )
    for asset_id in allowed_assets_ids:
        new_user_avatar_item : UserAvatarItem = UserAvatarItem( user_obj.id, asset_id )
        db.session.add( new_user_avatar_item )
    db.session.commit()
    
    if render_thumbnail:
        await thumbnailer.queue_full_user_render( user_obj )
    return removed_asset_ids

async def build_avatar_fetch_response( user_obj : User | None, avatar_hash : str | None, block_asset_types : list[AssetType] = [], outfit_obj : Outfit | None = None ) -> dict | None:
    """
        Builds the response for the avatar fetch endpoint.
        Supports lookup by user ID or avatar hash, if requested by avatar_hash it will be
        searched from the redis cache. Cache has to be populated with a request with a User object to this function first.
        
        This allows for thumbnailer service to cache a avatar by its hash so a gameserver render task can request it later on
        in case the user changed their avatar while the request is still being processed by the renderer.
        
        :param user_obj: The user to fetch the avatar for
        :param avatar_hash: The hash of the avatar to fetch
        :param block_asset_types: The asset types to block from the response
        :param outfit_obj: If user_obj is None, the outfit to fetch the avatar for
        
        :return: The avatar fetch response
    """
    
    if avatar_hash is not None:
        avatar_fetch_cache_key : str = f"avatar_fetch_response:{avatar_hash}:{''.join([str(x.value)+':' for x in block_asset_types])}"
        cache_lookup : str = await redis_controller.get( avatar_fetch_cache_key )
        if cache_lookup is not None:
            return json.loads( cache_lookup )
    
    target_avatar_obj : UserAvatar | Outfit | None = None
    if user_obj is not None:
        target_avatar_obj = await get_user_avatar_obj( user_obj )
    elif outfit_obj is not None:
        target_avatar_obj = outfit_obj
    else:
        return None
    
    avatar_items_list : list[UserAvatarItem] | list[OutfitItem] = []
    if user_obj is not None:
        avatar_items_list = await get_user_avatar_items( user_obj, block_asset_types = block_asset_types )
    else:
        # It is not really important to follow the block_asset_types for outfits as it is usually used for thumbnail rendering and not ingame
        avatar_items_list = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    
    asset_and_asset_type_ids : list[dict] = []
    avatar_assets_list : list[int] = []
    equipped_gear_version_ids : list[int] = []
    
    user_equipped_emotes : list[UserAvatarEmote] = UserAvatarEmote.query.filter_by( user_id = user_obj.id ).all()
    emotes : list[dict] = []
    
    for user_avatar_item in avatar_items_list:
        asset_obj : Asset = await assets.GetAssetById( user_avatar_item.asset_id )
        latest_asset_version : AssetVersion | None = await assets.GetLatestAssetVersion( user_avatar_item.asset_id )
        if asset_obj.asset_type == AssetType.Gear:
            equipped_gear_version_ids.append( latest_asset_version.id )
            continue
        
        asset_and_asset_type_ids.append({
            "assetId": user_avatar_item.asset_id,
            "assetTypeId": asset_obj.asset_type.value
        })
        if latest_asset_version is not None:
            avatar_assets_list.append( latest_asset_version.id )
    
    for user_emote in user_equipped_emotes:
        asset_obj : Asset = await assets.GetAssetById( user_emote.emote_id )
        emotes.append({
            "assetId": user_emote.emote_id,
            "assetName": asset_obj.name,
            "position": user_emote.emote_position
        })
    
    avatar_hash : str = await generate_user_avatar_hash( user_obj ) if user_obj is not None else await generate_outfit_hash( outfit_obj )
    avatar_fetch_cache_key : str = f"avatar_fetch_response:{avatar_hash}:{''.join([str(x.value)+':' for x in block_asset_types])}"
    built_response : dict = {
        "resolvedAvatarType": target_avatar_obj.rig_type.name,
        "equippedGearVersionIds": equipped_gear_version_ids,
        "backpackGearVersionIds": equipped_gear_version_ids,
        "accessoryVersionIds": avatar_assets_list,
        "assetAndAssetTypeIds": asset_and_asset_type_ids,
        "bodyColors": {
            "headColorId": target_avatar_obj.head_color_id,
            "leftArmColorId": target_avatar_obj.left_arm_color_id,
            "leftLegColorId": target_avatar_obj.left_leg_color_id,
            "rightArmColorId": target_avatar_obj.right_arm_color_id,
            "rightLegColorId": target_avatar_obj.right_leg_color_id,
            "torsoColorId": target_avatar_obj.torso_color_id,

            "HeadColor": target_avatar_obj.head_color_id,
            "LeftArmColor": target_avatar_obj.left_arm_color_id,
            "LeftLegColor": target_avatar_obj.left_leg_color_id,
            "RightArmColor": target_avatar_obj.right_arm_color_id,
            "RightLegColor": target_avatar_obj.right_leg_color_id,
            "TorsoColor": target_avatar_obj.torso_color_id
        },
        "animationAssetIds": {},
        "scales": {
            "height": target_avatar_obj.height_scale,
            "width": target_avatar_obj.width_scale,
            "head": target_avatar_obj.head_scale,
            "depth": 1,
            "proportion": target_avatar_obj.proportion_scale,
            "bodyType": target_avatar_obj.body_type_scale,

            "Height": target_avatar_obj.height_scale,
            "Width": target_avatar_obj.width_scale,
            "Head": target_avatar_obj.head_scale,
            "Depth": 1,
            "Proportion": target_avatar_obj.proportion_scale,
            "BodyType": target_avatar_obj.body_type_scale
        },
        "emotes": emotes
    }
    await redis_controller.set(
        avatar_fetch_cache_key,
        value = json.dumps( built_response ),
        ex = 60 * 60 * 24
    )
    return built_response

async def revalidate_user_avatar( user_obj : User ) -> list[ Asset ]:
    """
        Checks the user currently wearing and removes items that they no longer own
        or have been content deleted from the website. Returns a list of assets that
        were removed from the user's avatar.
        
        :param user_obj: The user to revalidate the avatar for
        
        :return: The assets that were removed from the user's avatar
    """
    removed_assets : list[ Asset ] = []
    existing_asset_ids : list[ int ] = []
    asset_type_counter : dict[ AssetType, int ] = {}
    user_avatar_item_list : list[UserAvatarItem] = await get_user_avatar_items( user_obj )
    for user_avatar_item in user_avatar_item_list:
        asset_obj : Asset = await assets.GetAssetById( user_avatar_item.asset_id)
        if not await DoesUserOwnAsset( user = user_obj, asset = asset_obj ) or asset_obj.moderation_status != ModerationStatus.Approved:
            db.session.delete( user_avatar_item )
            removed_assets.append( asset_obj )
            continue
        if asset_obj.id not in existing_asset_ids:
            existing_asset_ids.append( asset_obj.id )
        else:
            db.session.delete( user_avatar_item )
            removed_assets.append( asset_obj )
            continue
        if asset_obj.asset_type not in asset_type_counter:
            asset_type_counter[ asset_obj.asset_type ] = 0
        asset_type_rule : wearableAssetType = get_asset_type_rule( asset_obj.asset_type, avatar_rules )
        if asset_type_rule is None:
            db.session.delete( user_avatar_item )
            removed_assets.append( asset_obj )
            continue
        if asset_type_counter[ asset_obj.asset_type ] >= asset_type_rule.max_wearable:
            db.session.delete( user_avatar_item )
            removed_assets.append( asset_obj )
            continue
        asset_type_counter[ asset_obj.asset_type ] += 1
    
    db.session.commit()
    return removed_assets

async def update_outfit(
    outfit_obj : Outfit,
    outfit_name : str = "New Outfit",
    head_color_id : int = 1001,
    torso_color_id : int = 1001,
    right_arm_color_id : int = 1001,
    left_arm_color_id : int = 1001,
    right_leg_color_id : int = 1001,
    left_leg_color_id : int = 1001,
    
    height_scale : float = 1.0,
    width_scale : float = 1.0,
    head_scale : float = 1.0,
    proportion_scale : float = 1.0,
    body_type_scale : float = 1.0,
    
    rig_type : RigType = RigType.R6,
    equipped_asset_ids : list[ int ] = [],
    render_thumbnail : bool = True
):
    outfit_obj.outfit_name = outfit_name
    outfit_obj.rig_type = rig_type
    outfit_obj.head_color_id = head_color_id
    outfit_obj.torso_color_id = torso_color_id
    outfit_obj.right_arm_color_id = right_arm_color_id
    outfit_obj.left_arm_color_id = left_arm_color_id
    outfit_obj.right_leg_color_id = right_leg_color_id
    outfit_obj.left_leg_color_id = left_leg_color_id
    outfit_obj.height_scale = height_scale
    outfit_obj.width_scale = width_scale
    outfit_obj.head_scale = head_scale
    outfit_obj.proportion_scale = proportion_scale
    outfit_obj.body_type_scale = body_type_scale
    
    current_outfit_items : list[OutfitItem] = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    for outfit_item in current_outfit_items:
        db.session.delete( outfit_item )
    for asset_id in equipped_asset_ids:
        new_outfit_item : OutfitItem = OutfitItem( outfit_obj.id, asset_id )
        db.session.add( new_outfit_item )
    
    outfit_obj.avatar_hash = await generate_outfit_hash( outfit_obj )
    db.session.commit()
    
    if render_thumbnail:
        try:
            await build_avatar_fetch_response( user_obj = None, avatar_hash = outfit_obj.avatar_hash, outfit_obj = outfit_obj )
            await thumbnailer.render_avatar_thumbnail(
                avatar_hash = outfit_obj.avatar_hash
            )
        except Exception as e:
            pass

async def create_outfit(
    creator_user : User,
    outfit_name : str = "New Outfit",
    head_color_id : int = 1001,
    torso_color_id : int = 1001,
    right_arm_color_id : int = 1001,
    left_arm_color_id : int = 1001,
    right_leg_color_id : int = 1001,
    left_leg_color_id : int = 1001,
    
    height_scale : float = 1.0,
    width_scale : float = 1.0,
    head_scale : float = 1.0,
    proportion_scale : float = 1.0,
    body_type_scale : float = 1.0,
    
    rig_type : RigType = RigType.R6,
    equipped_asset_ids : list[ int ] = [],
    render_thumbnail : bool = True
) -> Outfit:
    await verify_user_avatar_colors( head_color_id, torso_color_id, right_arm_color_id, left_arm_color_id, right_leg_color_id, left_leg_color_id )
    await verify_user_avatar_scaling( height_scale, width_scale, head_scale, proportion_scale, body_type_scale )
    
    already_accepted_assets : list[ int ] = []
    for requested_asset_id in equipped_asset_ids:
        asset_obj : Asset = await assets.GetAssetById( requested_asset_id )
        if asset_obj is None or asset_obj.moderation_status != ModerationStatus.Approved:
            raise AssetCouldNotBeEquipped( f"Asset {requested_asset_id} could not be equipped because it does not exist or is moderated" )
        if not await DoesUserOwnAsset( user = creator_user, asset = asset_obj ):
            raise AssetCouldNotBeEquipped( f"Asset {requested_asset_id} could not be equipped because the user does not own it" )
        if asset_obj.id in already_accepted_assets:
            raise AssetCouldNotBeEquipped( f"Asset {requested_asset_id} could not be equipped because its a duplicate" )
        already_accepted_assets.append( asset_obj.id )
    
    avatar_hash : str = generate_avatar_hash(
        rig_type,
        head_color_id,
        torso_color_id,
        right_arm_color_id,
        left_arm_color_id,
        right_leg_color_id,
        left_leg_color_id,
        
        height_scale,
        width_scale,
        head_scale,
        proportion_scale,
        body_type_scale,
        
        equipped_asset_ids
    )
    new_outfit : Outfit = Outfit(
        outfit_name = outfit_name,
        avatar_hash = avatar_hash,
        creator_user_id = creator_user.id,
        rig_type = rig_type
    )
    new_outfit.head_color_id = head_color_id
    new_outfit.torso_color_id = torso_color_id
    new_outfit.right_arm_color_id = right_arm_color_id
    new_outfit.left_arm_color_id = left_arm_color_id
    new_outfit.right_leg_color_id = right_leg_color_id
    new_outfit.left_leg_color_id = left_leg_color_id
    
    new_outfit.height_scale = height_scale
    new_outfit.width_scale = width_scale
    new_outfit.head_scale = head_scale
    new_outfit.proportion_scale = proportion_scale
    new_outfit.body_type_scale = body_type_scale
    
    db.session.add( new_outfit )
    db.session.commit()
    
    for asset_id in equipped_asset_ids:
        new_outfit_item : OutfitItem = OutfitItem( new_outfit.id, asset_id )
        db.session.add( new_outfit_item )
    db.session.commit()
    
    if render_thumbnail:
        try:
            await build_avatar_fetch_response( user_obj = None, avatar_hash = new_outfit.avatar_hash, outfit_obj = new_outfit )
            await thumbnailer.render_avatar_thumbnail(
                avatar_hash = avatar_hash
            )
        except Exception as e:
            pass
    
    return new_outfit

async def delete_outfit( outfit_obj : Outfit ) -> None:
    outfit_items : list[OutfitItem] = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    for outfit_item in outfit_items:
        db.session.delete( outfit_item )
    db.session.delete( outfit_obj )
    db.session.commit()
    
async def wear_outfit( target_user : User, outfit_obj : Outfit, render_thumbnail : bool = True ) -> list[ Asset ]:
    target_user_avatar_obj : UserAvatar = await get_user_avatar_obj( target_user )
    
    outfit_items : list[OutfitItem] = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    removed_asset_ids : list[ int ] = await verify_user_avatar_items( target_user, [ x.asset_id for x in outfit_items ] )
    
    target_user_avatar_obj.rig_type = outfit_obj.rig_type
    target_user_avatar_obj.head_color_id = outfit_obj.head_color_id
    target_user_avatar_obj.torso_color_id = outfit_obj.torso_color_id
    target_user_avatar_obj.right_arm_color_id = outfit_obj.right_arm_color_id
    target_user_avatar_obj.left_arm_color_id = outfit_obj.left_arm_color_id
    target_user_avatar_obj.right_leg_color_id = outfit_obj.right_leg_color_id
    target_user_avatar_obj.left_leg_color_id = outfit_obj.left_leg_color_id
    target_user_avatar_obj.height_scale = outfit_obj.height_scale
    target_user_avatar_obj.width_scale = outfit_obj.width_scale
    target_user_avatar_obj.head_scale = outfit_obj.head_scale
    target_user_avatar_obj.proportion_scale = outfit_obj.proportion_scale
    target_user_avatar_obj.body_type_scale = outfit_obj.body_type_scale
    
    current_avatar_items : list[UserAvatarItem] = await get_user_avatar_items( target_user, allow_moderated_items = True )
    for current_avatar_item in current_avatar_items:
        db.session.delete( current_avatar_item )
    for outfit_item in outfit_items:
        new_avatar_item : UserAvatarItem = UserAvatarItem( target_user.id, outfit_item.asset_id )
        db.session.add( new_avatar_item )
    db.session.commit()
    
    if render_thumbnail:
        await thumbnailer.queue_full_user_render( target_user )
    
    return [ await assets.GetAssetById( x ) for x in removed_asset_ids ]
    