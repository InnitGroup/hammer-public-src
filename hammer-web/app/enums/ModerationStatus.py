from enum import Enum

class ModerationStatus( Enum ):
    Approved = 0
    AwaitingApproval = 1
    Denied = 2