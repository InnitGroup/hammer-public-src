from app.enums.RigType import RigType
from app.enums.AssetType import AssetType

class ScalingRule():
    minimum : float = 0
    maximum : float = 1
    increment : float = 0.01
    def __init__( self, minimum : float, maximum : float, increment : float ):
        self.minimum = minimum
        self.maximum = maximum
        self.increment = increment
    def to_dict( self ):
        return {
            "min": self.minimum,
            "max": self.maximum,
            "increment": self.increment
        }

class wearableAssetType():
    max_wearable : int = 1
    asset_type : AssetType = AssetType.TShirt
    user_facing_name : str = "T-Shirt"
    def __init__( self, max_wearable : int, asset_type : AssetType, user_facing_name : str ):
        self.max_wearable = max_wearable
        self.asset_type = asset_type
        self.user_facing_name = user_facing_name
    def to_dict( self ):
        return {
            "maxNumber": self.max_wearable,
            "id": self.asset_type.value,
            "name": self.user_facing_name
        }

class bodyColor():
    brickColorId : int = 1
    hexColor : str = "#FFFFFF"
    user_facing_name : str = "White"
    def __init__( self, brickColorId : int, hexColor : str, user_facing_name : str ):
        self.brickColorId = brickColorId
        self.hexColor = hexColor
        self.user_facing_name = user_facing_name
    def to_dict( self ):
        return {
            "brickColorId": self.brickColorId,
            "hexColor": self.hexColor,
            "name": self.user_facing_name
        }

class AvatarRules():
    playerAvatarTypes : list[RigType] = [ RigType.R6, RigType.R15 ]
    characterScales : dict[ str, ScalingRule ] = {
        "height": ScalingRule( minimum = 0.9, maximum = 1.05, increment = 0.01 ),
        "width": ScalingRule( minimum = 0.7, maximum = 1.0, increment = 0.01 ),
        "head": ScalingRule( minimum = 0.95, maximum = 1.0, increment = 0.01 ),
        "proportion": ScalingRule( minimum = 0.0, maximum = 1.0, increment = 0.01 ),
        "bodyType": ScalingRule( minimum = 0.0, maximum = 1.0, increment = 0.01 )
    }
    wearableAssetTypes : list[wearableAssetType] = [
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Face, user_facing_name = "Face" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Gear, user_facing_name = "Gear" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Head, user_facing_name = "Head" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.LeftArm, user_facing_name = "Left Arm" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.LeftLeg, user_facing_name = "Left Leg" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Pants, user_facing_name = "Pants" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.RightArm, user_facing_name = "Right Arm" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.RightLeg, user_facing_name = "Right Leg" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Shirt, user_facing_name = "Shirt" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.TShirt, user_facing_name = "T-Shirt" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.Torso, user_facing_name = "Torso" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.ClimbAnimation, user_facing_name = "Climb Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.DeathAnimation, user_facing_name = "Death Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.FallAnimation, user_facing_name = "Fall Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.IdleAnimation, user_facing_name = "Idle Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.JumpAnimation, user_facing_name = "Jump Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.RunAnimation, user_facing_name = "Run Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.SwimAnimation, user_facing_name = "Swim Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.WalkAnimation, user_facing_name = "Walk Animation" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.PoseAnimation, user_facing_name = "Pose Animation" ),
        wearableAssetType( max_wearable = 0, asset_type = AssetType.EmoteAnimation, user_facing_name = "Emote Animation" ),
        wearableAssetType( max_wearable = 3, asset_type = AssetType.Hat, user_facing_name = "Hat" ),
        wearableAssetType( max_wearable = 5, asset_type = AssetType.HairAccessory, user_facing_name = "Hair Accessory" ),
        wearableAssetType( max_wearable = 5, asset_type = AssetType.FaceAccessory, user_facing_name = "Face Accessory" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.NeckAccessory, user_facing_name = "Neck Accessory" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.ShoulderAccessory, user_facing_name = "Shoulder Accessory" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.FrontAccessory, user_facing_name = "Front Accessory" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.BackAccessory, user_facing_name = "Back Accessory" ),
        wearableAssetType( max_wearable = 1, asset_type = AssetType.WaistAccessory, user_facing_name = "Waist Accessory" )
    ]
    bodyColorsPalette : list[bodyColor] = [
        bodyColor( brickColorId = 361, hexColor = "#564236", user_facing_name = "Dirt brown" ),
        bodyColor( brickColorId = 192, hexColor = "#694028", user_facing_name = "Reddish brown" ),
        bodyColor( brickColorId = 217, hexColor = "#7C5C46", user_facing_name = "Brown" ),
        bodyColor( brickColorId = 153, hexColor = "#957977", user_facing_name = "Sand red" ),
        bodyColor( brickColorId = 359, hexColor = "#AF9483", user_facing_name = "Linen" ),
        bodyColor( brickColorId = 352, hexColor = "#C7AC78", user_facing_name = "Burlap" ),
        bodyColor( brickColorId = 5, hexColor = "#D7C59A", user_facing_name = "Brick yellow" ),
        bodyColor( brickColorId = 101, hexColor = "#DA867A", user_facing_name = "Medium red" ),
        bodyColor( brickColorId = 1007, hexColor = "#A34B4B", user_facing_name = "Dusty Rose" ),
        bodyColor( brickColorId = 1014, hexColor = "#AA5500", user_facing_name = "CGA brown" ),
        bodyColor( brickColorId = 38, hexColor = "#A05F35", user_facing_name = "Dark orange" ),
        bodyColor( brickColorId = 18, hexColor = "#CC8E69", user_facing_name = "Nougat" ),
        bodyColor( brickColorId = 125, hexColor = "#EAB892", user_facing_name = "Light orange" ),
        bodyColor( brickColorId = 1030, hexColor = "#FFCC99", user_facing_name = "Pastel brown" ),
        bodyColor( brickColorId = 133, hexColor = "#D5733D", user_facing_name = "Neon orange" ),
        bodyColor( brickColorId = 106, hexColor = "#DA8541", user_facing_name = "Bright orange" ),
        bodyColor( brickColorId = 105, hexColor = "#E29B40", user_facing_name = "Br. yellowish orange" ),
        bodyColor( brickColorId = 1017, hexColor = "#FFAF00", user_facing_name = "Deep orange" ),
        bodyColor( brickColorId = 24, hexColor = "#F5CD30", user_facing_name = "Bright yellow" ),
        bodyColor( brickColorId = 334, hexColor = "#F8D96D", user_facing_name = "Daisy orange" ),
        bodyColor( brickColorId = 226, hexColor = "#FDEA8D", user_facing_name = "Cool yellow" ),
        bodyColor( brickColorId = 141, hexColor = "#27462D", user_facing_name = "Earth green" ),
        bodyColor( brickColorId = 1021, hexColor = "#3A7D15", user_facing_name = "Camo" ),
        bodyColor( brickColorId = 28, hexColor = "#287F47", user_facing_name = "Dark green" ),
        bodyColor( brickColorId = 37, hexColor = "#4B974B", user_facing_name = "Bright green" ),
        bodyColor( brickColorId = 310, hexColor = "#5B9A4C", user_facing_name = "Shamrock" ),
        bodyColor( brickColorId = 317, hexColor = "#7C9C6B", user_facing_name = "Moss" ),
        bodyColor( brickColorId = 119, hexColor = "#A4BD47", user_facing_name = "Br. yellowish green" ),
        bodyColor( brickColorId = 1011, hexColor = "#002060", user_facing_name = "Navy blue" ),
        bodyColor( brickColorId = 1012, hexColor = "#2154B9", user_facing_name = "Deep blue" ),
        bodyColor( brickColorId = 1010, hexColor = "#0000FF", user_facing_name = "Really blue" ),
        bodyColor( brickColorId = 23, hexColor = "#0D69AC", user_facing_name = "Bright blue" ),
        bodyColor( brickColorId = 305, hexColor = "#527CAE", user_facing_name = "Steel blue" ),
        bodyColor( brickColorId = 102, hexColor = "#6E99CA", user_facing_name = "Medium blue" ),
        bodyColor( brickColorId = 45, hexColor = "#B4D2E4", user_facing_name = "Light blue" ),
        bodyColor( brickColorId = 107, hexColor = "#008F9C", user_facing_name = "Bright bluish green" ),
        bodyColor( brickColorId = 1018, hexColor = "#12EED4", user_facing_name = "Teal" ),
        bodyColor( brickColorId = 1027, hexColor = "#9FF3E9", user_facing_name = "Pastel blue-green" ),
        bodyColor( brickColorId = 1019, hexColor = "#00FFFF", user_facing_name = "Toothpaste" ),
        bodyColor( brickColorId = 1013, hexColor = "#04AFEC", user_facing_name = "Cyan" ),
        bodyColor( brickColorId = 11, hexColor = "#80BBDC", user_facing_name = "Pastel Blue" ),
        bodyColor( brickColorId = 1024, hexColor = "#AFDDFF", user_facing_name = "Pastel light blue" ),
        bodyColor( brickColorId = 104, hexColor = "#6B327C", user_facing_name = "Bright violet" ),
        bodyColor( brickColorId = 1023, hexColor = "#8C5B9F", user_facing_name = "Lavender" ),
        bodyColor( brickColorId = 321, hexColor = "#A75E9B", user_facing_name = "Lilac" ),
        bodyColor( brickColorId = 1015, hexColor = "#AA00AA", user_facing_name = "Magenta" ),
        bodyColor( brickColorId = 1031, hexColor = "#6225D1", user_facing_name = "Royal purple" ),
        bodyColor( brickColorId = 1006, hexColor = "#B480FF", user_facing_name = "Alder" ),
        bodyColor( brickColorId = 1026, hexColor = "#B1A7FF", user_facing_name = "Pastel violet" ),
        bodyColor( brickColorId = 21, hexColor = "#C4281C", user_facing_name = "Bright red" ),
        bodyColor( brickColorId = 1004, hexColor = "#FF0000", user_facing_name = "Really red" ),
        bodyColor( brickColorId = 1032, hexColor = "#FF00BF", user_facing_name = "Hot pink" ),
        bodyColor( brickColorId = 1016, hexColor = "#FF66CC", user_facing_name = "Pink" ),
        bodyColor( brickColorId = 330, hexColor = "#FF98DC", user_facing_name = "Carnation pink" ),
        bodyColor( brickColorId = 9, hexColor = "#E8BAC8", user_facing_name = "Light reddish violet" ),
        bodyColor( brickColorId = 1025, hexColor = "#FFC9C9", user_facing_name = "Pastel orange" ),
        bodyColor( brickColorId = 364, hexColor = "#5A4C42", user_facing_name = "Dark taupe" ),
        bodyColor( brickColorId = 351, hexColor = "#BC9B5D", user_facing_name = "Cork" ),
        bodyColor( brickColorId = 1008, hexColor = "#C1BE42", user_facing_name = "Olive" ),
        bodyColor( brickColorId = 29, hexColor = "#A1C48C", user_facing_name = "Medium green" ),
        bodyColor( brickColorId = 1022, hexColor = "#7F8E64", user_facing_name = "Grime" ),
        bodyColor( brickColorId = 151, hexColor = "#789082", user_facing_name = "Sand green" ),
        bodyColor( brickColorId = 135, hexColor = "#74869D", user_facing_name = "Sand blue" ),
        bodyColor( brickColorId = 1020, hexColor = "#00FF00", user_facing_name = "Lime green" ),
        bodyColor( brickColorId = 1028, hexColor = "#CCFFCC", user_facing_name = "Pastel green" ),
        bodyColor( brickColorId = 1009, hexColor = "#FFFF00", user_facing_name = "New Yeller" ),
        bodyColor( brickColorId = 1029, hexColor = "#FFFFCC", user_facing_name = "Pastel yellow" ),
        bodyColor( brickColorId = 1003, hexColor = "#111111", user_facing_name = "Really black" ),
        bodyColor( brickColorId = 26, hexColor = "#1B2A35", user_facing_name = "Black" ),
        bodyColor( brickColorId = 199, hexColor = "#635F62", user_facing_name = "Dark stone grey" ),
        bodyColor( brickColorId = 194, hexColor = "#A3A2A5", user_facing_name = "Medium stone grey" ),
        bodyColor( brickColorId = 1002, hexColor = "#CDCDCD", user_facing_name = "Mid gray" ),
        bodyColor( brickColorId = 208, hexColor = "#E5E4DF", user_facing_name = "Light stone grey" ),
        bodyColor( brickColorId = 1, hexColor = "#F2F3F3", user_facing_name = "White" ),
        bodyColor( brickColorId = 1001, hexColor = "#F8F8F8", user_facing_name = "Institutional white" )
    ]
    basicBodyColorsPalette : list[bodyColor] = [
        bodyColor( brickColorId = 364, hexColor = "#5A4C42", user_facing_name = "Dark taupe" ),
        bodyColor( brickColorId = 217, hexColor = "#7C5C46", user_facing_name = "Brown" ),
        bodyColor( brickColorId = 359, hexColor = "#AF9483", user_facing_name = "Linen" ),
        bodyColor( brickColorId = 18, hexColor = "#CC8E69", user_facing_name = "Nougat" ),
        bodyColor( brickColorId = 125, hexColor = "#EAB892", user_facing_name = "Light orange" ),
        bodyColor( brickColorId = 361, hexColor = "#564236", user_facing_name = "Dirt brown" ),
        bodyColor( brickColorId = 192, hexColor = "#694028", user_facing_name = "Reddish brown" ),
        bodyColor( brickColorId = 351, hexColor = "#BC9B5D", user_facing_name = "Cork" ),
        bodyColor( brickColorId = 352, hexColor = "#C7AC78", user_facing_name = "Burlap" ),
        bodyColor( brickColorId = 5, hexColor = "#D7C59A", user_facing_name = "Brick yellow" ),
        bodyColor( brickColorId = 153, hexColor = "#957977", user_facing_name = "Sand red" ),
        bodyColor( brickColorId = 1007, hexColor = "#A34B4B", user_facing_name = "Dusty Rose" ),
        bodyColor( brickColorId = 101, hexColor = "#DA867A", user_facing_name = "Medium red" ),
        bodyColor( brickColorId = 1025, hexColor = "#FFC9C9", user_facing_name = "Pastel orange" ),
        bodyColor( brickColorId = 330, hexColor = "#FF98DC", user_facing_name = "Carnation pink" ),
        bodyColor( brickColorId = 135, hexColor = "#74869D", user_facing_name = "Sand blue" ),
        bodyColor( brickColorId = 305, hexColor = "#527CAE", user_facing_name = "Steel blue" ),
        bodyColor( brickColorId = 11, hexColor = "#80BBDC", user_facing_name = "Pastel Blue" ),
        bodyColor( brickColorId = 1026, hexColor = "#B1A7FF", user_facing_name = "Pastel violet" ),
        bodyColor( brickColorId = 321, hexColor = "#A75E9B", user_facing_name = "Lilac" ),
        bodyColor( brickColorId = 107, hexColor = "#008F9C", user_facing_name = "Bright bluish green" ),
        bodyColor( brickColorId = 310, hexColor = "#5B9A4C", user_facing_name = "Shamrock" ),
        bodyColor( brickColorId = 317, hexColor = "#7C9C6B", user_facing_name = "Moss" ),
        bodyColor( brickColorId = 29, hexColor = "#A1C48C", user_facing_name = "Medium green" ),
        bodyColor( brickColorId = 105, hexColor = "#E29B40", user_facing_name = "Br. yellowish orange" ),
        bodyColor( brickColorId = 24, hexColor = "#F5CD30", user_facing_name = "Bright yellow" ),
        bodyColor( brickColorId = 334, hexColor = "#F8D96D", user_facing_name = "Daisy orange" ),
        bodyColor( brickColorId = 199, hexColor = "#635F62", user_facing_name = "Dark stone grey" ),
        bodyColor( brickColorId = 1002, hexColor = "#CDCDCD", user_facing_name = "Mid gray" ),
        bodyColor( brickColorId = 1001, hexColor = "#F8F8F8", user_facing_name = "Institutional white" )
    ]
    minimumDeltaEBodyColorDifference : float = 11.4
    proportionsAndBodyTypeEnabledForUser : bool = True
    bundlesEnabledForUser : bool = False
    emotesEnabledForUser : bool = True
    max_wearables : int = 10
    
    def __init__( self ):
        pass
    
    def to_dict( self ):
        return {
            "playerAvatarTypes": [ x.name for x in self.playerAvatarTypes ],
            "scales": { k: v.to_dict() for k, v in self.characterScales.items() },
            "wearableAssetTypes": [ x.to_dict() for x in self.wearableAssetTypes ],
            "bodyColorsPalette": [ x.to_dict() for x in self.bodyColorsPalette ],
            "basicBodyColorsPalette": [ x.to_dict() for x in self.basicBodyColorsPalette ],
            "minimumDeltaEBodyColorDifference": self.minimumDeltaEBodyColorDifference,
            "proportionsAndBodyTypeEnabledForUser": self.proportionsAndBodyTypeEnabledForUser,
            "bundlesEnabledForUser": self.bundlesEnabledForUser,
            "emotesEnabledForUser": self.emotesEnabledForUser,
            "maxWearables": self.max_wearables
        }
        
def get_asset_type_rule( asset_type : AssetType, avatar_rules : AvatarRules ) -> wearableAssetType | None:
    for wearable_asset_type in avatar_rules.wearableAssetTypes:
        if wearable_asset_type.asset_type == asset_type:
            return wearable_asset_type
    return None