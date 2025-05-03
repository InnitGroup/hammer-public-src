from enum import Enum

class GameJoinPrivacy( Enum ):
    NoOne = 0
    FriendsOnly = 1
    FriendsandFollowing = 2
    FriendsFollowingandFollowers = 3
    Everyone = 4