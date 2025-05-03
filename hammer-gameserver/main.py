import os
os.environ['PYTHONASYNCIODEBUG'] = '1'

import base64
import time
import logging
import zstd
import winreg
import psutil
import time
import threading
import json
import queue
import asyncio
import uuid
import xmltodict
import aiohttp
import re
import io
import random

from PIL import Image
from quart import Quart, request, Response, jsonify, make_response
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from logging.handlers import RotatingFileHandler

from soap_formatting import RCCSOAPMessages
from controllers.rccservice_controller import RCCService, create_rcc_instance, SOAPResponse
from controllers.quilkin_controller import QuilkinController
from enums.ProcessYear import ProcessYear
from enums.ThumbnailRequestTypes import ThumbnailRequestTypes

from server_config import ServerConfig

server_config = ServerConfig()

logging.basicConfig(
    level = logging.DEBUG,
    format = "%(asctime)s [%(levelname)s] %(message)s",
    handlers = [
        RotatingFileHandler(
            filename = server_config.log_file_path + "arbiter.log",
            maxBytes = 1000000,
            backupCount = 10
        ),
        logging.StreamHandler()
    ]
)
SoapMessageFormatter = RCCSOAPMessages()
quart_app = Quart( __name__ )

def read_access_key():
    """ Computer\HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\ROBLOX Corporation\Roblox\AccessKey """
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\ROBLOX Corporation\Roblox", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "AccessKey")
        winreg.CloseKey(key)
        return value
    except:
        return ""
    
def write_access_key( value : str ):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\ROBLOX Corporation\Roblox", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AccessKey", 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
    except Exception as e:
        logging.error(f"write_access_key > Failed to write AccessKey to registry, {str(e)}")
        pass

async def verify_signature( signature : bytes, data : bytes ) -> bool:
    with open("rsa_public_gameserver.pub", "rb") as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend=default_backend()
        )
    
    try:
        public_key.verify(
            signature,
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except:
        return False
    
async def get_decoded_data() -> bytes:
    """
        Must be called in a quart request context
    """
    if request.headers.get("Content-Encoding", default = "") == "zstd":
        return zstd.decompress( await request.get_data() )
    return await request.get_data()

@quart_app.before_request
async def verify_request():
    ReqUserAgent = request.headers.get("User-Agent", default = "Unknown")
    if ReqUserAgent != "HAMMER-Gameserver-Communication/1.1":
        return await make_response( jsonify({ "error": "Unauthorized" }), 401 )
    RequestSignature = request.headers.get("X-Hammer-Request-Signature", default = b"")
    try:
        RequestData : bytes = await request.get_data()
        ReqTimestamp, ReqSignature = RequestSignature.split("|")
        ReqTimestamp = float(ReqTimestamp)
        if time.time() - ReqTimestamp > 6:
            logging.error(f"verify_request > Unauthorized request from {request.remote_addr} has expired Request Signature")
            return await make_response( jsonify({ "error": "Unauthorized" }), 401 )
        ReconstructuedData : bytes = f"{str(ReqTimestamp)}\n{request.method}".encode('utf-8')
        if request.method == "POST":
            ReconstructuedData += "\n".encode('utf-8')
            ReconstructuedData += RequestData
        ReqSignature = base64.b64decode(ReqSignature)
        if not await verify_signature( ReqSignature, ReconstructuedData ):
            logging.error(f"verify_request > Unauthorized request from {request.remote_addr} has invalid Request Signature")
            return await make_response( jsonify({ "error": "Unauthorized" }), 401 )
    except Exception as e:
        logging.error(f"verify_request > Error parsing Request Signature: {e}")
        return await make_response( jsonify({ "error": "Unauthorized" }), 401 )

@quart_app.after_request
async def encode_request( response : Response ) -> Response:
    ResponseData : bytes = await response.get_data( as_text = False )
    ResponseData : bytes = zstd.compress( ResponseData )
    response.set_data( ResponseData )
    response.headers["Content-Encoding"] = "zstd"

    return response

class ThumbnailRequest:
    request_type : ThumbnailRequestTypes
    user_id : int | None = None
    asset_id : int | None = None
    render_width : int = 512
    render_height : int = 512
    render_format : str = "png"
    request_id : str
    avatar_hash : str | None = None
    
    def __init__( self, request_data : dict ):
        self.request_type = ThumbnailRequestTypes( request_data["thumbnail_request_type"] )
        self.user_id = request_data["user_id"]
        self.asset_id = request_data["asset_id"]
        self.render_width = request_data["width"]
        self.render_height = request_data["height"]
        self.render_format = request_data["format"]
        self.request_id = request_data["request_id"]
        self.avatar_hash = request_data["avatar_hash"] if "avatar_hash" in request_data else None

rccservice_instance_pool : dict[ ProcessYear, list[ RCCService ] ] = {}
rccservice_soap_port_available : list[ int ] = list( server_config.rcc_soap_port_range )
rccservice_gameserver_port_available : list[ int ] = list( server_config.rcc_gameserver_port_range )
running_rcc_instances : list[ RCCService ] = []

thumbnail_request_queue : queue.Queue = queue.Queue()

prelaunch_rcc_instance_lock = asyncio.Lock()
get_rccservice_soap_port_lock = asyncio.Lock()
get_rccservice_gameserver_port_lock = asyncio.Lock()
get_rccservice_instance_lock = asyncio.Lock()

async def get_rccservice_soap_port() -> int:
    global rccservice_soap_port_available
    logging.info(f"get_rccservice_soap_port > Trying to obtain get_rccservice_soap_port_lock")
    async with get_rccservice_soap_port_lock:
        logging.info(f"get_rccservice_soap_port > Obtained get_rccservice_soap_port_lock")
        if len( rccservice_soap_port_available ) == 0:
            rccservice_soap_port_available = list( server_config.rcc_soap_port_range )
        return rccservice_soap_port_available.pop(random.randint(0, len(rccservice_soap_port_available) - 1))
    
async def get_rccservice_gameserver_port() -> int:
    global rccservice_gameserver_port_available
    logging.info(f"get_rccservice_gameserver_port > Trying to obtain get_rccservice_gameserver_port_lock")
    async with get_rccservice_gameserver_port_lock:
        logging.info(f"get_rccservice_gameserver_port > Obtained get_rccservice_gameserver_port_lock")
        if len( rccservice_gameserver_port_available ) == 0:
            rccservice_gameserver_port_available = list( server_config.rcc_gameserver_port_range )
        return rccservice_gameserver_port_available.pop(random.randint(0, len(rccservice_gameserver_port_available) - 1))

async def prelaunch_rcc_instances():
    global rccservice_instance_pool
    logging.info(f"prelaunch_rcc_instances > Trying to obtain prelaunch_rcc_instance_lock")
    async with prelaunch_rcc_instance_lock:
        logging.info(f"prelaunch_rcc_instances > Obtained prelaunch_rcc_instance_lock")
        for rcc_year in server_config.prelaunch_instances_per_year:
            if rcc_year not in rccservice_instance_pool:
                rccservice_instance_pool[rcc_year] = []
            if len( rccservice_instance_pool[rcc_year] ) >= server_config.prelaunch_instances_per_year[rcc_year]:
                continue
            required_instances = server_config.prelaunch_instances_per_year[rcc_year] - len( rccservice_instance_pool[rcc_year] )
            executable_path = server_config.server_executable_paths[rcc_year]
            for i in range( required_instances ):
                rccservice_instance_pool[rcc_year].append(
                    await create_rcc_instance(
                        executable_path = executable_path,
                        rcc_soap_port = await get_rccservice_soap_port(),
                        kill_on_job_end = False,
                        rcc_version = rcc_year,
                        use_verbose = False,
                        PlaceIdStartupBypassOverwrite = 1 if rcc_year in [ ProcessYear.Sixteen ] else 0
                    )
                )

async def get_rcc_instance( rcc_year : ProcessYear, start_job_watcher : bool = True ) -> RCCService:
    global rccservice_instance_pool
    if rcc_year not in rccservice_instance_pool:
        rccservice_instance_pool[rcc_year] = []
    selected_instance : RCCService = None
    logging.info(f"get_rcc_instance > Trying to obtain get_rccservice_instance_lock")
    async with get_rccservice_instance_lock:
        logging.info(f"get_rcc_instance > Obtained get_rccservice_instance_lock")
        if len( rccservice_instance_pool[rcc_year] ) != 0:
            selected_instance = rccservice_instance_pool[rcc_year].pop( 0 )
            if start_job_watcher:
                await selected_instance.start_job_watcher()
        else:
            executable_path = server_config.server_executable_paths[rcc_year]
            selected_instance = await create_rcc_instance(
                executable_path = executable_path,
                rcc_soap_port = await get_rccservice_soap_port(),
                kill_on_job_end = start_job_watcher,
                rcc_version = rcc_year,
                use_verbose = False,
                PlaceIdStartupBypassOverwrite = 1 if rcc_year in [ ProcessYear.Sixteen ] else 0
            )
    
    quart_app.add_background_task( prelaunch_rcc_instances )
    return selected_instance
class SimpleFetchResponse:
    status_code : int
    content : bytes
    headers : dict
    
    def __init__( self, status_code : int, content : bytes, headers : dict ):
        self.status_code = status_code
        self.content = content
        self.headers = headers

async def simple_fetch( url : str, headers : dict | None = None, is_authenticated : bool = True, is_post : bool = False, body_data : bytes | None = None ) -> SimpleFetchResponse:
    if is_authenticated:
        if headers is None:
            headers = {}
        headers["AccessKey"] = read_access_key()
        headers["User-Agent"] = "HAMMER-Gameserver-Communication/1.1"
    async with aiohttp.ClientSession() as session:
        if not is_post:
            async with session.get( url, headers = headers ) as response:
                return SimpleFetchResponse(
                    status_code = response.status,
                    content = await response.read(),
                    headers = response.headers
                )
        else:
            async with session.post( url, headers = headers, data = body_data ) as response:
                return SimpleFetchResponse(
                    status_code = response.status,
                    content = await response.read(),
                    headers = response.headers
                )

async def process_thumbnail_render( render_result : bytes, request_info : ThumbnailRequest, _process_attempt : int = 0 ) -> None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url = f"http://internal.{server_config.base_domain}/v1/thumbnail-render-complete",
                data = render_result,
                headers = {
                    "Content-Type": "image/png",
                    "User-Agent": "HAMMER-Gameserver-Communication/1.1",
                    "AccessKey": read_access_key(),
                    "X-Hammer-Request-Id": request_info.request_id
                }
            ) as response:
                if response.status != 200:
                    logging.error(f"process_thumbnail_render > Failed to send thumbnail render to backend server, status code {response.status}, dropping request {request_info.request_id}")
                    return
                logging.info(f"process_thumbnail_render > Successfully sent thumbnail render to backend server for request {request_info.request_id}")
    except InterruptedError as e:
        logging.error(f"process_thumbnail_render > received InterruptedError: {str(e)}")
        return
    except Exception as e:
        logging.error(f"process_thumbnail_render > Exception raised: {str(e)}")
        if _process_attempt < 3:
            await process_thumbnail_render( render_result, request_info, _process_attempt + 1 )

with open("./TeeShirtTemplate.png", "rb") as tshirt_template_file:
    tshirt_template_bytes = tshirt_template_file.read()

async def render_tshirt( tshirt_id : int, thumbnail_request : ThumbnailRequest ) -> None:
    fetch_tshirt_asset : SimpleFetchResponse = await simple_fetch(
        f"https://www.{server_config.base_domain}/asset/?id={tshirt_id}"
    )
    if fetch_tshirt_asset.status_code != 200:
        raise Exception(f"Failed to fetch TShirt asset {tshirt_id}, status code {fetch_tshirt_asset.status_code}")
    response_text : str = fetch_tshirt_asset.content.decode('utf-8')
    original_image_lookup = re.search(r"id=(\d+)", response_text) or re.search(r"rbxassetid:\/\/(\d+)", response_text)
    if original_image_lookup is None:
        raise Exception(f"Failed to extract original image id from TShirt asset {tshirt_id}")
    original_image_id : int = int( original_image_lookup.group(1) )
    fetch_image_bytes : SimpleFetchResponse = await simple_fetch(
        f"https://www.{server_config.base_domain}/asset/?id={original_image_id}"
    )
    if fetch_image_bytes.status_code != 200:
        raise Exception(f"Failed to fetch original image asset {original_image_id}, status code {fetch_image_bytes.status_code}")
    tshirt_bg_image = Image( io.BytesIO( tshirt_template_bytes ) )
    content_image = Image.open( io.BytesIO( fetch_image_bytes.content ) )
    width, height = content_image.size
    aspect_ratio = width / height
    
    if width > height:
        new_width = 250
        new_height = int(new_width / aspect_ratio)
    else:
        new_height = 250
        new_width = int(new_height * aspect_ratio)
        
    content_image = content_image.resize((new_width, new_height), Image.LANCZOS)
    content_image = content_image.convert("RGBA")
    
    composite_image = Image.new('RGBA', tshirt_bg_image.size)
    composite_image.paste(tshirt_bg_image, (0, 0))
    mask = content_image.split()[3]
    composite_image.paste(content_image, (85, 85), mask=mask)

    composite_image_buffer = io.BytesIO()
    composite_image.save(composite_image_buffer, format='PNG')
    composite_image_buffer.seek(0)

    rendered_image = composite_image_buffer.read()
    await process_thumbnail_render( rendered_image, thumbnail_request )

async def thumbnail_render_worker():
    global thumbnail_request_queue
    while True:
        try:
            if thumbnail_request_queue.empty():
                await asyncio.sleep( 0.1 )
                continue
            thumbnail_request : ThumbnailRequest = thumbnail_request_queue.get( block = False )
            logging.info(f"thumbnail_render_worker > Processing request {thumbnail_request.request_id} of type {thumbnail_request.request_type.name}")
            
            execute_json : dict | None = None
            job_render_expiration : int = 10
            if thumbnail_request.request_type == ThumbnailRequestTypes.UserFullBody:
                execute_json = {
                    "Type": "Avatar",
                    "Arguments": [
                        f"https://avatar.{server_config.base_domain}/v1/avatar-fetch?placeId=0&userId={ thumbnail_request.user_id }&avatar_hash={thumbnail_request.avatar_hash}",
                        f"http://www.{server_config.base_domain}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.UserHeadshot:
                execute_json = {
                    "Type": "Closeup",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}",
                        f"https://avatar.{server_config.base_domain}/v1/avatar-fetch?placeId=0&userId={ thumbnail_request.user_id }&avatar_hash={thumbnail_request.avatar_hash}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,

                        True, 30, 100, 0, 0
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Model:
                execute_json = {
                    "Type": "Model",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}"
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Mesh:
                execute_json = {
                    "Type": "Mesh",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}"
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Place:
                execute_json = {
                    "Type": "Place",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}"
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Image:
                execute_json = {
                    "Type": "Image",
                    "Arguments": [
                        thumbnail_request.asset_id,
                        f"http://www.{server_config.base_domain}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.TShirt:
                return await render_tshirt( thumbnail_request.asset_id, thumbnail_request )
            elif thumbnail_request.request_type == ThumbnailRequestTypes.AvatarHead:
                execute_json = {
                    "Type": "Head",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}",
                        1785197
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.AvatarBodypart:
                execute_json = {
                    "Type": "BodyPart",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        f"http://www.{server_config.base_domain}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}/asset/?id=1785197"
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.AvatarHat:
                execute_json = {
                    "Type": "Hat",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}"
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.AvatarGear:
                execute_json = {
                    "Type": "Gear",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}",
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.MeshPart:
                execute_json = {
                    "Type": "MeshPart",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}",
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Pants:
                execute_json = {
                    "Type": "Pants",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}",
                        1785197
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Shirt:
                execute_json = {
                    "Type": "Shirt",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}",
                        1785197
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Avatar_R15_Action:
                execute_json = {
                    "Type": "Avatar_R15_Action",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}",
                        f"https://avatar.{server_config.base_domain}/v1/avatar-fetch?placeId=0&userId={ thumbnail_request.user_id }&avatar_hash={thumbnail_request.avatar_hash}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.Package:
                execute_json = {
                    "Type": "Package",
                    "Arguments": [
                        thumbnail_request.asset_id,
                        f"http://www.{server_config.base_domain}",
                        thumbnail_request.render_format,
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        f"http://www.{server_config.base_domain}/asset/?id=1785197",
                        ""
                    ]
                }
            elif thumbnail_request.request_type == ThumbnailRequestTypes.AnimationSilhouette:
                execute_json = {
                    "Type": "AnimationSilhouette",
                    "Arguments": [
                        f"http://www.{server_config.base_domain}/asset/?id={thumbnail_request.asset_id}",
                        f"http://www.{server_config.base_domain}",
                        thumbnail_request.render_width,
                        thumbnail_request.render_height,
                        "159/159/159"
                    ]
                }
            else:
                logging.error(f"thumbnail_render_worker > Unsupported request type {thumbnail_request.request_type.name}")
                continue
            
            rcc_instance : RCCService = await get_rcc_instance( ProcessYear.TwentyOne, start_job_watcher = True )
            job_render_id : str = str( uuid.uuid4() )
            
            render_response : SOAPResponse = await rcc_instance.send_batch_job_request(
                job_id = job_render_id,
                job_expiration = job_render_expiration,
                assigned_cores = 1,
                script_name = "RenderProcess",
                run_script = json.dumps(
                    {
                        "Mode": "Thumbnail",
                        "Settings": execute_json
                    }
                ),
                request_timeout = job_render_expiration + 5
            )
            if render_response is None:
                logging.error(f"thumbnail_render_worker > Failed to send job request to RCC instance")
                continue
            if render_response.status_code != 200:
                logging.error(f"thumbnail_render_worker > Failed to send job request to RCC instance, status code {render_response.status_code}, dropping request {thumbnail_request.request_id}")
                continue
            
            render_result = xmltodict.parse(render_response.content.strip())["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["ns1:BatchJobResponse"]["ns1:BatchJobResult"]
            final_render_result : bytes | None = None
            if type(render_result) == list:
                for ResponseItem in render_result:
                    if ResponseItem["ns1:type"] == "LUA_TSTRING":
                        rcc_render_output = ResponseItem["ns1:value"]
            else:
                if render_result["ns1:type"] == "LUA_TSTRING":
                    rcc_render_output = render_result["ns1:value"]
            
            if rcc_render_output is None:
                logging.error(f"thumbnail_render_worker > Failed to render thumbnail for request {thumbnail_request.request_id}")
                continue
            
            if thumbnail_request.render_format.lower() != "obj":
                final_render_result = base64.b64decode( rcc_render_output )
            else:
                final_render_result = rcc_render_output.encode('utf-8')
            
            quart_app.add_background_task( process_thumbnail_render, final_render_result, thumbnail_request )
        except InterruptedError as e:
            logging.error(f"thumbnail_render_worker > received InterruptedError: {str(e)}, stopping worker")
            break
        except Exception as e:
            logging.error(f"thumbnail_render_worker > exception raised: {str(e)}")
            continue

@quart_app.before_serving
async def _before_serving():
    quart_app.add_background_task( prelaunch_rcc_instances )
    for i in range( server_config.thumbnail_render_workers ):
        quart_app.add_background_task( thumbnail_render_worker )
    
@quart_app.route("/info", methods = ["GET"])
async def server_info():
    system_memory_usage : float = psutil.virtual_memory()[3]/1000000 # MB
    system_cpu_usage : float = psutil.cpu_percent() # Percentage
    system_memory_size : float = psutil.virtual_memory()[0]/1000000 # MB
    system_time : float = time.time()
    system_cores : int = psutil.cpu_count()
    system_network_sent : float = ( psutil.net_io_counters().bytes_sent * 8 ) / 1000000 # Mbps
    system_network_recv : float = ( psutil.net_io_counters().bytes_recv * 8 ) / 1000000 # Mbps
    running_instances : list[dict] = []
    for rcc_instance in running_rcc_instances:
        if not rcc_instance.is_rcc_running():
            logging.info(f"server_info > RCC instance {rcc_instance.assigned_server_uuid} is not running, removing from running instances")
            running_rcc_instances.remove( rcc_instance )
            continue
        running_instances.append({
            "server_uuid" : rcc_instance.assigned_server_uuid,
            "start_time" : rcc_instance.start_time,
            "rcc_version" : rcc_instance.rcc_version.name,
        })

    return await make_response( jsonify({
        "memory_usage" : system_memory_usage,
        "cpu_usage" : system_cpu_usage,
        "memory_size" : system_memory_size,
        "time" : system_time,
        "cores" : system_cores,
        "network_sent" : system_network_sent,
        "network_recv" : system_network_recv,

        "access_key" : read_access_key(),
        "thumbnail_request_queue_size" : thumbnail_request_queue.qsize(),
        "running_instances" : running_instances
    }), 200 )

@quart_app.route("/execute_script", methods = ["POST"])
async def execute_script():
    global running_rcc_instances
    script_request_data = json.loads(
        ( await get_decoded_data() ).decode('utf-8')
    )
    
    try:
        assert "target_server_uuid" in script_request_data, "target_server_uuid is required"
        assert "script_name" in script_request_data, "script_name is required"
        assert "script_arguments" in script_request_data, "script_arguments is required"
        assert "script" in script_request_data, "script is required"
        assert type( script_request_data["target_server_uuid"] ) == str, "target_server_uuid must be a string"
        assert type( script_request_data["script_name"] ) == str, "script_name must be a string"
        assert type( script_request_data["script_arguments"] ) == list, "script_arguments must be a list"
        assert type( script_request_data["script"] ) == str, "script must be a string"
    except AssertionError as e:
        return await make_response( jsonify({
            "error" : f"Validation failed: { str(e) }",
            "success" : False
        }), 400 )
    
    target_server_uuid : str = script_request_data["target_server_uuid"]
    target_rcc_instance : RCCService | None = None
    for rcc_instance in running_rcc_instances:
        if rcc_instance.assigned_server_uuid == target_server_uuid:
            target_rcc_instance = rcc_instance
            break
    if target_rcc_instance is None:
        return await make_response( jsonify({
            "error" : "Target server not found",
            "success" : False
        }), 404 )
    execute_script_response : SOAPResponse = await target_rcc_instance.send_execute_script_request(
        job_id = script_request_data["target_server_uuid"],
        script_name = script_request_data["script_name"],
        script = script_request_data["script"],
        script_arguments = script_request_data["script_arguments"]
    )
    return await make_response( jsonify({
        "success" : True,
        "status_code" : execute_script_response.status_code,
        "response" : execute_script_response.content
    }), 200 )

async def on_instance_killed_callback( server_uuid ):
    global running_rcc_instances
    await simple_fetch(
        f"https://gameinstances.api.{server_config.base_domain}/v1/instance-killed?server_uuid={server_uuid}",
        is_post = True
    )
    for rcc_instance in running_rcc_instances:
        if rcc_instance.assigned_server_uuid == server_uuid:
            running_rcc_instances.remove( rcc_instance )
            break

@quart_app.route("/start_new_game", methods = [ "POST" ])
async def _start_new_game_handler():
    global running_rcc_instances
    new_game_request_data = json.loads(
        ( await get_decoded_data() ).decode('utf-8')
    )
    
    try:
        assert "place_id" in new_game_request_data, "place_id is required"
        assert "place_year" in new_game_request_data, "place_year is required"
        assert "api_key" in new_game_request_data, "api_key is required"
        assert "universe_id" in new_game_request_data, "universe_id is required"
        assert "creator_id" in new_game_request_data, "creator_id is required"
        assert "creator_type" in new_game_request_data, "creator_type is required"
        assert "place_version" in new_game_request_data, "place_version is required"
        assert "job_id" in new_game_request_data, "job_id is required"
        assert "max_players" in new_game_request_data, "max_players is required"
        assert type( new_game_request_data["place_id"] ) == int, "place_id must be an integer"
        assert type( new_game_request_data["place_year"] ) == int, "place_year must be an integer"
        assert type( new_game_request_data["api_key"] ) == str, "api_key must be a string"
        assert type( new_game_request_data["universe_id"] ) == int, "universe_id must be an integer"
        assert type( new_game_request_data["creator_id"] ) == int, "creator_id must be an integer"
        assert type( new_game_request_data["creator_type"] ) == str, "creator_type must be a string"
        assert type( new_game_request_data["place_version"] ) == int, "place_version must be an integer"
        assert type( new_game_request_data["job_id"] ) == str, "job_id must be a string"
        assert type( new_game_request_data["max_players"] ) == int, "max_players must be an integer"
        assert new_game_request_data["creator_type"] in [ "User", "Group" ], "creator_type must be either User or Group"
    except AssertionError as e:
        return await make_response( jsonify({
            "error" : f"Validation failed: { str(e) }",
            "success" : False
        }), 400 )
        
    place_year : int = new_game_request_data["place_year"]
    if place_year not in [ 2021 ]:
        return await make_response( jsonify({
            "error" : "Unsupported place_year",
            "success" : False
        }), 400 )
    requested_process_year = ProcessYear( place_year )
    assigned_network_port : int = await get_rccservice_gameserver_port()
    if server_config.is_quilkin_enabled:
        try:
            new_quilkin_proxy = QuilkinController(
                proxy_target_host = "127.0.0.1",
                proxy_listen_port = assigned_network_port,
                proxy_target_port = assigned_network_port + server_config.quilkin_port_offset
            )
            new_quilkin_proxy.start_quilkin()
        except Exception as e:
            logging.error(f"_start_new_game_handler > Failed to start Quilkin proxy: {str(e)}")
            return await make_response( jsonify({
                "error" : "Failed to start Quilkin proxy",
                "success" : False
            }), 500 )
    
    new_rcc_instance : RCCService = await get_rcc_instance( requested_process_year, start_job_watcher = False )
    OpenGameJSON = SoapMessageFormatter.FormatGameOpenJSON(
        PlaceId = new_game_request_data["place_id"],
        CreatorId = new_game_request_data["creator_id"],
        CreatorType = new_game_request_data["creator_type"],
        JobId = new_game_request_data["job_id"],
        ApiKey = new_game_request_data["api_key"],
        MaxPlayers = new_game_request_data["max_players"],
        PortNumber = ( assigned_network_port + server_config.quilkin_port_offset ) if server_config.is_quilkin_enabled else assigned_network_port,
        MachineAddress = "127.0.0.1",
        UniverseId = new_game_request_data["universe_id"],
        GameCode = new_game_request_data["GameCode"] if "GameCode" in new_game_request_data else None,
        VipOwnerId = new_game_request_data["VipOwnerId"] if "VipOwnerId" in new_game_request_data else None
    )
    OpenJobResponse : SOAPResponse = await new_rcc_instance.send_open_job_request(
        job_id = new_game_request_data["job_id"],
        job_expiration = 60 * 60 * 24,
        assigned_cores = 1 if new_game_request_data["max_players"] <= 50 else 2,
        script_name = "OpenGame",
        run_script = OpenGameJSON,
        script_arguments = []   
    )
    await new_rcc_instance.start_job_watcher()
    if OpenJobResponse.status_code != 200:
        logging.error(f"_start_new_game_handler > Failed to send OpenGame request to RCC instance, status code {OpenJobResponse.status_code} - { OpenJobResponse.content }. Dropping request {new_game_request_data['job_id']}")
        return await make_response( jsonify({
            "error" : "Failed to send OpenGame request to RCC instance",
            "success" : False
        }), 500 )
    if server_config.is_quilkin_enabled:
        await new_rcc_instance.attach_quilkin_controller( new_quilkin_proxy )
    running_rcc_instances.append( new_rcc_instance )
    new_rcc_instance.start_time = time.time()
    new_rcc_instance.assigned_server_uuid = new_game_request_data["job_id"]
    new_rcc_instance.on_instance_killed_callback = on_instance_killed_callback
    logging.info(f"_start_new_game_handler > Successfully started new game {new_game_request_data['job_id']} on proxy port {assigned_network_port}, assigned RCC instance {new_rcc_instance.process.pid}")
    return await make_response( jsonify({
        "success" : True,
        "port" : assigned_network_port
    }), 200 )

@quart_app.route("/close_game", methods = [ "POST" ])
async def _close_game_handler():
    global running_rcc_instances
    close_game_request_data = json.loads(
        ( await get_decoded_data() ).decode('utf-8')
    )
    
    try:
        assert "job_id" in close_game_request_data, "job_id is required"
        assert type( close_game_request_data["job_id"] ) == str, "job_id must be a string"
    except AssertionError as e:
        return await make_response( jsonify({
            "error" : f"Validation failed: { str(e) }",
            "success" : False
        }), 400 )

    target_rcc_instance : RCCService | None = None
    for rcc_instance in running_rcc_instances:
        if rcc_instance.assigned_server_uuid == close_game_request_data["job_id"]:
            target_rcc_instance = rcc_instance
            break
    if target_rcc_instance is None:
        return await make_response( jsonify({
            "error" : "Target server not found",
            "success" : False
        }), 404 )
        
    target_rcc_instance.kill_rcc("Close requested by close_game endpoint")
    return await make_response( jsonify({
        "success" : True
    }), 200 )

@quart_app.route("/thumbnail_render", methods = [ "POST" ])
async def _thumbnail_render_handler():
    thumbnail_request_data = json.loads(
        ( await get_decoded_data() ).decode('utf-8')
    )
    
    try:
        assert "thumbnail_request_type" in thumbnail_request_data, "thumbnail_request_type is required"
        assert type( thumbnail_request_data["thumbnail_request_type"] ) == int, "thumbnail_request_type must be an integer"
        try:
            ThumbnailRequestTypes( thumbnail_request_data["thumbnail_request_type"] )
        except:
            raise AssertionError("thumbnail_request_type is not a valid ThumbnailRequestTypes enum value")
        assert "user_id" in thumbnail_request_data, "user_id is required"
        assert ( type( thumbnail_request_data["user_id"] ) == int ) or thumbnail_request_data["user_id"] is None, "user_id must be an integer or null"
        assert "asset_id" in thumbnail_request_data, "asset_id is required"
        assert ( type( thumbnail_request_data["asset_id"] ) == int ) or thumbnail_request_data["asset_id"] is None, "asset_id must be an integer or null"
        assert "width" in thumbnail_request_data, "width is required"
        assert type( thumbnail_request_data["width"] ) == int, "width must be an integer"
        assert "height" in thumbnail_request_data, "height is required"
        assert type( thumbnail_request_data["height"] ) == int, "height must be an integer"
        assert "format" in thumbnail_request_data, "format is required"
        assert type( thumbnail_request_data["format"] ) == str, "format must be a string"
        assert "request_id" in thumbnail_request_data, "request_id is required"
        assert type( thumbnail_request_data["request_id"] ) == str, "request_id must be a string"
    except AssertionError as e:
        return await make_response( jsonify({
            "error" : f"Validation failed: { str(e) }",
            "success" : False
        }), 400 )
    if thumbnail_request_queue.qsize() >= server_config.thumbnail_max_queue_size:
        return await make_response( jsonify({
            "error" : "Thumbnail request queue is full",
            "success" : False
        }), 503 )
        
    thumbnail_request_obj : ThumbnailRequest = ThumbnailRequest( thumbnail_request_data )
    thumbnail_request_queue.put( thumbnail_request_obj )
    
    return await make_response( jsonify({
        "success" : True,
        "request_id" : thumbnail_request_obj.request_id
    }), 200 )

if __name__ == '__main__':
    logging.info(f"AccessKey Read: {read_access_key()}")
    quart_app.run(
        host = '0.0.0.0',
        port = server_config.arbiter_port,
        debug = False,
        use_reloader = False
    )