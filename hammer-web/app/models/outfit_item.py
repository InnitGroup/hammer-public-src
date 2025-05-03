from app.extensions import db

class OutfitItem( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True )
    outfit_id = db.Column( db.BigInteger, db.ForeignKey( "outfit.id" ), index = True )
    asset_id = db.Column( db.BigInteger, db.ForeignKey( "asset.id" ), index = True )
    
    def __init__( self, outfit_id : int, asset_id : int ):
        self.outfit_id = outfit_id
        self.asset_id = asset_id
    
    def __repr__( self ):
        return f"<OutfitItem outfit_id={self.outfit_id}, asset_id={self.asset_id}>"