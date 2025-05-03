from app.extensions import db
from app.enums.RigType import RigType

class UserAvatar( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), primary_key = True )
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

    def __init__(
        self,
        user_id : int,
        rig_type : RigType = RigType.R6
    ):
        self.user_id = user_id
        self.rig_type = rig_type

    def __repr__( self ):
        return f"<UserAvatar user_id={self.user_id}, rig_type={self.rig_type}>"