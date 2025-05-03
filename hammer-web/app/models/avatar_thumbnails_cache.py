from app.extensions import db
from app.enums.ThumbnailRequestTypes import ThumbnailRequestTypes
from datetime import datetime, timezone

class AvatarThumbnailsCache( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    avatar_hash = db.Column( db.String( 512 ), nullable = False, index = True )
    render_format = db.Column( db.String( 32 ), nullable = False, index = True )
    thumbnail_request_type = db.Column( db.Enum( ThumbnailRequestTypes ), nullable = False, index = True )
    content_hash = db.Column( db.String( 512 ), nullable = False )
    
    created_at = db.Column( db.DateTime, nullable = False )
    
    def __init__( self, avatar_hash : str, render_format : str, thumbnail_request_type : ThumbnailRequestTypes, content_hash : str ):
        self.avatar_hash = avatar_hash
        self.render_format = render_format
        self.thumbnail_request_type = thumbnail_request_type
        self.content_hash = content_hash
        self.created_at = datetime.now( timezone.utc )