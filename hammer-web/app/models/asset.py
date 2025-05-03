from datetime import datetime

from app.extensions import db
from app.enums.CreatorType import CreatorType
from app.enums.AssetType import AssetType
from app.enums.AssetGenre import AssetGenre
from app.enums.ModerationStatus import ModerationStatus

class Asset( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True, nullable = False )
    rbx_asset_id = db.Column( db.BigInteger, nullable = True, default = None ) 
    name = db.Column( db.Text, nullable = False, index = True, default = "" )
    description = db.Column( db.Text, nullable = False, default = "" )

    asset_type = db.Column( db.Enum( AssetType ), nullable = False, index = True )
    asset_genre = db.Column( db.Enum( AssetGenre ), nullable = False, index = True )
    creator_id = db.Column( db.BigInteger, nullable = False, index = True )
    creator_type = db.Column( db.Enum( CreatorType ), nullable = False, index = True )

    created_at = db.Column( db.DateTime, nullable = False, index = True )
    updated_at = db.Column( db.DateTime, nullable = False, index = True )

    product_id = db.Column( db.BigInteger, db.ForeignKey( "product.id" ), nullable = True, index = True )

    moderation_status = db.Column( db.Enum( ModerationStatus ), nullable = False, default = ModerationStatus.AwaitingApproval )

    def __init__(
        self,
        name : str,
        description : str,
        asset_type : AssetType,

        creator_id : int = 2, # Defaults to the UGC user
        creator_type : CreatorType = CreatorType.User,

        asset_genre : AssetGenre = AssetGenre.All,
        moderation_status : ModerationStatus = ModerationStatus.AwaitingApproval,
        
        product_id : int | None = None,

        asset_id_override : int | None = None,
        roblox_asset_id : int | None = None
    ):
        self.name = name
        self.description = description
        self.asset_type = asset_type
        self.asset_genre = asset_genre
        self.creator_id = creator_id
        self.creator_type = creator_type
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.moderation_status = moderation_status
        self.product_id = product_id

        if asset_id_override is not None:
            self.id = asset_id_override
        if roblox_asset_id is not None:
            self.rbx_asset_id = roblox_asset_id

    def __repr__( self ):
        return f"<Asset {self.id}, {self.name}>"