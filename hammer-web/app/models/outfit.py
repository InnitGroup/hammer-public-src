from app.extensions import db
from app.enums.RigType import RigType
from datetime import datetime

class Outfit( db.Model ):
    id = db.Column( db.BigInteger, primary_key = True )
    outfit_name = db.Column( db.Text, nullable = False )
    avatar_hash = db.Column( db.Text, nullable = False, index = True )
    creator_user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), index = True )
    rig_type = db.Column( db.Enum( RigType ), nullable = False, default = RigType.R6 )

    head_color_id = db.Column(db.Integer, nullable=False, default=1001) 
    torso_color_id = db.Column(db.Integer, nullable=False, default=1001)
    right_arm_color_id = db.Column(db.Integer, nullable=False, default=1001)
    left_arm_color_id = db.Column(db.Integer, nullable=False, default=1001)
    right_leg_color_id = db.Column(db.Integer, nullable=False, default=1001)
    left_leg_color_id = db.Column(db.Integer, nullable=False, default=1001)

    height_scale = db.Column(db.Float, nullable=False, default=1.0)
    width_scale = db.Column(db.Float, nullable=False, default=1.0)
    head_scale = db.Column(db.Float, nullable=False, default=1.0) 
    proportion_scale = db.Column(db.Float, nullable=False, default=1.0)
    body_type_scale = db.Column(db.Float, nullable=False, default=1.0)
    
    created_at = db.Column( db.DateTime, nullable = False )
    updated_at = db.Column( db.DateTime, nullable = False )

    def __init__(
        self,
        outfit_name : str,
        avatar_hash : str,
        creator_user_id : int,
        rig_type : RigType = RigType.R6
    ):
        self.outfit_name = outfit_name
        self.avatar_hash = avatar_hash
        self.creator_user_id = creator_user_id
        self.rig_type = rig_type
        
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def __repr__( self ):
        return f"<Outfit creator_user_id={self.creator_user_id}, rig_type={self.rig_type}>"