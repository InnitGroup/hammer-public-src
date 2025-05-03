import aioboto3
import aiohttp
import hashlib
from app.extensions import redis_controller
from config import Config

web_config = Config()

async def get_s3_session():
    return aioboto3.Session(
        aws_access_key_id = web_config.AMAZON_S3_ACCESS_KEY,
        aws_secret_access_key = web_config.AMAZON_S3_SECRET_KEY,
        region_name = web_config.AMAZON_S3_REGION
    )
async def get_s3_url( object_name : str ) -> str:
    """
        Gets the URL of the given object in the given S3 bucket

        :param object_name: The name of the object to get the URL of

        :return: str
    """

    return f"{web_config.CDN_URL}/{object_name}"

class CDNHttpResponse():
    content : bytes
    status_code : int
    
    def __init__( self, content : bytes, status_code : int ):
        self.content = content
        self.status_code = status_code

async def download_file_from_cdn( object_name : str ) -> CDNHttpResponse:
    """
        Downloads the given file from the CDN instead of the S3 bucket

        :param object_name: The name of the object to download

        :return: bytes
    """

    async with aiohttp.ClientSession() as session:
        async with session.get( f"{web_config.CDN_URL}/{object_name}" ) as response:
            return CDNHttpResponse( await response.read(), response.status )

async def does_object_exist_in_s3( object_name : str, bucket_name : str = web_config.AMAZON_S3_BUCKET_NAME, bypass_cache : bool = False ) -> bool:
    """
        Checks if the given object name exists in the given S3 bucket

        :param object_name: The name of the object to check for
        :param bucket_name: The name of the bucket to check in
        :param bypass_cache: Whether or not to bypass the cache

        :return: bool
    """

    key_name : str = f"s3_object_exists_v2_{bucket_name}_{object_name}"
    if not bypass_cache and await redis_controller.exists( key_name ) > 0:
        return await redis_controller.get( key_name ) == "1"

    s3_session = await get_s3_session()
    async with s3_session.client( "s3" ) as s3_client:
        try:
            await s3_client.head_object( Bucket = bucket_name, Key = object_name )
            await redis_controller.set( key_name, "1", ex = 60 * 60 * 24 * 14 )
            return True
        except:
            return False

async def upload_bytes_to_s3( 
    content : bytes,
    bucket_name : str = web_config.AMAZON_S3_BUCKET_NAME,
    name_overwrite : str | None = None,
    content_type : str = "application/octet-stream",
    skip_if_exists : bool = True
) -> str:
    """
        Uploads the given bytes to the given S3 bucket

        :param content: The content to upload
        :param bucket_name: The name of the bucket to upload to
        :param name_overwrite: The name to save the file as
        :param content_type: The content type of the file
        :param skip_if_exists: Whether to skip the upload if the file already exists

        :return: the url of the uploaded file
    """

    s3_session = await get_s3_session()
    if type( content ) == str:
        content = content.encode()

    if name_overwrite is None:
        name_overwrite = hashlib.sha512( content ).hexdigest()

    if skip_if_exists and await does_object_exist_in_s3( name_overwrite, bucket_name ):
        return f"{web_config.CDN_URL}/{name_overwrite}"

    async with s3_session.client( "s3" ) as s3_client:
        await s3_client.put_object(
            Bucket = bucket_name,
            Key = name_overwrite,
            Body = content,
            ContentType = content_type
        )
        return f"{web_config.CDN_URL}/{name_overwrite}"