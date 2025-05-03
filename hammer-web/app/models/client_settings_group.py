from app.extensions import db
from datetime import datetime

class ClientSettingsGroup( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    name = db.Column( db.String( 255 ), nullable = False )
    description = db.Column( db.Text, nullable = False )

    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )
    api_key = db.Column( db.String( 255 ), nullable = True )

    gameserver_only = db.Column( db.Boolean, nullable = False, default = False )

    def __init__( self, name : str, description : str, api_key : str, gameserver_only : bool = False ):
        self.name = name
        self.description = description
        self.api_key = api_key
        self.gameserver_only = gameserver_only

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def __repr__( self ):
        return f"<ClientSettingsGroup {self.id}>"