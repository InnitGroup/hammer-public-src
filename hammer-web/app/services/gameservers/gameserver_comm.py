import time
import base64
import json
import aiohttp
import asyncio
import zstd
import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.models.gameserver import GameServer

from config import Config

config = Config()

async def sign_content( content : bytes ) -> str:
    """
        Signs the given content using the gameserver private key

        :param content: The content to sign

        :returns: str
    """
    assert isinstance( content, bytes ), "content must be a bytes object"

    with open( config.GAMESERVER_COMM_PRIVATE_KEY_LOCATION, "rb" ) as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )

    signature = private_key.sign(
        content,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    return base64.b64encode( signature ).decode( "utf-8" )

class GameServerHttpResponse():
    status_code : int
    response_data : dict

    def __init__( self, status_code : int, response_data : dict ) -> None:
        self.status_code = status_code
        self.response_data = response_data

async def perform_get(
    TargetGameserver : GameServer,
    Endpoint : str,
    AdditionalHeaders : dict = {},

    RequestTimeout : int = 10
) -> GameServerHttpResponse:
    """
        Performs a GET request to the given gameserver

        :param TargetGameserver: The gameserver to send the request to
        :param Endpoint: The endpoint to send the request to
        :param AdditionalHeaders: Additional headers to send with the request
        :param RequestTimeout: The amount of time before the request times out

        :returns: GameServerHttpResponse
    """
    assert isinstance( TargetGameserver, GameServer ), "TargetGameserver must be an instance of GameServer"
    assert isinstance( Endpoint, str ), "Endpoint must be a string"
    assert isinstance( AdditionalHeaders, dict ), "AdditionalHeaders must be a dictionary"

    RequestTimestamp = time.time()
    signed_content = await sign_content( f'{RequestTimestamp}\nGET'.encode( 'utf-8' ) )
    ReqSignature = f"{str(RequestTimestamp)}|{ signed_content }"

    session_timeout = aiohttp.ClientTimeout(total = None, sock_connect = RequestTimeout, sock_read = RequestTimeout)
    async with aiohttp.ClientSession( timeout = session_timeout ) as session:
        async with session.get(
            url = f"http://{TargetGameserver.arbiter_ip}:{TargetGameserver.arbiter_port}/{Endpoint}",
            headers = {
                "User-Agent": "HAMMER-Gameserver-Communication/1.1",
                "X-Hammer-Request-Signature": ReqSignature
            }
        ) as response:
            response_data : bytes = await response.content.read()
            if response.headers.get( "Content-Encoding", None ) == "zstd":
                response_data = zstd.decompress( response_data )
            return GameServerHttpResponse(
                status_code = response.status,
                response_data = json.loads( response_data )
            )

async def perform_post(
    TargetGameserver : GameServer,
    Endpoint : str,
    JSONData : dict | list = {},
    AdditionalHeaders : dict = {},

    RequestTimeout : int = 10
) -> aiohttp.ClientResponse:
    """
        Performs a POST request to the given gameserver

        :param TargetGameserver: The gameserver to send the request to
        :param Endpoint: The endpoint to send the request to
        :param JSONData: The JSON data to send with the request
        :param AdditionalHeaders: Additional headers to send with the request
        :param RequestTimeout: The amount of time before the request times out

        :returns: GameServerHttpResponse
    """
    assert isinstance( TargetGameserver, GameServer ), "TargetGameserver must be an instance of GameServer"
    assert isinstance( Endpoint, str ), "Endpoint must be a string"
    assert isinstance( JSONData, ( dict, list ) ), "JSONData must be a dictionary or list"
    assert isinstance( AdditionalHeaders, dict ), "AdditionalHeaders must be a dictionary"

    RequestTimestamp = time.time()
    compressed_content = zstd.compress( json.dumps( JSONData ).encode( "utf-8" ) )
    signed_content = await sign_content( f"{RequestTimestamp}\nPOST\n".encode( "utf-8" ) + compressed_content )
    ReqSignature = f"{str(RequestTimestamp)}|{signed_content}"

    session_timeout = aiohttp.ClientTimeout(total = None, sock_connect = RequestTimeout, sock_read = RequestTimeout)
    async with aiohttp.ClientSession( timeout = session_timeout ) as session:
        async with session.post(
            url = f"http://{TargetGameserver.arbiter_ip}:{TargetGameserver.arbiter_port}/{Endpoint}",
            headers = {
                "User-Agent": "HAMMER-Gameserver-Communication/1.1",
                "X-Hammer-Request-Signature": ReqSignature,
                "Content-Type": "application/json",
                "Content-Encoding": "zstd"
            },
            data = compressed_content
        ) as response:
            response_data = await response.content.read()
            if response.headers.get( "Content-Encoding", None ) == "zstd":
                response_data = zstd.decompress( response_data )
            return GameServerHttpResponse(
                status_code = response.status,
                response_data = json.loads( response_data )
            )