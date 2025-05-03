from app.extensions import db
from app.enums.ModerationStatus import ModerationStatus
from datetime import datetime

class AssetThumbnail( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True, nullable = False )
    asset_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id" ), nullable = False, index = True )
    asset_version = db.Column( db.BigInteger, nullable = False, index = True )
    moderation_status = db.Column( db.Enum( ModerationStatus ), nullable = False, default = ModerationStatus.AwaitingApproval )
    created_at = db.Column( db.DateTime, nullable = False, index = True )
    content_hash = db.Column( db.Text, nullable = True, index = True )
    asset_3d_content_hash = db.Column( db.Text, nullable = True, index = True )

    def __init__( self, asset_id : int, asset_version : int, content_hash : str, moderation_status : ModerationStatus = ModerationStatus.AwaitingApproval, asset_3d_content_hash : str = None ):
        self.asset_id = asset_id
        self.asset_version = asset_version
        self.content_hash = content_hash
        self.created_at = datetime.utcnow()
        self.moderation_status = moderation_status
        self.asset_3d_content_hash = asset_3d_content_hash

    def __repr__( self ):
        return f"<AssetThumbnail {self.id}, asset_id={self.asset_id}, asset_version={self.asset_version}, created_at={self.created_at}>"