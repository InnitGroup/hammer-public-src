"""
    inventory.roblox.com
"""

from quart import Blueprint, request, make_response, jsonify
from app.extensions import remote_address_limiter
from app.services import authentication, cursor, assets
from app.util.obj_builder import build_datetime_obj
from app.services import privacy, authentication

from app.models.user import User
from app.models.user_asset import UserAsset
from app.models.asset import Asset
from app.enums.AssetType import AssetType
from app.enums.AccountStatus import AccountStatus

InventoryAPIRoute = Blueprint('inventory_roblox', __name__, url_prefix='/', subdomain='inventory')

@InventoryAPIRoute.route("/v1/users/<int:user_id>/can-view-inventory", methods=["GET"])
@remote_address_limiter.limit("100/minute", deduct_when=lambda response: response.status_code == 200)
async def _can_view_inventory( user_id : int ):
    target_user_obj : User | None = authentication.get_user_by_id( user_id, return_none_on_deleted = True )
    if target_user_obj is None or target_user_obj.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "The user is invalid or does not exist." } ] }), 400 )
    
    authenticated_user : User | None = await authentication.GetCurrentUser()
    can_view_inventory : bool = await privacy.can_view_inventory( target_user_obj, authenticated_user )
    
    return await make_response( jsonify({ "canView": can_view_inventory }), 200 )

@InventoryAPIRoute.route("/v2/users/<int:user_id>/inventory/<int:asset_type>", methods=["GET"])
@remote_address_limiter.limit("70/minute", deduct_when=lambda response: response.status_code == 200)
async def _get_user_inventory_by_assettype( user_id : int, asset_type : int ):
    target_user_obj : User | None = authentication.get_user_by_id( user_id, return_none_on_deleted = True )
    if target_user_obj is None or target_user_obj.account_status == AccountStatus.GDPR_Deleted:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "The user is invalid or does not exist." } ] }), 400 )
    
    try:
        asset_type : AssetType | None = AssetType( asset_type )
    except:
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid asset type." } ] }), 400 )
    
    authenticated_user : User | None = await authentication.GetCurrentUser()
    can_view_inventory : bool = await privacy.can_view_inventory( target_user_obj, authenticated_user )
    if not can_view_inventory:
        return await make_response( jsonify({ "errors": [ { "code": 11, "message": "You don't have permissions to view the specified user's inventory." } ] }), 403 )
    
    page_cursor : str | None = request.args.get( "cursor", type = str, default = None )
    cursor_discriminator : str = f"inventory_{target_user_obj.id}:{asset_type.value}"
    if page_cursor is not None:
        try:
            page_cursor_obj : cursor.ExclusiveStartKeyCursor | cursor.CursorBase = cursor.parse_cursor( page_cursor, cursor_discriminator )
            if not isinstance( page_cursor_obj, cursor.ExclusiveStartKeyCursor ):
                raise ValueError()
        except cursor.InvalidCursorException as e:
            return await make_response( jsonify({ "errors": [ { "code": 4, "message": f"{str(e)}" } ] }), 400 )
    else:
        page_limit : int = request.args.get( "limit", type = int, default = 10 )
        if page_limit not in [ 10, 18, 25, 50, 100 ]:
            return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid limit." } ] }), 400 )
        sorting_order : str = request.args.get( "sortOrder", type = str, default = "Asc" )
        if sorting_order not in [ "Asc", "Desc" ]:
            return await make_response( jsonify({ "errors": [ { "code": 5, "message": "Invalid sort order." } ] }), 400 )
        sort_order_enum : cursor.SortOrder = cursor.SortOrder.Ascending if sorting_order == "Asc" else cursor.SortOrder.Descending
        page_cursor_obj = cursor.ExclusiveStartKeyCursor(
            discriminator = cursor_discriminator,
            key = 1,
            count = page_limit,
            sort_order = sort_order_enum,
            paging_direction = cursor.CursorPagingDirection.Forward
        )
    showDuplicates : bool = request.args.get( "showDuplicates", type = int, default = 1 ) == 1
    
    user_asset_list = UserAsset.query.filter_by( owner_user_id = target_user_obj.id ).outerjoin(
        Asset, UserAsset.asset_id == Asset.id
    ).filter(
        Asset.asset_type == asset_type
    )
    if not showDuplicates:
        user_asset_list = user_asset_list.order_by( UserAsset.asset_id ).distinct( UserAsset.asset_id )
    user_asset_list = user_asset_list.order_by(
        UserAsset.id.desc() if page_cursor_obj.sort_order == cursor.SortOrder.Descending else UserAsset.id.asc()
    ).paginate(
        page = page_cursor_obj.key,
        per_page = page_cursor_obj.count,
        error_out = False
    )
    
    response_data : list[dict] = []
    for user_asset_obj in user_asset_list.items:
        user_asset_obj : UserAsset
        asset_obj : Asset = await assets.GetAssetById( user_asset_obj.asset_id )
        response_data.append({
            "userAssetId": user_asset_obj.id,
            "assetId": user_asset_obj.asset_id,
            "assetName": asset_obj.name,
            "collectibleItemId": None,
            "collectibleItemInstanceId": None,
            "serialNumber": user_asset_obj.serial_number,
            "owner": {
                "userId": target_user_obj.id,
                "username": target_user_obj.username
            },
            "created": build_datetime_obj( user_asset_obj.created_at ),
            "updated": build_datetime_obj( user_asset_obj.updated_at )
        })
    
    next_cursor : str | None = None
    if user_asset_list.has_next:
        next_cursor = cursor.fork_cursor( page_cursor_obj, user_asset_list.next_num, cursor.CursorPagingDirection.Forward )
    
    previous_cursor : str | None = None
    if user_asset_list.has_prev:
        previous_cursor = cursor.fork_cursor( page_cursor_obj, user_asset_list.prev_num, cursor.CursorPagingDirection.Backward )
    
    return await make_response( jsonify({
        "previousPageCursor": previous_cursor,
        "nextPageCursor": next_cursor,
        "data": response_data
    }), 200 )