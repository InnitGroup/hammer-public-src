from enum import Enum

class WebsiteFeature( Enum ):
    """
        NEVER CHANGE THE ORDER OF THESE ENUMS IT WILL FUCK UP EVERYTHING UP
    """
    IsLoginEnabled = 0
    IsRegistrationEnabled = 1
    EconomyPurchases = 2
    ThumbnailRenders = 3
    InviteKeyCreation = 4