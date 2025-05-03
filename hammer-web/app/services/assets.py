import redis_lock
import logging
import hashlib
from sqlalchemy import or_

from app.services import s3manager
from app.services.roblox_api import fetch_asset_info, fetch_bundle_info, fetch_asset_bytes_from_assetdelivery, RobloxAPIExceptions
from app.models.asset import Asset
from app.models.asset_version import AssetVersion
from app.models.bundle import Bundle
from app.models.bundle_item import BundleItem
from app.models.product import Product
from app.enums.AssetType import AssetType
from app.enums.CreatorType import CreatorType
from app.enums.ModerationStatus import ModerationStatus
from app.enums.BundleType import BundleType
from app.enums.ProductType import ProductType
from app.extensions import db, redis_controller, sync_redis_controller
from app.util import RBXMesh

from config import Config

web_config = Config()

class AssetServiceExceptions():
    class AssetTypeNotAllowed(Exception):
        pass
    class AssetDoesNotExistOnRoblox(Exception):
        pass
    class AssetDownloadDenied(Exception):
        pass
    class AssetMigrationBlocked(Exception):
        pass
    class InternalServiceError(Exception):
        pass
    
async def GetAssetById( AssetId : int ) -> Asset | None:
    if isinstance( AssetId, Asset ):
        return AssetId
    assert isinstance( AssetId, int ), "AssetId must be an integer"
    return Asset.query.filter_by( id = AssetId ).first()

bundleTypeStrToEnum = {
    "BodyParts": BundleType.BodyParts,
    "Animations": BundleType.Animations,
    "Shoes": BundleType.Shoes,
    "DynamicHeads": BundleType.DynamicHeads,
    "DynamicHeadAvatar": BundleType.DynamicHeadAvatar
}

async def CreateBundle(
    name : str,
    description : str,
    bundle_type : BundleType = BundleType.BodyParts,
    creator_id : int = 1,
    creator_type : CreatorType = CreatorType.User,
    rbx_bundle_id : int | None = None,
    
    bundle_id_override : int | None = None
) -> Bundle:
    NewBundle : Bundle = Bundle(
        name = name,
        description = description,
        bundle_type = bundle_type,
        creator_id = creator_id,
        creator_type = creator_type,
        rbx_bundle_id = rbx_bundle_id,
        
        bundle_id_override = bundle_id_override
    )
    db.session.add( NewBundle )
    db.session.commit()
    
    newProduct : Product = Product(
        product_type = ProductType.BundleProduct
    )
    db.session.add( newProduct )
    db.session.commit()
    
    NewBundle.product_id = newProduct.id
    db.session.commit()
    
    return NewBundle
async def MigrateRobloxBundle(
    BundleId : int,
    AllowedBundleTypes : list [ BundleType ] = [
        BundleType.BodyParts, BundleType.Animations
    ],
    CreatorId : int = 1, # Defaults to the ROBLOX user
    CreatorType : CreatorType = CreatorType.User,
    KeepRobloxBundleId : bool = True,
    KeepBundleInfo : bool = True
) -> Bundle:
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"migrate_bundle_{BundleId}", expire = 60 ) as lock:
        BundleObj : Bundle | None = Bundle.query.filter(
            or_(
                Bundle.id == BundleId,
                Bundle.rbx_bundle_id == BundleId
            )
        ).first()
        if BundleObj is not None:
            return BundleObj
        
        try:
            BundleInfo : dict = await fetch_bundle_info( bundle_id = BundleId )
        except RobloxAPIExceptions.AssetNotFound:
            raise AssetServiceExceptions.AssetDoesNotExistOnRoblox( f"Bundle {BundleId} does not exist on Roblox" )
        except RobloxAPIExceptions.UnexpectedStatusCode as e:
            logging.error( f"services.assets > MigrateRobloxBundle, unexpected status code when fetching bundle info for bundle {BundleId}, {e}" )
            raise AssetServiceExceptions.AssetDoesNotExistOnRoblox( f"Bundle {BundleId} does not exist on Roblox" )
        except Exception as e:
            logging.error( f"services.assets > MigrateRobloxBundle, exception raised: {e}" )
            raise AssetServiceExceptions.InternalServiceError( f"Failed to fetch bundle info for bundle {BundleId}: {e}" )
        
        try:
            assert "bundleType" in BundleInfo, "bundleType not found in bundle info"
            assert "name" in BundleInfo, "name not found in bundle info"
            assert "description" in BundleInfo, "description not found in bundle info"
            assert "items" in BundleInfo, "items not found in bundle info"
            assert isinstance( BundleInfo["bundleType"], str ), "bundleType must be a string"
            assert isinstance( BundleInfo["name"], str ), "name must be a string"
            assert isinstance( BundleInfo["description"], str ), "description must be a string"
            assert isinstance( BundleInfo["items"], list ), "items must be a list"
        except AssertionError as e:
            logging.error( f"services.assets > MigrateRobloxBundle, exception raised during data validation: {e}" )
            raise AssetServiceExceptions.InternalServiceError( f"Failed to migrate bundle {BundleId}" )
        
        requestedBundleType : BundleType = bundleTypeStrToEnum[ BundleInfo["bundleType"] ]
        if requestedBundleType not in AllowedBundleTypes:
            raise AssetServiceExceptions.AssetTypeNotAllowed( f"Bundle type {BundleType( BundleInfo['bundleType'] )} not allowed" )
        newBundle : Bundle = await CreateBundle(
            name = BundleInfo["name"] if KeepBundleInfo else f"Bundle {BundleId}",
            description = BundleInfo["description"] if KeepBundleInfo else f"Bundle {BundleId}",
            bundle_type = requestedBundleType,
            creator_id = CreatorId,
            creator_type = CreatorType,
            rbx_bundle_id = BundleId,
            
            bundle_id_override = BundleId if KeepRobloxBundleId else None
        )
        
        for item in BundleInfo["items"]:
            try:
                assert "type" in item, "type not found in item"
                assert "id" in item, "id not found in item"
                assert isinstance( item["type"], str ), "type must be a string"
                assert isinstance( item["id"], int ), "id must be an integer"
            except AssertionError as e:
                logging.error( f"services.assets > MigrateRobloxBundle, exception raised during data validation: {e}" )
                raise AssetServiceExceptions.InternalServiceError( f"Failed to migrate bundle {BundleId}" )
            
            if item["type"] == "Asset":
                try:
                    await MigrateAsset(
                        AssetId = item["id"],
                        AllowedAssetTypes = [],
                        CreatorId = CreatorId,
                        CreatorType = CreatorType,
                        KeepRobloxAssetId = False,
                        KeepAssetInfo = True,
                        RenderAssetThumbnail = False
                    )
                except AssetServiceExceptions.AssetDoesNotExistOnRoblox:
                    pass
                except AssetServiceExceptions.AssetMigrationBlocked:
                    pass
                except AssetServiceExceptions.AssetTypeNotAllowed:
                    pass
                except AssetServiceExceptions.InternalServiceError as e:
                    logging.error( f"services.assets > MigrateRobloxBundle, failed to migrate asset {item['id']}: {e}" )
                    raise AssetServiceExceptions.InternalServiceError( f"Failed to migrate bundle {BundleId}" )
                except Exception as e:
                    logging.error( f"services.assets > MigrateRobloxBundle, failed to migrate asset {item['id']}: {e}" )
                    raise AssetServiceExceptions.InternalServiceError( f"Failed to migrate bundle {BundleId}" )
            else:
                continue
            newBundleItem : BundleItem = BundleItem(
                bundle_id = newBundle.id,
                asset_id = item["id"]
            )
            db.session.add( newBundleItem )
        db.session.commit()
        
        return newBundle

async def CreateNewAsset(
    name : str = "Asset",
    description : str = "",
    asset_type : AssetType = AssetType.Image,
    creator_id : int = 2,
    creator_type : CreatorType = CreatorType.User,
    moderation_status : ModerationStatus = ModerationStatus.Approved,
 
    asset_id_override : int | None = None,
    roblox_asset_id : int | None = None,
    
    content_hash : str | None = None,
    uploader_user_id : int | None = None
) -> Asset:
    NewAsset : Asset = Asset(
        name = name,
        description = description,
        asset_type = asset_type,
        creator_id = creator_id,
        creator_type = creator_type,
        moderation_status = moderation_status,
        
        asset_id_override = asset_id_override,
        roblox_asset_id = roblox_asset_id
    )
    db.session.add( NewAsset )
    db.session.commit()
    
    NewProduct : Product = Product(
        product_type = ProductType.UserProduct,
        asset_id = NewAsset.id,
        asset_type = asset_type
    )
    db.session.add( NewProduct )
    db.session.commit()
    
    NewAsset.product_id = NewProduct.id
    db.session.commit()
    
    if content_hash is not None:
        await CreateNewAssetVersion(
            AssetObj = NewAsset,
            NewVersionContentHash = content_hash,
            UploaderUserId = uploader_user_id
        )
    
    return NewAsset

async def MigrateAsset(
    AssetId : int,
    AllowedAssetTypes : list [ AssetType ] = [ 
        AssetType.Image, AssetType.Audio, AssetType.Mesh, AssetType.Lua, AssetType.Model, AssetType.Decal,
        AssetType.Animation, AssetType.SolidModel, AssetType.MeshPart, AssetType.FallAnimation, AssetType.IdleAnimation,
        AssetType.JumpAnimation, AssetType.RunAnimation, AssetType.SwimAnimation, AssetType.WalkAnimation, AssetType.PoseAnimation
    ],
    CreatorId : int = 2, # Defaults to the UGC user
    CreatorType : CreatorType = CreatorType.User,
    KeepRobloxAssetId : bool = True,
    KeepAssetInfo : bool = True,
    RenderAssetThumbnail : bool = True
) -> Asset:
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"migrate_asset_{AssetId}", expire = 60 ) as lock:
        AssetObj : Asset | None = Asset.query.filter(
            or_(
                Asset.id == AssetId,
                Asset.rbx_asset_id == AssetId
            )
        ).first()
        if AssetObj is not None:
            return AssetObj
        
        AssetMigrationBlockedKeyName : str = f"asset_migration_blocked_{AssetId}"
        if await redis_controller.exists( AssetMigrationBlockedKeyName ) > 0:
            raise AssetServiceExceptions.AssetMigrationBlocked( f"Asset {AssetId} migration is blocked" )
        
        try:
            AssetInfo : dict = await fetch_asset_info( asset_id = AssetId )
        except RobloxAPIExceptions.AssetNotFound:
            await redis_controller.set( AssetMigrationBlockedKeyName, "1", ex = 60 * 60 * 24 )
            raise AssetServiceExceptions.AssetDoesNotExistOnRoblox( f"Asset {AssetId} does not exist on Roblox" )
        except RobloxAPIExceptions.UnexpectedStatusCode as e:
            logging.error( f"services.assets > MigrateAsset, unexpected status code when fetching asset info for asset {AssetId}, {e}" )
            raise AssetServiceExceptions.AssetDoesNotExistOnRoblox( f"Asset {AssetId} does not exist on Roblox" )
        except Exception as e:
            logging.error( f"services.assets > MigrateAsset, exception raised: {e}" )
            raise AssetServiceExceptions.InternalServiceError( f"Failed to fetch asset info for asset {AssetId}: {e}" )
        
        try:
            assert "AssetTypeId" in AssetInfo, "AssetTypeId not found in asset info"
            assert "Name" in AssetInfo, "Name not found in asset info"
            assert "Description" in AssetInfo, "Description not found in asset info"
            assert isinstance( AssetInfo["AssetTypeId"], int ), "AssetTypeId must be an integer"
            assert isinstance( AssetInfo["Name"], str ), "Name must be a string"
            assert isinstance( AssetInfo["Description"], str ), "Description must be a string"
        except AssertionError as e:
            logging.error( f"services.assets > MigrateAsset, exception raised during data validation: {e}" )
            raise AssetServiceExceptions.InternalServiceError( f"Failed to migrate asset {AssetId}" )

        requestedAssetType : AssetType = AssetType( AssetInfo["AssetTypeId"] )
        if requestedAssetType not in AllowedAssetTypes and len( AllowedAssetTypes ) > 0:
            raise AssetServiceExceptions.AssetTypeNotAllowed( f"Asset type {AssetType( AssetInfo['AssetTypeId'] )} not allowed" )
        

        try:
            AssetContentBytes : bytes = await fetch_asset_bytes_from_assetdelivery( asset_id = AssetId )
        except RobloxAPIExceptions.AssetNotFound:
            raise AssetServiceExceptions.AssetDoesNotExistOnRoblox( f"Asset {AssetId} does not exist on Roblox" )
        except RobloxAPIExceptions.AccessDenied:
            await redis_controller.set( AssetMigrationBlockedKeyName, "1", ex = 60 * 60 * 24 )
            raise AssetServiceExceptions.AssetDownloadDenied( f"Access denied to download asset {AssetId}" )
        except RobloxAPIExceptions.UnexpectedStatusCode:
            raise AssetServiceExceptions.InternalServiceError( f"Failed to fetch asset bytes for asset {AssetId}" )
        except RobloxAPIExceptions.InternalServiceError:
            raise AssetServiceExceptions.InternalServiceError( f"Failed to fetch asset bytes for asset {AssetId}" )
        except Exception as e:
            logging.error( f"services.assets > MigrateAsset, exception raised: {e}" )
            raise AssetServiceExceptions.InternalServiceError( f"Failed to fetch asset bytes for asset {AssetId}" )
        
        if requestedAssetType == AssetType.Mesh:
            originalAssetContentBytes : bytes = AssetContentBytes
            try:
                if RBXMesh.get_mesh_version( AssetContentBytes ) not in [ 1.0, 1.1, 2.0 ]:
                    meshData : RBXMesh.FileMeshData = RBXMesh.read_mesh_data( AssetContentBytes )
                    AssetContentBytes = RBXMesh.export_mesh_v2( meshData )
            except Exception as e:
                logging.warning( f"services.assets > MigrateAsset, failed to downgrade mesh {AssetId}: {e}" )
                AssetContentBytes = originalAssetContentBytes

        try:
            AssetContentBytes = AssetContentBytes.replace(
                "roblox.com".encode("utf-8"),
                web_config.BaseDomain.encode("utf-8")
            )
        except Exception as e:
            pass
        
        AssetName : str = AssetInfo["Name"] if KeepAssetInfo else f"Asset {AssetId}"
        AssetDescription : str = AssetInfo["Description"] if KeepAssetInfo else f"Asset {AssetId}"

        NewAsset : Asset = await CreateNewAsset(
            name = AssetName,
            description = AssetDescription,
            asset_type = requestedAssetType,
            creator_id = CreatorId,
            creator_type = CreatorType,
            moderation_status = ModerationStatus.Approved,
            asset_id_override = AssetId if KeepRobloxAssetId else None,
            roblox_asset_id = AssetId
        )
        
        await CreateNewAssetVersionWithBytes(
            AssetObj = NewAsset,
            AssetBytes = AssetContentBytes,
            UploaderUserId = None,
            ContentType = "application/octet-stream" if requestedAssetType != AssetType.Image else "image/png"
        )
        
        if RenderAssetThumbnail:
            from app.services import thumbnailer
            await thumbnailer.render_asset_thumbnail( asset_obj = NewAsset )
        
        return NewAsset

async def GetAssetVersionByVersionNumber( AssetObj : Asset | int, VersionNumber : int ) -> AssetVersion | None:
    AssetObj : Asset = await GetAssetById( AssetObj )
    return AssetVersion.query.filter_by( asset_id = AssetObj.id, version_number = VersionNumber ).first()

async def GetLatestAssetVersion( AssetObj : Asset | int ) -> AssetVersion:
    AssetObj : Asset = await GetAssetById( AssetObj )
    return AssetVersion.query.filter_by( asset_id = AssetObj.id ).order_by( AssetVersion.version_number.desc() ).first()

async def CreateNewAssetVersionWithBytes( AssetObj : Asset | int, AssetBytes : bytes, UploaderUserId : int = None, ContentType : str = "application/octet-stream") -> AssetVersion:
    AssetObj : Asset = await GetAssetById( AssetObj )
    
    AssetContentHash : str = hashlib.sha512( AssetBytes ).hexdigest()
    try:
        await s3manager.upload_bytes_to_s3(
            content = AssetBytes,
            bucket_name = web_config.AMAZON_S3_BUCKET_NAME,
            name_overwrite = AssetContentHash,
            content_type = ContentType,
        )
    except Exception as e:
        logging.error( f"services.assets > CreateNewAssetVersionWithBytes, failed to upload asset {AssetObj.id} to S3: {e}" )
        raise AssetServiceExceptions.InternalServiceError( f"Failed to upload asset {AssetObj.id} to S3" )
    
    return await CreateNewAssetVersion(
        AssetObj = AssetObj,
        NewVersionContentHash = AssetContentHash,
        UploaderUserId = UploaderUserId
    )

async def CreateNewAssetVersion( AssetObj : Asset | int, NewVersionContentHash : str, UploaderUserId : int = None ) -> AssetVersion:
    AssetObj : Asset = await GetAssetById( AssetObj )
    
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"asset_version_creation_lock:{AssetObj.id}", expire = 10, auto_renewal = True ):
        LatestVersion : AssetVersion = await GetLatestAssetVersion( AssetObj )
        if LatestVersion is not None and LatestVersion.content_hash == NewVersionContentHash:
            return LatestVersion
        
        NewAssetVersion : AssetVersion = AssetVersion(
            asset_id = AssetObj.id,
            version_number = LatestVersion.version_number + 1 if LatestVersion is not None else 1,
            content_hash = NewVersionContentHash,
            uploader_id = UploaderUserId
        )

        db.session.add( NewAssetVersion )
        db.session.commit()