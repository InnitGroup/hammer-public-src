import logging
import gzip
import json
from quart import Blueprint, request, make_response, jsonify, redirect, Response, url_for
from PIL import Image
from io import BytesIO
from sqlalchemy import func

from app.models.user import User
from app.models.user_thumbnail import UserThumbnail
from app.models.asset import Asset
from app.models.asset_thumbnail import AssetThumbnail
from app.models.groups import GroupIcon
from app.enums.ModerationStatus import ModerationStatus
from app.enums.AccountStatus import AccountStatus
from app.services import s3manager, thumbnailer, groups
from app.extensions import redis_controller, csrf_protect

from config import Config

web_config = Config()

ThumbnailRoute = Blueprint('thumbnails_roblox', __name__, url_prefix='/', subdomain = "thumbnails")

class ThumbnailRouteExceptions():
    class MissingParameter(Exception):
        pass
    class InvalidParameter(Exception):
        pass
    class ThumbnailDoesNotExist(Exception):
        pass
    class AssetDoesNotExist(Exception):
        pass
    class UserDoesNotExist(Exception):
        pass
    class UnsupportedFormat(Exception):
        pass
    class InternalServiceError(Exception):
        pass
    
    class ImageNotRendered(Exception):
        pass
    class ImageAwaitingModeration(Exception):
        pass
    class ImageModerated(Exception):
        pass

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.MissingParameter )
async def _handle_missing_parameter( e ):
    return await make_response(
        jsonify({ "status": 0, "message": "Missing parameter" }),
        400
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.InvalidParameter )
async def _handle_invalid_parameter( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "Invalid parameter" }),
        400
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.ThumbnailDoesNotExist )
async def _handle_thumbnail_does_not_exist( e ):
    return await make_response(
        jsonify({ "status": 0, "message": "Thumbnail does not exist" }),
        404
    )
    
@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.AssetDoesNotExist )
async def _handle_asset_does_not_exist( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "Asset does not exist" }),
        404
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.UserDoesNotExist )
async def _handle_user_does_not_exist( e ):
    return await make_response(
        jsonify({ "status": 1, "message": "User does not exist" }),
        404
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.UnsupportedFormat )
async def _handle_unsupported_format( e ):
    return await make_response(
        jsonify({ "status": 2, "message": "Unsupported format" }),
        400
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.InternalServiceError )
async def _handle_internal_service_error( e ):
    return await make_response(
        jsonify({ "status": 3, "message": "Internal service error" }),
        500
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.ImageNotRendered )
async def _handle_image_not_rendered( e ):
    return await make_response(
        redirect( url_for( endpoint = 'static', filename = 'img/RenderingInProgress.png', _scheme = 'https') ),
        302
    )

@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.ImageAwaitingModeration )
async def _handle_image_awaiting_moderation( e ):
    return await make_response(
        redirect( url_for( endpoint = 'static', filename = 'img/AwaitingApproval.png', _scheme = 'https') ),
        302
    )
    
@ThumbnailRoute.errorhandler( ThumbnailRouteExceptions.ImageModerated )
async def _handle_image_moderated( e ):
    return await make_response(
        redirect( url_for( endpoint = 'static', filename = 'img/ContentDeleted.png', _scheme = 'https') ),
        302
    )

def is_format_supported( format : str ) -> bool:
    """
        Check if the format is supported
        
        :param format: The format to check
        
        :return: Whether the format is supported
    """
    
    return format.upper() in [ "PNG", "JPEG", "WEBP" ]

def parse_request_resolution(
    width_parameters : list[ str ] = [ 'width', 'x' ],
    height_parameters : list[ str ] = [ 'height', 'y' ],
    allowed_widths : list[ int ] = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
    allowed_heights : list[ int ] = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
    must_be_square : bool = True,
    round_to_nearest_resolution : bool = True,
) -> tuple[ int, int ]:
    """
        Parse the request resolution and return the width and height as a tuple.
        Must be called within a Quart request context.
        
        :param width_parameters: List of parameter names to check for width
        :param height_parameters: List of parameter names to check for height
        :param allowed_widths: List of allowed widths
        :param allowed_heights: List of allowed heights
        :param must_be_square: Whether the resolution must have a 1:1 aspect ratio
        :param round_to_nearest_resolution: Whether to round the resolution to the nearest allowed resolution
        
        :return: A tuple containing the width and height
    """
    
    requested_width : int | None = None
    requested_height : int | None = None

    try:
        for width_parameter in width_parameters:
            if width_parameter in request.args:
                requested_width = int( request.args[ width_parameter ] )
                break
            
        for height_parameter in height_parameters:
            if height_parameter in request.args:
                requested_height = int( request.args[ height_parameter ] )
                break
    except ValueError:
        raise ThumbnailRouteExceptions.InvalidParameter( "Invalid width or height parameter" )
    
    if requested_width is None or requested_height is None:
        raise ThumbnailRouteExceptions.MissingParameter( "Missing width or height parameter" )
    if requested_height < 1 or requested_width < 1:
        raise ThumbnailRouteExceptions.InvalidParameter( "Invalid width or height parameter" )
    if must_be_square and requested_width != requested_height:
        raise ThumbnailRouteExceptions.InvalidParameter( "Width and height must be equal" )
    
    if round_to_nearest_resolution:
        requested_width = min( allowed_widths, key = lambda x: abs(x - requested_width) )
        requested_height = min( allowed_heights, key = lambda x: abs(x - requested_height) )
    
    return ( requested_width, requested_height )

async def _internal_image_resize(
    img_content_hash : str,
    target_width : int,
    target_height : int,
    img_format : str = "PNG",
    
    cropped_image_name : str = None,
) -> str:
    img_fetch_response : s3manager.CDNHttpResponse = await s3manager.download_file_from_cdn( img_content_hash )
    if img_fetch_response.status_code != 200:
        logging.error(f"thumbnails.image_resize > failed to fetch image {img_content_hash}, status code {img_fetch_response.status_code}")
        raise Exception(f"image_resize > failed to fetch image {img_content_hash}, status code {img_fetch_response.status_code}")
    original_image_bytes : bytes = img_fetch_response.content
    
    original_image : Image.Image = Image.open(BytesIO(original_image_bytes))
    resized_image : Image.Image = original_image.resize(
        size = (target_width, target_height),
        resample = Image.LANCZOS
    ).convert( "RGBA" if img_format.upper() in ["PNG", "WEBP"] else "RGB" )
    
    final_image_file : BytesIO = BytesIO()
    resized_image.save(
        final_image_file,
        format = img_format.upper()
    )
    final_image_file.seek(0)
    await s3manager.upload_bytes_to_s3(
        content = final_image_file.read(),
        name_overwrite = cropped_image_name if cropped_image_name else f"{img_content_hash}-{target_width}-{target_height}-{img_format.lower()}",
        content_type = f"image/{img_format.lower()}"
    )
    
    return f"{web_config.CDN_URL}/{cropped_image_name if cropped_image_name else f'{img_content_hash}-{target_width}-{target_height}-{img_format.lower()}'}"

async def handle_image_resizing(
    image_content_hash : str,
    requested_width : int,
    requested_height : int,
    format : str = "PNG",
    cache_control : str = "public, must-revalidate, max-age=1200",
    return_as_json : bool = False,
    return_as_cdn_url : bool = False
) -> Response | str:
    """
        Handle the image resizing process
        
        :param image_content_hash: The content hash of the image
        :param requested_width: The requested width
        :param requested_height: The requested height
        :param cache_control: The Cache-Control header value
        :param return_as_json: Whether to return the image as JSON
        
        :return: Response
    """
    
    if not is_format_supported( format ):
        raise ThumbnailRouteExceptions.UnsupportedFormat( "Unsupported format" )
    
    final_url : str | None = None
    resized_image_name : str = f"{image_content_hash}-{requested_width}-{requested_height}-{format.lower()}"
    if await s3manager.does_object_exist_in_s3( resized_image_name ):
        final_url = await s3manager.get_s3_url( resized_image_name )
    
    if final_url is None:
        resize_image_key_lock : str = f"resize_image_key_lock:{image_content_hash}"
        if await redis_controller.exists( resize_image_key_lock ) > 0:
            raise ThumbnailRouteExceptions.ImageNotRendered( "Image not rendered" )
        await redis_controller.set( resize_image_key_lock, "1", ex = 180 )
        try:
            final_url = await _internal_image_resize(
                img_content_hash = image_content_hash,
                target_width = requested_width,
                target_height = requested_height,
                img_format = format,
                cropped_image_name = resized_image_name
            )
        except Exception as e:
            await redis_controller.set( resize_image_key_lock, "1", ex = 60 )
            raise ThumbnailRouteExceptions.ImageNotRendered( "Image not rendered" )
    
    if return_as_cdn_url:
        return final_url
    
    final_response : Response = None
    if return_as_json:
        final_response = await make_response( jsonify({
            "Final": True,
            "Url": final_url
        }), 200 )
    else:
        final_response = await make_response( redirect(
            final_url,
            code = 302
        ), 302 )
    
    final_response.headers["Cache-Control"] = cache_control
    return final_response    

@ThumbnailRoute.route( "/Thumbs/Avatar.ashx", methods = [ "GET" ], subdomain = "www" )
@ThumbnailRoute.route( "/thumbs/avatar.ashx", methods = [ "GET" ], subdomain = "www" )
async def _fullbody_avatar():
    requested_user_id : int | None = request.args.get( key = "userId", type = int, default = None )
    requested_username : str | None = request.args.get( key = "username", type = str, default = None )
    requested_format : str = request.args.get( key = "format", type = str, default = "PNG" )
    if requested_user_id is None and requested_username is None:
        raise ThumbnailRouteExceptions.MissingParameter( "Missing user ID or username parameter" )
    
    requested_width, requested_height = parse_request_resolution(
        width_parameters = [ 'width', 'x' ],
        height_parameters = [ 'height', 'y' ],
        allowed_widths = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
        allowed_heights = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
        must_be_square = True,
        round_to_nearest_resolution = True
    )
    
    if requested_username is not None and requested_user_id is None:
        requested_user : User | None = User.query.filter( func.lower( User.username ) == func.lower( requested_username ) ).first()
        if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
            raise ThumbnailRouteExceptions.UserDoesNotExist( "User does not exist" )
        requested_user_id = requested_user.id
    else:
        requested_user : User | None = User.query.filter_by( id = requested_user_id ).first()
        if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
            raise ThumbnailRouteExceptions.UserDoesNotExist( "User does not exist" )
    
    user_thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = requested_user )
    if user_thumbnail_obj.fullbody_content_hash is None:
        raise ThumbnailRouteExceptions.ImageNotRendered( "Image not rendered" )
    
    content_hash : str = user_thumbnail_obj.fullbody_content_hash
    return await handle_image_resizing(
        image_content_hash = content_hash,
        requested_width = requested_width,
        requested_height = requested_height,
        format = requested_format
    )
    
@ThumbnailRoute.route( "/Thumbs/Head.ashx", methods = [ "GET" ], subdomain = "www" )
async def _headshot_avatar():
    requested_user_id : int | None = request.args.get( key = "userId", type = int, default = None )
    requested_format : str = request.args.get( key = "format", type = str, default = "PNG" )
    if requested_user_id is None:
        raise ThumbnailRouteExceptions.MissingParameter( "Missing user ID parameter" )
    
    requested_width, requested_height = parse_request_resolution(
        width_parameters = [ 'width', 'x' ],
        height_parameters = [ 'height', 'y' ],
        allowed_widths = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
        allowed_heights = [ 48, 60, 100, 150, 180, 200, 352, 420, 500 ],
        must_be_square = True,
        round_to_nearest_resolution = True
    )
    
    requested_user : User | None = User.query.filter_by( id = requested_user_id ).first()
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        raise ThumbnailRouteExceptions.UserDoesNotExist( "User does not exist" )
    user_thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = requested_user )
    if user_thumbnail_obj.headshot_content_hash is None:
        raise ThumbnailRouteExceptions.ImageNotRendered( "Image not rendered" )
    content_hash : str = user_thumbnail_obj.headshot_content_hash
    return await handle_image_resizing(
        image_content_hash = content_hash,
        requested_width = requested_width,
        requested_height = requested_height,
        format = requested_format
    )
    
@ThumbnailRoute.route( "/Thumbs/Asset.ashx", methods = [ "GET" ], subdomain = "www" )
@ThumbnailRoute.route( "/thumbs/asset.ashx", methods = [ "GET" ], subdomain = "www" )
async def _asset_thumbnail():
    requested_asset_id : int | None = request.args.get( key = "assetId", type = int, default = None ) or request.args.get( key = "assetid", type = int, default = None )
    requested_format : str = request.args.get( key = "format", type = str, default = "PNG" )
    if requested_asset_id is None:
        raise ThumbnailRouteExceptions.MissingParameter( "Missing asset ID parameter" )
    
    requested_width, requested_height = parse_request_resolution(
        width_parameters = [ 'width', 'x' ],
        height_parameters = [ 'height', 'y' ],
        allowed_widths = [48,180,420,60,100,150,352,396,480,512,576,700,768,640,360,1280,720],
        allowed_heights = [48,180,420,60,100,150,352,396,480,512,576,700,768,640,36,1280,720],
        must_be_square = False,
        round_to_nearest_resolution = True
    )
    
    asset_obj : Asset | None = Asset.query.filter_by( id = requested_asset_id ).first()
    if asset_obj is None:
        raise ThumbnailRouteExceptions.AssetDoesNotExist( "Asset does not exist" )
    if asset_obj.moderation_status == ModerationStatus.Denied:
        raise ThumbnailRouteExceptions.ImageModerated( "Image moderated" )
    if asset_obj.moderation_status == ModerationStatus.AwaitingApproval:
        raise ThumbnailRouteExceptions.ImageAwaitingModeration( "Image awaiting moderation" )
    asset_thumbnail_obj : AssetThumbnail | None = await thumbnailer.get_asset_thumbnail_obj( asset_obj = asset_obj )
    if asset_thumbnail_obj is None:
        raise ThumbnailRouteExceptions.ImageNotRendered( "Image not rendered" )
    if asset_thumbnail_obj.moderation_status == ModerationStatus.AwaitingApproval:
        raise ThumbnailRouteExceptions.ImageAwaitingModeration( "Image awaiting moderation" )
    if asset_thumbnail_obj.moderation_status == ModerationStatus.Denied:
        raise ThumbnailRouteExceptions.ImageModerated( "Image moderated" )
    
    content_hash : str = asset_thumbnail_obj.content_hash
    return await handle_image_resizing(
        image_content_hash = content_hash,
        requested_width = requested_width,
        requested_height = requested_height,
        format = requested_format
    )

@ThumbnailRoute.route( "/v1/users/avatar-3d", methods = ["GET"], subdomain = "thumbnails" )
@ThumbnailRoute.route( "/Thumbs/UserAvatar3D", methods = ["GET"], subdomain = "www" )
async def _user_avatar_3d():
    requested_user_id : int | None = request.args.get( key = "userId", type = int, default = None )
    if requested_user_id is None:
        raise ThumbnailRouteExceptions.MissingParameter( "Missing user ID parameter" )
    requested_user : User | None = User.query.filter_by( id = requested_user_id ).first()
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        raise ThumbnailRouteExceptions.UserDoesNotExist( "User does not exist" )
    user_thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = requested_user )
    if user_thumbnail_obj.body_3d_content_hash is None:
        return await make_response(jsonify({
            "targetId": requested_user_id,
            "state": "Pending",
            "imageUrl": ""
        }))
    
    content_hash : str = user_thumbnail_obj.body_3d_content_hash
    return await make_response(jsonify({
        "targetId": requested_user_id,
        "state": "Completed",
        "imageUrl": f"{web_config.CDN_URL}/{content_hash}"
    }))

@ThumbnailRoute.route("/v1/users/<int:user_id>/thumbnail-status", methods = ["GET"], subdomain = "thumbnails")
async def _user_thumbnail_status(user_id : int):
    requested_user_id : int = user_id
    requested_user : User | None = User.query.filter_by( id = requested_user_id ).first()
    if requested_user is None or requested_user.account_status == AccountStatus.GDPR_Deleted:
        raise ThumbnailRouteExceptions.UserDoesNotExist( "User does not exist" )
    user_thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = requested_user )
    return await make_response(jsonify({
        "userId": requested_user_id,
        "full_body": "Completed" if user_thumbnail_obj.fullbody_content_hash is not None else "Pending",
        "headshot": "Completed" if user_thumbnail_obj.headshot_content_hash is not None else "Pending",
        "body_3d": "Completed" if user_thumbnail_obj.body_3d_content_hash is not None else "Pending"
    }), 200)

@ThumbnailRoute.route("/v1/batch", methods = ["POST"], subdomain = "thumbnails")
@csrf_protect.exempt
async def _batch_request_thumbanils():
    is_gzip_payload : bool = request.headers.get("Content-Encoding") == "gzip"
    if is_gzip_payload:
        try:
            payload = gzip.decompress( await request.data )
        except:
            raise ThumbnailRouteExceptions.InvalidParameter( "Invalid gzip payload" )
        try:
            payload = json.loads( payload )
        except:
            raise ThumbnailRouteExceptions.InvalidParameter( "Invalid JSON payload" )
    else:
        payload = await request.get_json()
        
    if not isinstance( payload, list ):
        raise ThumbnailRouteExceptions.InvalidParameter( "Invalid JSON payload" )
    if len( payload ) > 15:
        raise ThumbnailRouteExceptions.InvalidParameter( "Too many requests" )
    
    processed_requests : list[dict] = []
    failed_requests : list[dict] = []
    for thumb_request in payload:
        try:
            assert "requestId" in thumb_request, "Missing requestId"
            assert "targetId" in thumb_request, "Missing targetId"
            assert "type" in thumb_request, "Missing type"
            assert "size" in thumb_request, "Missing size"
            assert type( thumb_request["requestId"] ) == str, "requestId expected to be a string"
            assert type( thumb_request["targetId"] ) == int, "targetId expected to be an integer"
            assert type( thumb_request["type"] ) == str, "type expected to be a string"
            assert type( thumb_request["size"] ) == str, "size expected to be a string"
            assert thumb_request["type"] in ["Avatar", "AvatarHeadShot", "GameIcon", "GameThumbnail", "Asset", "GroupIcon"], "Invalid type"
            assert "x" in thumb_request["size"], "Invalid size"
            splitted_size = thumb_request["size"].split("x")
            assert len( splitted_size ) == 2, "Invalid size"
            assert type( int( splitted_size[0] ) ) == int, "Invalid size"
            assert type( int( splitted_size[1] ) ) == int, "Invalid size"
            requested_width = int( splitted_size[0] )
            requested_height = int( splitted_size[1] )
            assert thumb_request["targetId"] > 0, "Invalid targetId"
        except AssertionError as e:
            failed_requests.append(f"{e}")
            continue
        allowed_sizes = [48,180,420,60,100,150,352,396,480,512,576,700,768,640,36,1280,720]
        target_width = min( allowed_sizes, key = lambda x: abs(x - requested_width) )
        target_height = min( allowed_sizes, key = lambda x: abs(x - requested_height) )
        request_type = thumb_request["type"]
        target_id = thumb_request["targetId"]
        thumbnail_content_hash : str | None = None
        if request_type == "Avatar":
            thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = target_id )
            if thumbnail_obj is None:
                continue
            thumbnail_content_hash = thumbnail_obj.fullbody_content_hash
        elif request_type == "AvatarHeadShot":
            thumbnail_obj : UserThumbnail = await thumbnailer.get_user_thumbnail_obj( user_obj = target_id )
            if thumbnail_obj is None:
                continue
            thumbnail_content_hash = thumbnail_obj.headshot_content_hash
        elif request_type == "Asset":
            asset_thumbnail_obj : AssetThumbnail | None = await thumbnailer.get_asset_thumbnail_obj( asset_obj = target_id )
            if asset_thumbnail_obj is None:
                continue
            if asset_thumbnail_obj.moderation_status != ModerationStatus.Approved:
                continue
            thumbnail_content_hash = asset_thumbnail_obj.content_hash
        elif request_type == "GroupIcon":
            group_icon_obj : GroupIcon | None = await groups.GetGroupIconFromGroup( TargetGroup = target_id )
            if group_icon_obj is None:
                continue
            if group_icon_obj.moderation_status != ModerationStatus.Approved:
                continue
            thumbnail_content_hash = group_icon_obj.content_hash
        else:
            continue
        
        try:
            resized_image_url : str = await handle_image_resizing(
                image_content_hash = thumbnail_content_hash,
                requested_width = target_width,
                requested_height = target_height,
                format = "PNG",
                return_as_cdn_url = True
            )
        except ThumbnailRouteExceptions.ImageNotRendered:
            continue
        processed_requests.append({
            "requestId": thumb_request["requestId"],
            "targetId": target_id,
            "state": "Completed",
            "imageUrl": resized_image_url,
            "version": None
        })
    return await make_response( jsonify({
        "data": processed_requests,
        "errors": failed_requests
    }), 200 )