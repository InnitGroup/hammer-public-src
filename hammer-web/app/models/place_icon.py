from app.extensions import db
from datetime import datetime

class PlaceIcon( db.Model ):
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    parent_place_id = db.Column(db.BigInteger, db.ForeignKey('place.id'), nullable=False, index=True)
    asset_id = db.Column(db.BigInteger, nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, nullable=False)
    def __init__(self, parent_place_id, asset_id, created_at=None):
        self.parent_place_id = parent_place_id
        self.asset_id = asset_id
        
        if created_at is None:
            created_at = datetime.utcnow()
        self.created_at = created_at