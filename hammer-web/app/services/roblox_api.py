"""
    Service to fetch information from the Roblox API
"""

import aiohttp
import logging
import json

from app.extensions import redis_controller
from config import Config

web_config = Config()

class RobloxAPIExceptions():
    class UnexpectedStatusCode( Exception ):
        pass
    class AssetNotFound( Exception ):
        pass
    class AccessDenied( Exception ):
        pass
    class InternalServiceError( Exception ):
        pass

async def _get_aiosession() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        headers = {
            "User-Agent": "Roblox/WinInet",
            "Roblox-Place-Id": "1818",
            "Requester": "Client"
        }   
    )
    
async def fetch_bundle_info( bundle_id : int, bypass_cache : bool = False ) -> dict:
    """
        Fetches information about a bundle from catalog.roblox.com
        
        :param bundle_id: The bundle ID to fetch information about
        :param bypass_cache: Whether or not to bypass the cache
        
        :return: dict
    """
    async def _fetch_from_marketplace_api() -> dict:
        async with await _get_aiosession() as aio_client_session:
            async with aio_client_session.get( f"https://catalog.roblox.com/v1/bundles/{bundle_id}/details" ) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return response_json
                elif response.status == 404:
                    raise RobloxAPIExceptions.AssetNotFound( f"Bundle {bundle_id} not found" )
                else:
                    raise RobloxAPIExceptions.UnexpectedStatusCode( f"Unexpected status code {response.status} when fetching bundle info" )
    
    if not bypass_cache and await redis_controller.exists( f"roblox_api_fetch_bundle_info_{bundle_id}" ) > 0:
        cached_results = await redis_controller.get( f"roblox_api_fetch_bundle_info_{bundle_id}" )
        return json.loads( cached_results )
    try:
        bundle_info_results = await _fetch_from_marketplace_api()
        await redis_controller.set( f"roblox_api_fetch_bundle_info_{bundle_id}", json.dumps( bundle_info_results ), ex = 60 * 60 * 24 * 7 )
        return bundle_info_results
    except RobloxAPIExceptions.AssetNotFound as e:
        raise e
    except RobloxAPIExceptions.UnexpectedStatusCode as e:
        raise e
    except aiohttp.ClientConnectionError:
        raise RobloxAPIExceptions.InternalServiceError( "Failed to connect to Roblox API" )
    except Exception as e:
        logging.error( f"services.roblox_api > fetch_bundle_info: {str(e)}" )
        raise RobloxAPIExceptions.InternalServiceError( "Failed to fetch bundle info" )

async def fetch_asset_info( asset_id : int, bypass_cache : bool = False ) -> dict:
    """
        Fetches information about a Roblox asset from economy.roblox.com

        :param asset_id: The asset ID to fetch information about
        :param bypass_cache: Whether or not to bypass the cache

        :return: dict
    """

    async def _fetch_from_economy_api() -> dict:
        async with await _get_aiosession() as aio_client_session:
            async with aio_client_session.get( f"https://economy.roblox.com/v2/developer-products/{asset_id}/info" ) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return response_json
                elif response.status == 404:
                    raise RobloxAPIExceptions.AssetNotFound( f"Asset {asset_id} not found" )
                else:
                    raise RobloxAPIExceptions.UnexpectedStatusCode( f"Unexpected status code {response.status} when fetching asset info" )
    
    if not bypass_cache and await redis_controller.exists( f"roblox_api_fetch_asset_info_{asset_id}" ) > 0:
        cached_results = await redis_controller.get( f"roblox_api_fetch_asset_info_{asset_id}" )
        return json.loads( cached_results )
    
    try:
        asset_info_results = await _fetch_from_economy_api()
        await redis_controller.set( f"roblox_api_fetch_asset_info_{asset_id}", json.dumps( asset_info_results ), ex = 60 * 60 * 24 * 7 )
        return asset_info_results
    except RobloxAPIExceptions.AssetNotFound as e:
        raise e
    except RobloxAPIExceptions.UnexpectedStatusCode as e:
        raise e
    except aiohttp.ClientConnectionError:
        raise RobloxAPIExceptions.InternalServiceError( "Failed to connect to Roblox API" )
    except Exception as e:
        logging.error( f"services.roblox_api > fetch_asset_info: {str(e)}" )
        raise RobloxAPIExceptions.InternalServiceError( "Failed to fetch asset info" )
    
async def fetch_asset_bytes_from_assetdelivery( asset_id : int, roblox_place_id : int = 1818 ) -> bytes:
    """
        Fetches the bytes of a Roblox asset from assetdelivery.roblox.com

        :param asset_id: The asset ID to fetch bytes for
        :param roblox_place_id: The place ID to fetch the asset from

        :return: bytes
    """

    async def _fetch_from_assetdelivery() -> bytes:
        async with await _get_aiosession() as aio_client_session:
            async with aio_client_session.get( url = f"https://assetdelivery.roblox.com/v1/asset?id={asset_id}", headers = { "Roblox-Place-Id": str( roblox_place_id )}) as response:
                if response.status == 200:
                    response_bytes = await response.read()
                    return response_bytes
                elif response.status == 404:
                    raise RobloxAPIExceptions.AssetNotFound( f"Asset {asset_id} not found" )
                elif response.status in [ 401, 403, 409 ]:
                    raise RobloxAPIExceptions.AccessDenied( f"Access denied to download asset {asset_id}" )
                else:
                    raise RobloxAPIExceptions.UnexpectedStatusCode( f"Unexpected status code {response.status} when fetching asset bytes" )
    
    try:
        return await _fetch_from_assetdelivery()
    except RobloxAPIExceptions.UnexpectedStatusCode as e:
        raise e
    except RobloxAPIExceptions.AssetNotFound as e:
        raise e
    except RobloxAPIExceptions.AccessDenied as e:
        raise e
    except aiohttp.ClientConnectionError:
        raise RobloxAPIExceptions.InternalServiceError( "Failed to connect to Roblox API" )
    except Exception as e:
        logging.error( f"services.roblox_api > fetch_asset_bytes_from_assetdelivery: {str(e)}" )
        raise RobloxAPIExceptions.InternalServiceError( "Failed to fetch asset bytes" )