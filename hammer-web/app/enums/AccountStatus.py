from enum import Enum

class AccountStatus(Enum):
    Active = 0
    Suspended = 1
    Deleted = 2
    GDPR_Deleted = 3