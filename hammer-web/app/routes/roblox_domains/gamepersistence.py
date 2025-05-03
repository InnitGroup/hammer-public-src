"""
    Ported from SYNTAX Source Code
    gamepersistence.roblox.com
"""
from datetime import datetime, timedelta

from quart import Blueprint, make_response, jsonify, request
from app.extensions import db, csrf_protect
from app.services import authentication, cursor
from app.services.gameservers.server_dispatcher import get_universe_by_placeid
from app.models.gameserver import GameServer
from app.models.place_datastore import PlaceDatastore
from app.models.place_ordered_datastore import PlaceOrderedDatastore
from app.models.universe import Universe

GamePersistenceRoute = Blueprint('gamepersistence_roblox', __name__, url_prefix='/', subdomain='gamepersistence')

@GamePersistenceRoute.before_request
async def _before_request():
    requesting_gameserver : GameServer | None = await authentication.GetCurrentGameServer( verify_access_key = True )
    if requesting_gameserver is None:
        return await make_response( jsonify({ "errors": [ { "code": 0, "message": "Authorization has been denied for this request." } ] }), 401 )

@GamePersistenceRoute.route("/persistence/getSortedValues", methods=["POST"])
@csrf_protect.exempt
async def _get_sorted_values():
    target_place_id : int = request.args.get("placeId", default=None, type=int)
    data_type : str = request.args.get("type", default=None, type=str)
    scope : str = request.args.get("scope", default="global", type=str)
    page_size : int = request.args.get("pageSize", default=50, type=int)
    exclusive_start_key : str | None = request.args.get("exclusiveStartKey", default=None, type=str)
    key : str = request.args.get("key", default=None, type=str)
    ascending : bool = request.args.get("ascending", default="False", type=str) == "True"
    inclusive_min_value : int = request.args.get("inclusiveMinValue", default=None, type=int)
    exclusive_max_value : int = request.args.get("inclusiveMaxValue", default=None, type=int)
    
    universe_obj : Universe | None = await get_universe_by_placeid( target_place_id )
    if universe_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid place ID." } ] }), 400 )
    if page_size == 0 or page_size > 100:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Invalid page size." } ] }), 400 )
    if data_type != "sorted":
        return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid data type." } ] }), 400 )
    
    cursor_discriminator = f"{universe_obj.id}:{scope}:{key}:{inclusive_min_value}:{exclusive_max_value}"
    if exclusive_start_key is not None:
        try:
            cursor_obj = cursor.parse_cursor( exclusive_start_key, discriminator = cursor_discriminator )
            if not isinstance( cursor_obj, cursor.ExclusiveStartKeyCursor ):
                raise ValueError()
        except cursor.InvalidCursorException as e:
            return await make_response( jsonify({ "errors": [ { "code": 4, "message": str(e) } ] }), 400 )
    else:
        sort_order_enum = cursor.SortOrder.Ascending if ascending else cursor.SortOrder.Descending
        cursor_obj = cursor.ExclusiveStartKeyCursor(
            discriminator = cursor_discriminator,
            key = 1,
            count = page_size,
            sort_order = sort_order_enum,
            paging_direction = cursor.CursorPagingDirection.Forward
        )
    
    datastore_obj = PlaceOrderedDatastore.query.filter_by(
        universe_id = universe_obj.id,
        scope = scope,
        key = key
    )
    if inclusive_min_value is not None:
        datastore_obj = datastore_obj.filter( PlaceOrderedDatastore.value >= inclusive_min_value )
    if exclusive_max_value is not None:
        datastore_obj = datastore_obj.filter( PlaceOrderedDatastore.value < exclusive_max_value )
    if cursor_obj.sort_order == cursor.SortOrder.Ascending:
        datastore_obj = datastore_obj.order_by( PlaceOrderedDatastore.value.asc() )
    else:
        datastore_obj = datastore_obj.order_by( PlaceOrderedDatastore.value.desc() )
    datastore_obj : list[ PlaceOrderedDatastore ] = datastore_obj.paginate( page = cursor_obj.key, per_page = cursor_obj.count, error_out = False )
    response_data = []
    for datastore_item in datastore_obj.items:
        response_data.append({
            "Target": datastore_item.name,
            "Value": datastore_item.value
        })
    return await make_response( jsonify({
        "data": {
            "Entries": response_data,
            "ExclusiveStartKey": cursor.fork_cursor( cursor_obj, new_key = datastore_obj.next_num, new_paging_direction=cursor.CursorPagingDirection.Forward ) if datastore_obj.has_next else None
        }
    }), 200 )

@GamePersistenceRoute.route("/persistence/getv2", methods=["POST"])
@GamePersistenceRoute.route("/persistence/getV2", methods=["POST"])
@csrf_protect.exempt
async def _get_persistence():
    target_place_id : int = request.args.get("placeId", default=None, type=int)
    data_type : str = request.args.get("type", default=None, type=str)
    scope : str = request.args.get("scope", default="global", type=str)
    
    universe_obj : Universe | None = await get_universe_by_placeid( target_place_id )
    if universe_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid place ID." } ] }), 400 )
    form_data = await request.form
    requested_data = []
    _count = 0
    while True:
        request_scope : str | None = form_data.get( f"qkeys[{_count}].scope", default = None, type = str )
        request_target : str | None = form_data.get( f"qkeys[{_count}].target", default = None, type = str )
        request_datastore_name : str | None = form_data.get( f"qkeys[{_count}].key", default = None, type = str )
        if request_scope is None or request_target is None or request_datastore_name is None:
            break
        requested_data.append({ "scope": request_scope, "target": request_target, "key": request_datastore_name })
        _count += 1
    if len( requested_data ) == 0:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Invalid request." } ] }), 400 )
    
    response_data = []
    for requested_item in requested_data:
        datastore_value = None
        if data_type == "standard":
            datastore_obj : PlaceDatastore | None = PlaceDatastore.query.filter_by(
                universe_id = universe_obj.id,
                scope = requested_item["scope"],
                key = requested_item["key"],
                name = requested_item["target"]
            ).first()
            datastore_value = datastore_obj.value if datastore_obj is not None else None
        elif data_type == "sorted":
            datastore_obj : PlaceOrderedDatastore | None = PlaceOrderedDatastore.query.filter_by(
                universe_id = universe_obj.id,
                scope = requested_item["scope"],
                key = requested_item["key"],
                name = requested_item["target"]
            ).first()
            datastore_value = str(datastore_obj.value) if datastore_obj is not None else None
        if datastore_value is not None:
            response_data.append({
                "Value": datastore_value,
                "Scope": requested_item["scope"],
                "Key": requested_item["key"],
                "Target": requested_item["target"]
            })
    return await make_response( jsonify({
        "data": response_data
    }), 200 )
        
@GamePersistenceRoute.route("/persistence/set", methods=["POST"])
@csrf_protect.exempt
async def _set_persistence():
    target_place_id : int = request.args.get( "placeId", type = int, default = None )
    data_type : str = request.args.get( "type", type = str, default = None )
    scope : str = request.args.get( "scope", type = str, default = "global" )
    key : str = request.args.get( "key", type = str, default = None )
    target : str = request.args.get( "target", type = str, default = None )
    value_length : int = request.args.get( "valueLength", type = int, default = None )
    
    form_data = await request.form
    value : str = form_data.get( "value", type = str, default = None )
    
    if value_length is None or value_length > 1024 * 1024:
        return await make_response( jsonify({ "errors": [ { "code": 1, "message": "Invalid value length or length larger than 1024 * 1024 bytes." } ] }), 400 )
    universe_obj : Universe | None = await get_universe_by_placeid( target_place_id )
    if universe_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid place ID." } ] }), 400 )
    if data_type == "standard":
        datastore_obj : PlaceDatastore | None = PlaceDatastore.query.filter_by(
            universe_id = universe_obj.id,
            scope = scope,
            key = key,
            name = target
        ).first()
        if datastore_obj is None:
            datastore_obj = PlaceDatastore(
                universe_id = universe_obj.id,
                scope = scope,
                key = key,
                name = target,
                value = value
            )
            db.session.add( datastore_obj )
        else:
            datastore_obj.value = value
        datastore_obj.updated_at = datetime.utcnow()
    elif data_type == "sorted":
        try:
            value : float = float( value )
        except:
            return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid value for sorted datastore." } ] }), 400 )
        datastore_obj : PlaceOrderedDatastore | None = PlaceOrderedDatastore.query.filter_by(
            universe_id = universe_obj.id,
            scope = scope,
            key = key,
            name = target
        ).first()
        if datastore_obj is None:
            datastore_obj = PlaceOrderedDatastore(
                universe_id = universe_obj.id,
                scope = scope,
                key = key,
                name = target,
                value = value
            )
            db.session.add( datastore_obj )
        else:
            datastore_obj.value = value
        datastore_obj.updated_at = datetime.utcnow()
    
    db.session.commit()
    return await make_response( jsonify({
        "data": value
    }), 200 )
    
@GamePersistenceRoute.route("/persistence/increment", methods=["POST"])
@csrf_protect.exempt
async def _increment_persistence():
    target_place_id : int = request.args.get( "placeId", type = int, default = None )
    data_type : str = request.args.get( "type", type = str, default = None )
    scope : str = request.args.get( "scope", type = str, default = "global" )
    key : str = request.args.get( "key", type = str, default = None )
    target : str = request.args.get( "target", type = str, default = None )
    value : int = request.args.get( "value", type = int, default = 1 )
    
    universe_obj : Universe | None = await get_universe_by_placeid( target_place_id )
    if universe_obj is None:
        return await make_response( jsonify({ "errors": [ { "code": 2, "message": "Invalid place ID." } ] }), 400 )
    if data_type == "standard":
        datastore_obj : PlaceDatastore | None = PlaceDatastore.query.filter_by(
            universe_id = universe_obj.id,
            scope = scope,
            key = key,
            name = target
        ).first()
        if datastore_obj is None:
            datastore_obj = PlaceDatastore(
                universe_id = universe_obj.id,
                scope = scope,
                key = key,
                name = target,
                value = str(value)
            )
            db.session.add( datastore_obj )
        else:
            try:
                datastore_obj.value = str( int(datastore_obj.value) + value )
            except:
                return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid value for incrementing." } ] }), 400 )
        datastore_obj.updated_at = datetime.utcnow()
    elif data_type == "sorted":
        datastore_obj : PlaceOrderedDatastore | None = PlaceOrderedDatastore.query.filter_by(
            universe_id = universe_obj.id,
            scope = scope,
            key = key,
            name = target
        ).first()
        if datastore_obj is None:
            datastore_obj = PlaceOrderedDatastore(
                universe_id = universe_obj.id,
                scope = scope,
                key = key,
                name = target,
                value = value
            )
            db.session.add( datastore_obj )
        else:
            try:
                datastore_obj.value = float( datastore_obj.value ) + value
            except:
                return await make_response( jsonify({ "errors": [ { "code": 3, "message": "Invalid value for incrementing." } ] }), 400 )
        datastore_obj.updated_at = datetime.utcnow()
    
    db.session.commit()
    return await make_response( jsonify({
        "data": value
    }), 200 )