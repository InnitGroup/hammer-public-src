"""
    avatar.roblox.com
"""

from quart import Blueprint, request, make_response, jsonify, abort

from app.services import authentication, assets, avatar, thumbnailer, text_moderation
from app.models.asset import Asset
from app.models.user import User
from app.models.user_avatar import UserAvatar
from app.models.user_avatar_item import UserAvatarItem
from app.models.asset_version import AssetVersion
from app.models.outfit import Outfit
from app.models.outfit_item import OutfitItem
from app.models.user_avatar_emote import UserAvatarEmote
from app.enums.AssetType import AssetType
from app.enums.RigType import RigType
from app.enums.AccountStatus import AccountStatus
from app.extensions import remote_address_limiter, csrf_protect, user_limiter
from app.util.avatar_rules import AvatarRules, get_asset_type_rule

AvatarRoute = Blueprint('avatar_roblox', __name__, url_prefix='/', subdomain='avatar')

avatar_rules : AvatarRules = AvatarRules()

@AvatarRoute.errorhandler( authentication.AuthenticationExceptions.UserNotAuthenticated )
async def _handle_user_not_authenticated( e ):
    return await make_response( jsonify({ "errors": [
        { "code": 0, "message": "Authorization has been denied for this request." }
    ] }), 401 )
    
@AvatarRoute.before_request
async def _is_csrf_required():
    if request.method != "POST":
        return
    if "roblox" not in request.user_agent.string.lower():
        return
    csrf_protect.protect()
    
@AvatarRoute.route("/v1/avatar-rules", methods=["GET"])
@remote_address_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _v1_avatar_rules():
    return await make_response( jsonify( avatar_rules.to_dict() ) )

@AvatarRoute.route("/v1/avatar", methods=["GET"])
@AvatarRoute.route("/v1/users/<int:user_id>/avatar", methods=["GET"])
@remote_address_limiter.limit("60/minute", deduct_when=lambda response: response.status_code == 200)
async def _v1_fetch_authenticated_avatar( user_id : int | None = None ):
    if user_id is None:
        target_user : User | None = await authentication.GetCurrentUser()
        if target_user is None:
            return await make_response( jsonify({ "errors": [
                { "code": 0, "message": "Authorization has been denied for this request." }
            ] }), 401 )
    else:
        target_user : User | None = User.query.filter_by( id = user_id ).first()
        if target_user is None or target_user.account_status == AccountStatus.GDPR_Deleted:
            return await make_response( jsonify({ "errors": [
                { "code": 1, "message": "The specified user does not exist." }
            ] }), 400 )
    target_user_avatar_obj : UserAvatar = await avatar.get_user_avatar_obj( target_user )
    user_avatar_items_list : list[UserAvatarItem] = await avatar.get_user_avatar_items( target_user, block_asset_types = [] )
    asset_and_assettype_ids : list[dict] = []
    user_avatar_hash : str = await avatar.generate_user_avatar_hash( target_user )
    user_equipped_emotes : list[UserAvatarEmote] = UserAvatarEmote.query.filter_by( user_id = target_user.id ).all()
    emotes : list[dict] = []
    
    for user_avatar_item in user_avatar_items_list:
        asset_obj : Asset = await assets.GetAssetById( user_avatar_item.asset_id )
        latest_asset_version : AssetVersion | None = await assets.GetLatestAssetVersion( user_avatar_item.asset_id )
        
        asset_and_assettype_ids.append({
            "id": user_avatar_item.asset_id,
            "name": asset_obj.name,
            "assetType": {
                "id": asset_obj.asset_type.value,
                "name": asset_obj.asset_type.name
            },
            "currentVersionId": latest_asset_version.id
        })
    
    for user_emote in user_equipped_emotes:
        asset_obj : Asset = await assets.GetAssetById( user_emote.emote_id )
        emotes.append({
            "assetId": user_emote.emote_id,
            "assetName": asset_obj.name,
            "position": user_emote.emote_position
        })
    
    return jsonify({
        "scales": {
            "height": target_user_avatar_obj.height_scale,
            "width": target_user_avatar_obj.width_scale,
            "head": target_user_avatar_obj.head_scale,
            "depth": 1,
            "proportion": target_user_avatar_obj.proportion_scale,
            "bodyType": target_user_avatar_obj.body_type_scale,
        },
        "playerAvatarType": target_user_avatar_obj.rig_type.name,
        "bodyColors": {
            "headColorId": target_user_avatar_obj.head_color_id,
            "leftArmColorId": target_user_avatar_obj.left_arm_color_id,
            "leftLegColorId": target_user_avatar_obj.left_leg_color_id,
            "rightArmColorId": target_user_avatar_obj.right_arm_color_id,
            "rightLegColorId": target_user_avatar_obj.right_leg_color_id,
            "torsoColorId": target_user_avatar_obj.torso_color_id,
        },
        "assets": asset_and_assettype_ids,
        "defaultShirtApplied": False,
        "defaultPantsApplied": False,
        "emotes": emotes,
        "avatar_hash": user_avatar_hash
    })

@AvatarRoute.route("/v1/users/<int:user_id>/currently-wearing", methods=["GET"])
@remote_address_limiter.limit("60/minute", deduct_when=lambda response: response.status_code == 200)
async def _v1_fetch_currently_wearing( user_id : int ):
    target_user : User | None = User.query.filter_by( id = user_id ).first()
    if target_user is None or target_user.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The specified user does not exist." }
        ] }), 400 )
    user_avatar_items_list : list[UserAvatarItem] = await avatar.get_user_avatar_items( target_user, block_asset_types = [], allow_moderated_items = True )
    return jsonify({ "assetIds": [ user_avatar_item.asset_id for user_avatar_item in user_avatar_items_list ] })

@AvatarRoute.route("/v1/avatar-fetch/", methods=["GET"])
@AvatarRoute.route("/v1/avatar-fetch", methods=["GET"])
async def _v1_avatar_fetch():
    req_place_id : int = request.args.get(
        key = "placeId",
        default = 0,
        type = int
    )
    req_user_id : int | None = request.args.get(
        key = "userId",
        default = None,
        type = int
    )
    requested_avatar_hash : str | None = request.args.get(
        key = "avatar_hash",
        default = None,
        type = str
    )
    if req_user_id is None and requested_avatar_hash is None:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The user is invalid." }
        ] }), 400 )
    
    if req_user_id is not None:
        target_user_obj : User | None = User.query.filter_by( id = req_user_id ).first()
        if target_user_obj is None and requested_avatar_hash is None:
            return await make_response( jsonify({ "errors": [
                { "code": 1, "message": "The user is invalid." }
            ] }), 400 )
    
    avatar_fetch_response : dict | None = await avatar.build_avatar_fetch_response(
        user_obj = target_user_obj,
        avatar_hash = requested_avatar_hash,
        block_asset_types = [ AssetType.Gear ] if req_place_id > 0 else []
    )
    if avatar_fetch_response is None:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "An error occurred while fetching the avatar." }
        ] }), 500 )
    
    return jsonify( avatar_fetch_response )

@AvatarRoute.route("/v1/avatar/set-player-avatar-type", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("25/minute", deduct_when=lambda response: response.status_code == 200)
async def _set_avatar_rig_type():
    try:
        assert request.is_json, "Unsupported Content-Type"
        payload_data : dict = await request.get_json()
        assert "playerAvatarType" in payload_data, "playerAvatarType is required"
        assert payload_data["playerAvatarType"] in ["R6", "R15"], "playerAvatarType is invalid or unsupported"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    authenticated_user : User = await authentication.GetCurrentUser()
    rig_type : RigType = RigType.R6 if payload_data["playerAvatarType"] == "R6" else RigType.R15
    await avatar.set_user_avatar_rig( user_obj = authenticated_user, rig_type = rig_type, render_thumbnail = True )
    user_avatar_hash : str = await avatar.generate_user_avatar_hash( authenticated_user )
    return jsonify({ "success": True, "avatar_hash": user_avatar_hash })

@AvatarRoute.route("/v1/avatar/set-scales", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("35/minute", deduct_when=lambda response: response.status_code == 200)
async def _set_avatar_scales():
    try:
        assert request.is_json, "Unsupported Content-Type"
        payload_data : dict = await request.get_json()
        assert "height" in payload_data, "height is required"
        assert "width" in payload_data, "width is required"
        assert "head" in payload_data, "head is required"
        assert "proportion" in payload_data, "proportion is required"
        assert "bodyType" in payload_data, "bodyType is required"
        assert isinstance( payload_data["height"], (int, float) ), "height must be a number"
        assert isinstance( payload_data["width"], (int, float) ), "width must be a number"
        assert isinstance( payload_data["head"], (int, float) ), "head must be a number"
        assert isinstance( payload_data["proportion"], (int, float) ), "proportion must be a number"
        assert isinstance( payload_data["bodyType"], (int, float) ), "bodyType must be a number"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        await avatar.set_user_avatar_scales(
            user_obj = authenticated_user,
            height_scale = payload_data["height"],
            width_scale = payload_data["width"],
            head_scale = payload_data["head"],
            proportion_scale = payload_data["proportion"],
            body_type_scale = payload_data["bodyType"],
            render_thumbnail = True
        )
    except avatar.InvalidAvatarScale as e:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": str(e) }
        ] }), 400 )
    
    user_avatar_hash : str = await avatar.generate_user_avatar_hash( authenticated_user )
    return jsonify({ "success": True, "avatar_hash": user_avatar_hash })

@AvatarRoute.route("/v1/avatar/set-body-colors", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("35/minute", deduct_when=lambda response: response.status_code == 200)
async def _set_avatar_body_colors():
    try:
        assert request.is_json, "Unsupported Content-Type"
        payload_data : dict = await request.get_json()
        assert "headColorId" in payload_data, "headColorId is required"
        assert "torsoColorId" in payload_data, "torsoColorId is required"
        assert "rightArmColorId" in payload_data, "rightArmColorId is required"
        assert "leftArmColorId" in payload_data, "leftArmColorId is required"
        assert "rightLegColorId" in payload_data, "rightLegColorId is required"
        assert "leftLegColorId" in payload_data, "leftLegColorId is required"
        assert isinstance( payload_data["headColorId"], int ), "headColorId must be a number"
        assert isinstance( payload_data["torsoColorId"], int ), "torsoColorId must be a number"
        assert isinstance( payload_data["rightArmColorId"], int ), "rightArmColorId must be a number"
        assert isinstance( payload_data["leftArmColorId"], int ), "leftArmColorId must be a number"
        assert isinstance( payload_data["rightLegColorId"], int ), "rightLegColorId must be a number"
        assert isinstance( payload_data["leftLegColorId"], int ), "leftLegColorId must be a number"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        await avatar.set_user_body_colors(
            user_obj = authenticated_user,
            head_color_id = payload_data["headColorId"],
            torso_color_id = payload_data["torsoColorId"],
            right_arm_color_id = payload_data["rightArmColorId"],
            left_arm_color_id = payload_data["leftArmColorId"],
            right_leg_color_id = payload_data["rightLegColorId"],
            left_leg_color_id = payload_data["leftLegColorId"],
            render_thumbnail = True
        )
    except avatar.InvalidBodyColor as e:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": str(e) }
        ] }), 400 )
    user_avatar_hash : str = await avatar.generate_user_avatar_hash( authenticated_user )
    return jsonify({ "success": True, "avatar_hash": user_avatar_hash })
        
@AvatarRoute.route("/v1/avatar/set-wearing-assets", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _set_avatar_wearing_assets():
    try:
        assert request.is_json, "Unsupported Content-Type"
        payload_data : dict = await request.get_json()
        assert "assetIds" in payload_data, "assetIds is required"
        assert isinstance( payload_data["assetIds"], list ), "assetIds must be a list"
        assert all( isinstance( asset_id, int ) for asset_id in payload_data["assetIds"] ), "assetIds must be a list of numbers"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    invalid_asset_ids : list[int] = await avatar.set_user_avatar_items( user_obj = authenticated_user, asset_ids = payload_data["assetIds"], render_thumbnail = True )
    user_avatar_hash : str = await avatar.generate_user_avatar_hash( authenticated_user )
    
    return jsonify({
        "success": True,
        "avatar_hash": user_avatar_hash,
        "invalidAssetIds": invalid_asset_ids
    })

@AvatarRoute.route("/v1/avatar/redraw-thumbnail", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("5/minute", deduct_when=lambda response: response.status_code == 200)
async def _redraw_avatar_thumbnail():
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        await thumbnailer.queue_full_user_render( user_obj = authenticated_user, clear_previous_thumbnails = True, bypass_cache = True, synchronous_queue = True )
    except thumbnailer.RenderServiceExceptions.ThumbnailRenderCooldown as e:
        return abort( 429 )
    return jsonify({ "success": True })

@AvatarRoute.route("/v1/emotes", methods=["GET"])
@authentication.require_authentication
@user_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _get_user_emotes():
    authenticated_user : User = await authentication.GetCurrentUser()
    user_emotes : list[UserAvatarEmote] = UserAvatarEmote.query.filter_by( user_id = authenticated_user.id ).all()
    emotes : list[dict] = []
    for user_emote in user_emotes:
        asset_obj : Asset = await assets.GetAssetById( user_emote.emote_id )
        emotes.append({
            "assetId": user_emote.emote_id,
            "assetName": asset_obj.name,
            "position": user_emote.emote_position
        })
    return jsonify({ "data": emotes })

@AvatarRoute.route("/v1/emotes/<int:emote_id>/<int:position>", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("35/minute", deduct_when=lambda response: response.status_code == 200)
async def _set_avatar_emote( emote_id: int, position: int ):
    if not position >= 1 and position <= 8:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "That emote position is invalid" }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    try:
        await avatar.set_user_emote( user_obj = authenticated_user, emote_id = emote_id, emote_position = position )
    except avatar.AssetCouldNotBeEquipped as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    return jsonify({ "success": True })

@AvatarRoute.route("/v1/emotes/<int:emote_position>", methods=["DELETE"])
@authentication.require_authentication
@user_limiter.limit("15/minute")
async def _remove_avatar_emote( emote_position: int ):
    authenticated_user : User = await authentication.GetCurrentUser()
    if not emote_position >= 1 and emote_position <= 8:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "That emote position is invalid" }
        ] }), 400 )
    try:
        await avatar.remove_user_emote( user_obj = authenticated_user, emote_position = emote_position )
    except Exception as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": "An error occurred while removing the emote" }
        ] }), 500 )
    return jsonify({ "success": True })

@AvatarRoute.route("/v1/users/<int:user_id>/outfits", methods=["GET"])
@remote_address_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _get_user_outfits( user_id : int ):
    target_user_obj : User | None = User.query.filter_by( id = user_id ).first()
    if target_user_obj is None or target_user_obj.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The user is invalid." }
        ] }), 400 )
    
    page_number : int = request.args.get( key = "page", default = 1, type = int )
    itemsPerPage : int = request.args.get( key = "itemsPerPage", default = 25, type = int )
    try:
        assert itemsPerPage >= 1 and itemsPerPage <= 25, "itemsPerPage must be between 1 and 25"
        assert page_number >= 1, "page must be greater than or equal to 1"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
        
    user_avatar_outfits : list[Outfit] = Outfit.query.filter_by( creator_user_id = target_user_obj.id ).paginate(
        page = page_number, per_page = itemsPerPage, error_out = False
    )
    outfits : list[dict] = []
    for outfit in user_avatar_outfits.items:
        outfits.append({
            "id": outfit.id,
            "name": outfit.outfit_name,
            "isEditable": True,
        })
    total_outfits : int = user_avatar_outfits.total
    return jsonify({ "data": outfits, "total": total_outfits, "next_page": user_avatar_outfits.next_num })

@AvatarRoute.route("/v1/outfits/<int:outfit_id>/details", methods=["GET"])
@remote_address_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _get_outfit_details( outfit_id : int ):
    outfit_obj : Outfit | None = Outfit.query.filter_by( id = outfit_id ).first()
    if outfit_obj is None:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The specified userOutfitId is invalid." }
        ] }), 400 )
    
    outfit_items : list[OutfitItem] = OutfitItem.query.filter_by( outfit_id = outfit_obj.id ).all()
    asset_items : list[dict] = []
    for outfit_item in outfit_items:
        asset_obj : Asset = await assets.GetAssetById( outfit_item.asset_id )
        latest_asset_version : AssetVersion | None = await assets.GetLatestAssetVersion( outfit_item.asset_id )
        asset_items.append({
            "id": outfit_item.asset_id,
            "name": asset_obj.name,
            "assetType": {
                "id": asset_obj.asset_type.value,
                "name": asset_obj.asset_type.name
            },
            "currentVersionId": latest_asset_version.id
        })
    return jsonify({
        "id": outfit_obj.id,
        "name": outfit_obj.outfit_name,
        "assets": asset_items,
        "bodyColors": {
            "headColorId": outfit_obj.head_color_id,
            "torsoColorId": outfit_obj.torso_color_id,
            "rightArmColorId": outfit_obj.right_arm_color_id,
            "leftArmColorId": outfit_obj.left_arm_color_id,
            "rightLegColorId": outfit_obj.right_leg_color_id,
            "leftLegColorId": outfit_obj.left_leg_color_id
        },
        "scale": {
            "height": outfit_obj.height_scale,
            "width": outfit_obj.width_scale,
            "head": outfit_obj.head_scale,
            "proportion": outfit_obj.proportion_scale,
            "bodyType": outfit_obj.body_type_scale,
            "depth": 1
        },
        "playerAvatarType": outfit_obj.rig_type.name,
        "isEditable": True
    })
    
@AvatarRoute.route("/v1/outfits/<int:outfit_id>/delete", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("10/minute", deduct_when=lambda response: response.status_code == 200)
async def _delete_outfit( outfit_id : int ):
    outfit_obj : Outfit | None = Outfit.query.filter_by( id = outfit_id ).first()
    if outfit_obj is None:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The specified userOutfitId is invalid." }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    if outfit_obj.creator_user_id != authenticated_user.id:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "You do not have permission to delete this outfit." }
        ] }), 403 )
    
    try:
        await avatar.delete_outfit( outfit_obj )
    except Exception as e:
        return await make_response( jsonify({ "errors": [
            { "code": 3, "message": "An error occurred while deleting the outfit." }
        ] }), 500 )
        
    return jsonify({ "success": True })

@AvatarRoute.route("/v1/outfits/create", methods=["POST"])
@AvatarRoute.route("/v1/outfits/<int:outfit_id>/update", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("5/minute", deduct_when=lambda response: response.status_code == 200)
async def _create_outfit( outfit_id : int | None = None ):
    if not request.is_json:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": "Unsupported Content-Type" }
        ] }), 400 )
    payload_data : dict = await request.get_json()
    try:
        assert "name" in payload_data, "name is required"
        assert "bodyColors" in payload_data, "bodyColors is required"
        assert "assetIds" in payload_data, "assetIds is required"
        assert "scale" in payload_data, "scale is required"
        assert "playerAvatarType" in payload_data, "playerAvatarType is required"
        assert isinstance( payload_data["name"], str ), "name must be a string"
        assert isinstance( payload_data["bodyColors"], dict ), "bodyColors must be a dictionary"
        assert isinstance( payload_data["assetIds"], list ), "assetIds must be a list"
        assert isinstance( payload_data["scale"], dict ), "scale must be a dictionary"
        bodyColors : dict = payload_data["bodyColors"]
        scaleSettings : dict = payload_data["scale"]
        assetIds : list = payload_data["assetIds"]
        outfit_name : str = payload_data["name"]
        assert all( isinstance( asset_id, int ) for asset_id in assetIds ), "assetIds must be a list of numbers"
        assert "headColorId" in bodyColors, "headColorId is required"
        assert "torsoColorId" in bodyColors, "torsoColorId is required"
        assert "rightArmColorId" in bodyColors, "rightArmColorId is required"
        assert "leftArmColorId" in bodyColors, "leftArmColorId is required"
        assert "rightLegColorId" in bodyColors, "rightLegColorId is required"
        assert "leftLegColorId" in bodyColors, "leftLegColorId is required"
        assert "height" in scaleSettings, "height is required"
        assert "width" in scaleSettings, "width is required"
        assert "head" in scaleSettings, "head is required"
        assert "proportion" in scaleSettings, "proportion is required"
        assert "bodyType" in scaleSettings, "bodyType is required"
        assert isinstance( bodyColors["headColorId"], int ), "headColorId must be a number"
        assert isinstance( bodyColors["torsoColorId"], int ), "torsoColorId must be a number"
        assert isinstance( bodyColors["rightArmColorId"], int ), "rightArmColorId must be a number"
        assert isinstance( bodyColors["leftArmColorId"], int ), "leftArmColorId must be a number"
        assert isinstance( bodyColors["rightLegColorId"], int ), "rightLegColorId must be a number"
        assert isinstance( bodyColors["leftLegColorId"], int ), "leftLegColorId must be a number"
        assert isinstance( scaleSettings["height"], (int, float) ), "height must be a number"
        assert isinstance( scaleSettings["width"], (int, float) ), "width must be a number"
        assert isinstance( scaleSettings["head"], (int, float) ), "head must be a number"
        assert isinstance( scaleSettings["proportion"], (int, float) ), "proportion must be a number"
        assert isinstance( scaleSettings["bodyType"], (int, float) ), "bodyType must be a number"
        assert len( outfit_name ) <= 40, "name must be less than or equal to 40 characters"
        assert len( outfit_name ) >= 3, "name must be greater than or equal to 3 characters"
    except AssertionError as e:
        return await make_response( jsonify({ "errors": [
            { "code": 0, "message": str(e) }
        ] }), 400 )
    
    try:
        text_moderation.filter_text( text_to_filter = outfit_name, raise_exception = True )
    except text_moderation.TextNotAllowed as e:
        return await make_response( jsonify({ "errors": [
            { "code": 4, "message": "Invalid outfit name" }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    if outfit_id is not None:
        target_outfit_obj : Outfit | None = Outfit.query.filter_by( id = outfit_id ).first()
        if target_outfit_obj is None:
            return await make_response( jsonify({ "errors": [
                { "code": 1, "message": "The specified userOutfit does not exist!" }
            ] }), 400 )
        if target_outfit_obj.creator_user_id != authenticated_user.id:
            return await make_response( jsonify({ "errors": [
                { "code": 2, "message": "You do not have permission to update this outfit." }
            ] }), 403 )
    
    try:
        await avatar.verify_user_avatar_colors(
            head_color_id = bodyColors["headColorId"],
            torso_color_id = bodyColors["torsoColorId"],
            right_arm_color_id = bodyColors["rightArmColorId"],
            left_arm_color_id = bodyColors["leftArmColorId"],
            right_leg_color_id = bodyColors["rightLegColorId"],
            left_leg_color_id = bodyColors["leftLegColorId"]
        )
    except avatar.InvalidBodyColor as e:
        return await make_response( jsonify({ "errors": [
            { "code": 3, "message": "Body colors must be valid BrickColor IDs" }
        ] }), 400 )
    
    try:
        await avatar.verify_user_avatar_scaling(
            height_scale = scaleSettings["height"],
            width_scale = scaleSettings["width"],
            head_scale = scaleSettings["head"],
            proportion_scale = scaleSettings["proportion"],
            body_type_scale = scaleSettings["bodyType"]
        )
    except avatar.InvalidAvatarScale as e:
        return await make_response( jsonify({ "errors": [
            { "code": 4, "message": "Avatar scaling is invalid" }
        ] }), 400 )
    
    if payload_data["playerAvatarType"] not in ["R6", "R15"]:
        return await make_response( jsonify({ "errors": [
            { "code": 7, "message": "Invalid Player Avatar Type. Valid types are R6 and R15" }
        ] }), 400 )
    
    try:
        await avatar.verify_user_avatar_items( user_obj = authenticated_user, asset_ids = assetIds, raise_exception_on_invalid_asset = True )
    except avatar.AssetCouldNotBeEquipped as e:
        return await make_response( jsonify({ "errors": [
            { "code": 5, "message": "Asset is not wearable by you and was not added to the outfit" }
        ] }), 400 )
    
    rig_type : RigType = RigType.R6 if payload_data["playerAvatarType"] == "R6" else RigType.R15
    if outfit_id is not None:
        try:
            await avatar.update_outfit(
                outfit_obj = target_outfit_obj,
                outfit_name = outfit_name,
                head_color_id = bodyColors["headColorId"],
                torso_color_id = bodyColors["torsoColorId"],
                right_arm_color_id = bodyColors["rightArmColorId"],
                left_arm_color_id = bodyColors["leftArmColorId"],
                right_leg_color_id = bodyColors["rightLegColorId"],
                left_leg_color_id = bodyColors["leftLegColorId"],
                
                height_scale = scaleSettings["height"],
                width_scale = scaleSettings["width"],
                head_scale = scaleSettings["head"],
                proportion_scale = scaleSettings["proportion"],
                body_type_scale = scaleSettings["bodyType"],
                
                rig_type = rig_type,
                equipped_asset_ids = assetIds
            )
        except Exception as e:
            return await make_response( jsonify({ "errors": [
                { "code": 6, "message": "An error occurred while updating the outfit" }
            ] }), 500 )
        return jsonify({ "success": True, "outfitId": target_outfit_obj.id })
    else:
        try:
            new_outfit : Outfit = await avatar.create_outfit(
                creator_user = authenticated_user,
                outfit_name = outfit_name,
                head_color_id = bodyColors["headColorId"],
                torso_color_id = bodyColors["torsoColorId"],
                right_arm_color_id = bodyColors["rightArmColorId"],
                left_arm_color_id = bodyColors["leftArmColorId"],
                right_leg_color_id = bodyColors["rightLegColorId"],
                left_leg_color_id = bodyColors["leftLegColorId"],
                
                height_scale = scaleSettings["height"],
                width_scale = scaleSettings["width"],
                head_scale = scaleSettings["head"],
                proportion_scale = scaleSettings["proportion"],
                body_type_scale = scaleSettings["bodyType"],
                
                rig_type = rig_type,
                equipped_asset_ids = assetIds
            )
        except Exception as e:
            return await make_response( jsonify({ "errors": [
                { "code": 6, "message": "An error occurred while creating the outfit" }
            ] }), 500 )
        
        return jsonify({ "success": True, "outfitId": new_outfit.id })
    
@AvatarRoute.route("/v1/outfits/<int:outfit_id>/wear", methods=["POST"])
@authentication.require_authentication
@user_limiter.limit("15/minute", deduct_when=lambda response: response.status_code == 200)
async def _wear_outfit( outfit_id : int ):
    outfit_obj : Outfit | None = Outfit.query.filter_by( id = outfit_id ).first()
    if outfit_obj is None:
        return await make_response( jsonify({ "errors": [
            { "code": 1, "message": "The specified userOutfitId is invalid." }
        ] }), 400 )
    
    authenticated_user : User = await authentication.GetCurrentUser()
    if outfit_obj.creator_user_id != authenticated_user.id:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "You do not have permission to wear this outfit." }
        ] }), 403 )
    
    try:
        removed_assets : list[Asset] = await avatar.wear_outfit( target_user = authenticated_user, outfit_obj = outfit_obj )
    except avatar.AssetCouldNotBeEquipped as e:
        return await make_response( jsonify({ "errors": [
            { "code": 2, "message": "An error occurred while equipping the outfit." }
        ] }), 500 )
    invalid_assets : list[dict] = []
    for asset_obj in removed_assets:
        invalid_assets.append({
            "id": asset_obj.id,
            "name": asset_obj.name,
            "assetType": {
                "id": asset_obj.asset_type.value,
                "name": asset_obj.asset_type.name
            }
        })
    return jsonify({
        "invalidAssets": invalid_assets,
        "invalidAssetIds": [ asset_obj.id for asset_obj in removed_assets ],
        "success": True
    })