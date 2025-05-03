from app.extensions import db
from app.enums.FlagValueType import FlagValueType

class ClientSettingsValue( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True, autoincrement = True )
    parent_group_id = db.Column( db.BigInteger, db.ForeignKey( "client_settings_group.id" ), nullable = False, index = True )
    key_name = db.Column( db.String( 512 ), nullable = False, index = True )
    value = db.Column( db.Text, nullable = False )
    value_type = db.Column( db.Enum( FlagValueType ), nullable = False, index = True)

    def __init__( self, parent_group_id : int, key_name : str, value : str, value_type : FlagValueType ):
        self.parent_group_id = parent_group_id
        self.key_name = key_name
        self.value = value
        self.value_type = value_type

    def __repr__( self ):
        return f"<ClientSettingsValue {self.id}>"