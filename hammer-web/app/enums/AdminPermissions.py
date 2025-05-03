from enum import Enum

class AdminPermissions(Enum):
    """
        Do not change the order of these enums, as it will affect the database.
    """
    ManageGameservers = 0 
    ModifyClientSettings = 1
    ManageWebsiteFeatures = 2
    CopyItemsFromRoblox = 3
    ManageItems = 4
    ManageUsers = 5
    ReviewPendingAssets = 6