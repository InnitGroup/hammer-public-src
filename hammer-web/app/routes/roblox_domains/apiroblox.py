"""
    api.roblox.com 
    apis.roblox.com
"""
import random

from quart import Blueprint, request, jsonify, make_response
from app.extensions import csrf_protect
from app.services import authentication, groups
from app.services.economy.purchase import GetProductById
from app.services.economy.balance import GetTargetEconomyObject
from app.util.obj_builder import build_datetime_obj

from app.models.user import User
from app.models.universe import Universe
from app.models.place import Place
from app.models.groups import GroupRole, Group, GroupRolePermission
from app.models.asset import Asset
from app.models.product import Product
from app.models.user_economy import UserEconomy
from app.enums.PlaceRigChoice import PlaceRigChoice
from app.enums.CreatorType import CreatorType

APIRobloxRoute = Blueprint('api_roblox', __name__, url_prefix='/', subdomain='api')
APIssRobloxRoute = Blueprint('apis_roblox', __name__, url_prefix='/', subdomain='apis') # why must there be two api subdomains?

@APIRobloxRoute.route('/device/initialize', methods=['POST'])
@csrf_protect.exempt
async def _device_initialize():
    return await make_response(
        jsonify({"browserTrackerId" : random.randint(100000000,9999999999), "appDeviceIdentifier" : None}),
        200
    )

EnumTogameAvatarType = {
    PlaceRigChoice.UserChoice: "PlayerChoice",
    PlaceRigChoice.ForceR6: "MorphToR6",
    PlaceRigChoice.ForceR15: "MorphToR15"
}

@APIRobloxRoute.route("/marketplace/productinfo", methods=["GET"])
async def _marketplace_info():
    requested_assetid = request.args.get("assetId", type = int, default = None)
    if requested_assetid is None:
        return jsonify({ "errors": [ { "code": 1, "message": "Invalid assetId" } ] }), 400
    asset_obj : Asset | None = Asset.query.filter_by( id = requested_assetid ).first()
    if asset_obj is None:
        return jsonify({ "errors": [ { "code": 1, "message": "Invalid assetId" } ] }), 400
    asset_product_obj : Product = await GetProductById( asset_obj.product_id )
    creator_name = "Unknown"
    if asset_obj.creator_type == CreatorType.User:
        creator_user_obj : User | None = User.query.filter_by( id = asset_obj.creator_id ).first()
        if creator_user_obj is not None:
            creator_name = creator_user_obj.username
    else:
        creator_group : Group | None = groups.GetGroupFromId( asset_obj.creator_id )
        if creator_group is not None:
            creator_name = creator_group.name
    return jsonify({
        "Name": asset_obj.name,
        "Description": asset_obj.description,
        "Created": build_datetime_obj( asset_obj.created_at ),
        "Updated": build_datetime_obj( asset_obj.updated_at ),
        "PriceInRobux": asset_product_obj.price_in_robux,
        "PriceInTickets": asset_product_obj.price_in_tickets,
        "AssetId": asset_obj.id,
        "ProductId": asset_product_obj.id,
        "AssetTypeId": asset_obj.asset_type.value,
        "Creator": {
            "Id": asset_obj.creator_id,
            "Name": creator_name,
            "CreatorType": asset_obj.creator_type.value
        },
        "MinimumMembershipLevel": asset_product_obj.minimum_membership_level.value,
        "IsForSale": asset_product_obj.is_for_sale
    })

@APIRobloxRoute.route("/universes/validate-place-join", methods=["GET"])
async def _validate_place_join():
    return "true"

@APIRobloxRoute.route("/users/<int:userId>/canmanage/<int:placeId>", methods=["GET"])
async def _user_can_manage(userId: int, placeId: int):
    target_user_obj : User | None = User.query.filter_by( id = userId ).first()
    if target_user_obj is None:
        return jsonify({ "Success": True, "CanManage": False }), 200
    target_place_obj : Place | None = Place.query.filter_by( place_id = placeId ).first()
    if target_place_obj is None:
        return jsonify({ "Success": True, "CanManage": False }), 200
    parent_universe_obj : Universe | None = Universe.query.filter_by( id = target_place_obj.parent_universe_id ).first()
    if parent_universe_obj is None:
        return jsonify({ "Success": True, "CanManage": False }), 200
    if parent_universe_obj.creator_type == CreatorType.User:
        if parent_universe_obj.creator_id == userId:
            return jsonify({ "Success": True, "CanManage": True }), 200
    else:
        owner_group : Group | None = groups.GetGroupFromId( parent_universe_obj.creator_id )
        if owner_group is None:
            return jsonify({ "Success": True, "CanManage": False }), 200
        target_group_role : GroupRole = groups.GetUserRolesetInGroup( target_user_obj, owner_group )
        role_permissions : GroupRolePermission = groups.GetRolesetPermission( target_group_role )
        if role_permissions.manage_group_games:
            return jsonify({ "Success": True, "CanManage": True }), 200
    return jsonify({ "Success": True, "CanManage": False }), 200

@APIRobloxRoute.route("/game/players/<int:userId>/", methods=["GET"])
async def game_players(userId: int):
    return jsonify({
        "ChatFilter": "whitelist"
    })

@APIRobloxRoute.route("/v1.1/game-start-info/")
async def game_start_info():
    requesting_universeid : int | None = request.args.get("universeId", default = None, type = int)
    if requesting_universeid is None:
        return jsonify({
            "message": "Invalid request",
            "success": False
        }), 400
    universe_obj : Universe | None = Universe.query.filter_by(id = requesting_universeid).first()
    if universe_obj is None:
        return jsonify({
            "message": "Place not found",
            "success": False
        }), 404
    root_place_obj : Place | None = Place.query.filter_by( place_id = universe_obj.root_place_id ).first()

    return jsonify({
        "gameAvatarType": EnumTogameAvatarType[root_place_obj.rig_choice],
        "allowCustomAnimations":"True",
        "universeAvatarCollisionType":"OuterBox",
        "universeAvatarBodyType":"Standard",
        "jointPositioningType":"ArtistIntent",
        "message":"",
        "universeAvatarMinScales":{
            "height":0.9,
            "width":0.7,
            "head":0.95,
            "depth":0.0,
            "proportion":0.0,
            "bodyType":0.0
        },
        "universeAvatarMaxScales":{
            "height":1.05,
            "width":1.0,
            "head":1.0,
            "depth":0.0,
            "proportion":1.0,
            "bodyType":1.0
        },
        "universeAvatarAssetOverrides":[],
        "moderationStatus":None
    })

@APIRobloxRoute.route("/users/account-info", methods=["GET"])
@authentication.require_authentication
async def _get_account_info():
    authenticated_user : User = await authentication.GetCurrentUser()
    user_economy_obj : UserEconomy = await GetTargetEconomyObject( authenticated_user )
    return jsonify({
        "UserId": authenticated_user.id,
        "Username": authenticated_user.username,
        "DisplayName": authenticated_user.username,
        "HasPasswordSet": True,
        "Email": None,
        "MembershipType": "None",
        "RobuxBalance": user_economy_obj.robux_bal,
        "AgeBracket": 0,
        "Roles": [],
        "EmailNotificationEnabled": False,
        "PasswordNotificationEnabled": False
    })

@APIssRobloxRoute.route("/universal-app-configuration/v1/behaviors/app-policy/content", methods=["GET"])
async def _get_app_policy_content():
    return await make_response(
        jsonify({
        "ChatConversationHeaderGroupDetails": True,
        "ChatHeaderSearch": True,
        "ChatHeaderCreateChatGroup": True,
        "ChatHeaderHomeButton": False,
        "ChatHeaderNotifications": True,
        "ChatPlayTogether": True,
        "ChatShareGameToChatFromChat": True,
        "ChatTapConversationThumbnail": True,
        "ChatViewProfileOption": True,
        "GamesDropDownList": True,
        "UseNewDropDown": False,
        "GameDetailsMorePage": True,
        "GameDetailsShowGlobalCounters": True,
        "GameDetailsPlayWithFriends": True,
        "GameDetailsSubtitle": True,
        "GameInfoList": True,
        "GameInfoListDeveloper": True,
        "GamePlaysAndRatings": True,
        "GameInfoShowBadges": True,
        "GameInfoShowCreated": True,
        "GameInfoShowGamepasses": True,
        "GameInfoShowGenre": True,
        "GameInfoShowMaxPlayers": True,
        "GameInfoShowServers": True,
        "GameInfoShowUpdated": True,
        "GameReportingDisabled": False,
        "GamePlayerCounts": True,
        "GiftCardsEnabled": False,
        "Notifications": True,
        "OfficialStoreEnabled": False,
        "RecommendedGames": True,
        "SearchBar": True,
        "MorePageType": "More",
        "AboutPageType": "About",
        "FriendFinder": True,
        "SocialLinks": True,
        "SocialGroupLinks": True,
        "EnableShareCaptureCTA": True,
        "SiteMessageBanner": True,
        "UseWidthBasedFormFactorRule": False,
        "UseHomePageWithAvatarAndPanel": False,
        "UseBottomBar": True,
        "AvatarHeaderIcon": "LuaApp/icons/ic-back",
        "AvatarEditorShowBuyRobuxOnTopBar": True,
        "HomeIcon": "LuaApp/icons/ic-roblox-close",
        "ShowYouTubeAgeAlert": False,
        "GameDetailsShareButton": True,
        "CatalogShareButton": True,
        "AccountProviderName": "",
        "InviteFromAccountProvider": False,
        "ShareToAccountProvider": False,
        "ShareToAccountProviderTimeout": 8,
        "ShowDisplayName": True,
        "GamesPageCreationCenterTitle": False,
        "ShowShareTargetGameCreator": True,
        "SearchAutoComplete": True,
        "CatalogShow3dView": True,
        "CatalogReportingDisabled": False,
        "CatalogCommunityCreations": True,
        "CatalogPremiumCategory": True,
        "CatalogPremiumContent": True,
        "ItemDetailsFullView": True,
        "UseAvatarExperienceLandingPage": True,
        "HomePageFriendSection": True,
        "HomePageProfileLink": True,
        "PurchasePromptIncludingWarning": False,
        "ShowVideoThumbnails": True,
        "VideoSharingTestContent": [],
        "SystemBarPlacement": "Bottom",
        "EnableInGameHomeIcon": False,
        "UseExternalBrowserForDisclaimerLinks": False,
        "ShowExitFullscreenToast": True,
        "ExitFullscreenToastEnabled": False,
        "UseLuobuAuthentication": False,
        "CheckUserAgreementsUpdatedOnLogin": True,
        "AddUserAgreementIdsToSignupRequest": True,
        "UseOmniRecommendation": True,
        "ShowAgeVerificationOverlayEnabled": False,
        "ShouldShowGroupsTile": True,
        "ShowVoiceUpsell": False,
        "ProfileShareEnabled": True,
        "ContactImporterEnabled": True,
        "FriendCodeQrCodeScannerEnabled": False,
        "RealNamesInDisplayNamesEnabled": False,
        "CsatSurveyRestrictTextInput": False,
        "RobloxCreatedItemsCreatedByLuobu": False,
        "GameInfoShowChatFeatures": True,
        "PlatformGroup": "Unknown",
        "UsePhoneSearchDiscoverEntry": False,
        "HomeLocalFeedItems": {
            "UserInfo": 1,
            "FriendCarousel": 2
        },
        "Routes": {
            "auth": {
                "connect": "v2/login",
                "login": "v2/login",
                "signup": "v2/signup"
            }
        },
        "PromotionalEmailsCheckboxEnabled": True,
        "PromotionalEmailsOptInByDefault": False,
        "EnablePremiumUserFeatures": True,
        "CanShowUnifiedChatUpsell": True,
        "RequireExplicitVoiceConsent": True,
        "RequireExplicitAvatarVideoConsent": True,
        "EnableVoiceReportAbuseMenu": True
    }),
        200
    )