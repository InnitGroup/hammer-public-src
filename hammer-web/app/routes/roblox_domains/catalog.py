"""
    catalog.roblox.com
"""

from quart import Blueprint, request, make_response, jsonify, abort

from app.services import authentication, assets
from app.models.asset import Asset
from app.models.asset_version import AssetVersion
from app.models.bundle import Bundle
from app.models.bundle_item import BundleItem
from app.enums.AssetType import AssetType
from app.util.obj_builder import build_creator_obj
from app.extensions import remote_address_limiter

CatalogRoute = Blueprint('catalog_roblox', __name__, url_prefix='/', subdomain='catalog')

@CatalogRoute.errorhandler(429)
async def _rate_limit_handler(e):
    return await make_response(
        jsonify({ "errors": [
            { "code": 7, "message": "Too many attempts. Please wait a bit."}
        ] }),
        429
    )
@CatalogRoute.errorhandler( 503 )
async def _service_unavailable_handler(e):
    return await make_response(
        jsonify({ "errors": [
            { "code": 11, "message": "Service unavailable. Please try again later."}
        ] }),
        503
    )

@CatalogRoute.route("/v1/bundles/<int:bundleId>/details", methods = ["GET"] )
@remote_address_limiter.limit("60/minute", deduct_when = lambda response: response.status_code != 200)
@remote_address_limiter.limit("30/minute", deduct_when = lambda response: response.status_code == 200)
async def _bundle_details( bundleId : int ):
    bundleObj : Bundle | None = Bundle.query.filter_by( id = bundleId ).first()
    if bundleObj is None:
        return await make_response(
            jsonify({ "errors": [
                { "code": 1, "message": "Invalid bundle"}
            ] }),
            400
        )
    bundleItems : list[BundleItem] = BundleItem.query.filter_by( bundle_id = bundleId ).all()
    bundleItemsList : list[dict] = []
    for bundleItem in bundleItems:
        assetObj : Asset = await assets.GetAssetById( bundleItem.asset_id )
        if assetObj is None:
            continue
        bundleItemsList.append({
            "id": assetObj.id,
            "name": assetObj.name,
            "type": "Asset"
        })
    
    return await make_response(jsonify({
        "id": bundleObj.id,
        "name": bundleObj.name,
        "description": bundleObj.description,
        "bundleType": bundleObj.bundle_type.name,
        "items": bundleItemsList,
        "creator": await build_creator_obj( bundleObj.creator_id, bundleObj.creator_type )
    }), 200)