from app.extensions import db
from datetime import datetime

class PlaceDatastore( db.Model ):
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    universe_id = db.Column(db.BigInteger, db.ForeignKey('universe.id'), nullable=False, index=True)

    scope = db.Column(db.String(255), nullable=False, index=True)
    key = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.String(1024 * 1024), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, universe_id, scope, key, name, value, created_at=None, updated_at=None):
        self.universe_id = universe_id
        self.scope = scope
        self.key = key
        self.name = name
        self.value = value
        
        if created_at is None:
            created_at = datetime.utcnow()
        if updated_at is None:
            updated_at = datetime.utcnow()
        self.created_at = created_at
        self.updated_at = updated_at
    
    def __repr__(self):
        return '<PlaceDatastore %r>' % self.id