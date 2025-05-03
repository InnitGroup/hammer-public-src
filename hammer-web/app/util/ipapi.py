import aiohttp
import json
import logging
from config import Config
from app.extensions import redis_controller

web_config = Config()

class InvalidIPAddress(Exception):
    pass
class InternalServiceError(Exception):
    pass

async def fetch_ip_info( ip_address: str, bypass_cache : bool = False ) -> dict:
    """
        Fetches information about the given IP from ipapi.is
        Refer to documentation: https://ipapi.is/developers.html
    """
    ip_address_cache_key : str = f"ipapi_is:{ip_address}"
    if not bypass_cache and await redis_controller.exists( ip_address_cache_key ) > 0:
        return json.loads( await redis_controller.get( name = ip_address_cache_key ) )
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.ipapi.is?q={ip_address}&key={web_config.IPAPI_KEY}") as response:
                if response.status != 200:
                    raise InternalServiceError( "Internal service error" )
                
                ip_info : dict = await response.json()
                await redis_controller.set( name = ip_address_cache_key, value = json.dumps( ip_info ), ex = 60 * 60 * 24 )
                return ip_info
    except Exception as e:
        logging.error(f"util.ipapi.fetch_ip_info: {e}")
        raise InternalServiceError( "Internal service error" )