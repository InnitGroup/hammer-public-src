from enum import Enum

class MessagePrivacy( Enum ):
    NoOne = 0
    FriendsOnly = 1
    FriendsandFollowing = 2
    FriendsFollowingandFollowers = 3
    Everyone = 4