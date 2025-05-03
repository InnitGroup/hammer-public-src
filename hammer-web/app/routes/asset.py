import logging

from quart import request, make_response, Blueprint, jsonify, redirect
from app.extensions import get_remote_address
from app.services import authentication, assets
from app.models.asset import Asset
from app.models.asset_version import AssetVersion
from app.models.gameserver import GameServer
from app.enums.AssetType import AssetType
from app.enums.ModerationStatus import ModerationStatus
from config import Config

web_config = Config()

AssetRoute = Blueprint('asset', __name__, url_prefix='/')

class AssetRouteExceptions():
    class MissingParameter(Exception):
        pass
    class InvalidParameter(Exception):
        pass
    class AssetDoesNotExist(Exception):
        pass
    class AssetIsModerated(Exception):
        pass
    class PermissionDenied(Exception):
        pass
    class AssetMigrationBlocked(Exception):
        pass
    class InternalServiceError(Exception):
        pass
    class AssetVersionDoesNotExist(Exception):
        pass

@AssetRoute.errorhandler( AssetRouteExceptions.MissingParameter )
async def _handle_missing_parameter( e ):
    return await make_response(
        jsonify({ "status": 0, "message": "Missing parameter" }),
        400
    )
@AssetRoute.errorhandler( AssetRouteExceptions.InvalidParameter )
async def _handle_invalid_parameter( e ):
    return await make_response(
        jsonify({ "status": 0, "message": "Invalid parameter" }),
        400
    )

@AssetRoute.errorhandler( AssetRouteExceptions.AssetVersionDoesNotExist )
async def _handle_asset_version_does_not_exist( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "Asset version does not exist" }),
        404
    )
    
@AssetRoute.errorhandler( AssetRouteExceptions.AssetDoesNotExist )
async def _handle_asset_does_not_exist( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "Asset does not exist" }),
        404
    )
@AssetRoute.errorhandler( AssetRouteExceptions.AssetIsModerated )
async def _handle_asset_is_moderated( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "Asset is moderated or pending moderation" }),
        403
    )
@AssetRoute.errorhandler( AssetRouteExceptions.PermissionDenied )
async def _handle_permission_denied( e ):
    return await make_response(
        jsonify({ "status": 2, "message": "You are not authorised to access this asset" }),
        403
    )
@AssetRoute.errorhandler( AssetRouteExceptions.AssetMigrationBlocked )
async def _handle_asset_migration_blocked( e ):
    return await make_response(
        jsonify({ "status": 3, "message": "Asset migration is blocked for this asset" }),
        403
    )
@AssetRoute.errorhandler( assets.AssetServiceExceptions.InternalServiceError )
async def _handle_internal_service_error( e ):
    return await make_response(
        jsonify({ "status": 4, "message": "Internal Service Error raised during asset migration, please try again later" }),
        500
    )
@AssetRoute.errorhandler( AssetRouteExceptions.InternalServiceError )
async def _handle_internal_service_error( e ):
    return await make_response(
        jsonify({ "status": 4, "message": "Internal Service Error, please try again later" }),
        500
    )


@AssetRoute.route("/v1/asset/", methods=["GET"], subdomain = "assetdelivery")
@AssetRoute.route("/v1/asset", methods=["GET"], subdomain = "assetdelivery")
@AssetRoute.route("/Asset/", methods = ["GET"], subdomain = "www")
@AssetRoute.route("/Asset", methods = ["GET"], subdomain = "www")
@AssetRoute.route("/asset/", methods = ["GET"], subdomain = "www")
@AssetRoute.route("/asset", methods = ["GET"], subdomain = "www")
async def _get_asset():
    RequestedAssetId : int | None = request.args.get( key = "id", default = None, type = int )
    RequestedAssetVersion : int | None = request.args.get( key = "version", default = None, type = int )
    RequestedassetVersionId : int | None = request.args.get( key = "assetVersionId", default = None, type = int ) or request.args.get( key = "assetversionid", default = None, type = int )
    
    RequesterRbxGameId : str | None = request.headers.get( key = "Roblox-Game-Id", default = None, type = str )
    RequesterRbxPlaceId : int | None = request.headers.get( key = "Roblox-Place-Id", default = None, type = int )
    
    if RequestedAssetId is None and RequestedassetVersionId is None:
        raise AssetRouteExceptions.MissingParameter("Missing parameter")
    if RequestedAssetId is not None:
        if RequestedAssetId < 1:
            raise AssetRouteExceptions.InvalidParameter("Invalid parameter 'id'")
        AssetObj : Asset | None = Asset.query.filter_by(
            id = RequestedAssetId
        ).first()
    elif RequestedassetVersionId is not None:
        if RequestedassetVersionId < 1:
            raise AssetRouteExceptions.InvalidParameter("Invalid parameter 'assetVersionId'")
        AssetVersionObj : AssetVersion | None = AssetVersion.query.filter_by(
            id = RequestedassetVersionId
        ).first()
        if AssetVersionObj is None:
            raise AssetRouteExceptions.AssetDoesNotExist("Asset does not exist")
        AssetObj : Asset = Asset.query.filter_by(
            id = AssetVersionObj.asset_id
        ).first()

    if AssetObj is None:
        try:
            AssetObj = await assets.MigrateAsset(
                AssetId = RequestedAssetId,
                KeepAssetInfo = True,
                KeepRobloxAssetId = True,
                RenderAssetThumbnail = False
            )
        except assets.AssetServiceExceptions.AssetDoesNotExistOnRoblox:
            raise AssetRouteExceptions.AssetDoesNotExist("Asset does not exist")
        except assets.AssetServiceExceptions.AssetMigrationBlocked:
            raise AssetRouteExceptions.AssetMigrationBlocked("Asset migration is blocked for this asset")
        except assets.AssetServiceExceptions.AssetTypeNotAllowed:
            raise AssetRouteExceptions.AssetMigrationBlocked("Asset migration is blocked for this asset")
        except assets.AssetServiceExceptions.InternalServiceError as e:
            raise e
        except Exception as e:
            logging.error( f"routes.asset > _get_asset, exception raised: {e}" )
            raise AssetRouteExceptions.InternalServiceError("Failed to migrate asset")
        
    isCachingAllowed : bool = True
    isScriptInsert = request.args.get( key = 'scriptinsert', type = int, default = 0 ) == 1
    isClientInsert = request.args.get( key = 'clientinsert', type = int, default = 0 ) == 1
    isAuthenticatedGameserver : bool = await authentication.GetCurrentGameServer() is not None

    if AssetObj.moderation_status != ModerationStatus.Approved or AssetObj.asset_type == AssetType.Place:
        isCachingAllowed = False

    if AssetObj.moderation_status != ModerationStatus.Approved and ( not isAuthenticatedGameserver or isScriptInsert or isClientInsert):
        raise AssetRouteExceptions.AssetIsModerated("Asset is moderated or pending moderation")
    
    if AssetObj.asset_type == AssetType.Place and ( not isAuthenticatedGameserver or isScriptInsert or isClientInsert):
        raise AssetRouteExceptions.PermissionDenied("You are not authorised to access this asset")
    
    if RequestedAssetVersion is not None:
        SelectedAssetVersionObj : AssetVersion | None = await assets.GetAssetVersionByVersionNumber(
            AssetObj = AssetObj,
            VersionNumber = RequestedAssetVersion
        )
        if SelectedAssetVersionObj is None:
            raise AssetRouteExceptions.AssetVersionDoesNotExist("Asset version does not exist")
    else:
        SelectedAssetVersionObj : AssetVersion | None = await assets.GetLatestAssetVersion( AssetObj = AssetObj )
    if SelectedAssetVersionObj is None:
        logging.error( f"routes.asset > _get_asset, failed to fetch asset version for asset {AssetObj.id}" )
        raise AssetRouteExceptions.InternalServiceError("Failed to fetch asset version")
    
    redirect_response = await make_response(
        redirect( f"{web_config.CDN_URL}/{SelectedAssetVersionObj.content_hash}" ),
        301
    )

    if isCachingAllowed:
        redirect_response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        redirect_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        redirect_response.headers["Pragma"] = "no-cache"
        redirect_response.headers["Expires"] = "0"

    return redirect_response
