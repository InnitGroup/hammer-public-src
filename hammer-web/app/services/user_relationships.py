import redis_lock
from app.extensions import db, sync_redis_controller

from app.models.friend_request import FriendRequest
from app.models.friend_relationship import FriendRelationship
from app.models.follow_relationship import FollowRelationship
from app.models.user import User

from sqlalchemy import or_

class UserRelationshipServiceException( Exception ):
    pass
class Exceptions():
    class UserAlreadyFriends( UserRelationshipServiceException ):
        pass
    class UserAlreadySentFriendRequest( UserRelationshipServiceException ):
        pass
    class UserAlreadyFollowing( UserRelationshipServiceException ):
        pass
    class UserNotFriends( UserRelationshipServiceException ):
        pass
    class UserNotFollowing( UserRelationshipServiceException ):
        pass
    class ExceededFriendLimit( UserRelationshipServiceException ):
        pass
    
def get_friend_relationship( user1_id : int, user2_id : int ) -> FriendRelationship | None :
    if user1_id < user2_id:
        first_user_id = user1_id
        second_user_id = user2_id
    else:
        first_user_id = user2_id
        second_user_id = user1_id
        
    return FriendRelationship.query.filter_by( first_user_id = first_user_id, second_user_id = second_user_id ).first()

def get_friend_request( sender_id : int, receiver_id : int ) -> FriendRequest | None:
    return FriendRequest.query.filter_by( sender_id = sender_id, receiver_id = receiver_id ).first()

async def create_friend_relationship( user1_id : int, user2_id : int ) -> FriendRelationship:
    if user1_id < user2_id:
        first_user_id = user1_id
        second_user_id = user2_id
    else:
        first_user_id = user2_id
        second_user_id = user1_id
        
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"create_friend_relationship:{first_user_id}:{second_user_id}", expire = 10, auto_renewal = True ):
        if get_friend_relationship( user1_id, user2_id ) is not None:
            raise Exceptions.UserAlreadyFriends()
        if await get_user_friend_count( user1_id ) >= 200 or await get_user_friend_count( user2_id ) >= 200:
            raise Exceptions.ExceededFriendLimit()
        
        user1_requests_user2 : FriendRequest | None = get_friend_request( user1_id, user2_id )
        user2_requests_user1 : FriendRequest | None = get_friend_request( user2_id, user1_id )
        if user1_requests_user2 is not None:
            db.session.delete( user1_requests_user2 )
        if user2_requests_user1 is not None:
            db.session.delete( user2_requests_user1 )
        
        friend_relationship = FriendRelationship( first_user_id = user1_id, second_user_id = user2_id )
        db.session.add( friend_relationship )
        db.session.commit()
        
        return friend_relationship

async def send_friend_request( sender_id : int, receiver_id : int ) -> FriendRequest | FriendRelationship:
    """
        Send a friend request from sender to receiver
        
        However, if the receiver has a pending friend request with the sender
        the relationship will be automatically created and will return a FriendRelationship object
    """
    
    if sender_id == receiver_id:
        raise ValueError("Sender and receiver IDs cannot be the same")
    
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"send_friend_request:{sender_id}:{receiver_id}", expire = 10, auto_renewal = True ):
        if get_friend_relationship( sender_id, receiver_id ) is not None:
            raise Exceptions.UserAlreadyFriends()
        
        if get_friend_request( sender_id, receiver_id ) is not None:
            raise Exceptions.UserAlreadySentFriendRequest()
        
        if get_friend_request( receiver_id, sender_id ) is not None:
            return await create_friend_relationship( sender_id, receiver_id )
        
        friend_request = FriendRequest( sender_id = sender_id, receiver_id = receiver_id )
        db.session.add( friend_request )
        db.session.commit()
        
        return friend_request

async def get_user_friend_count( user_obj : User | int ) -> int:
    user_id = user_obj.id if isinstance( user_obj, User ) else user_obj
    return FriendRelationship.query.filter( or_( FriendRelationship.first_user_id == user_id, FriendRelationship.second_user_id == user_id ) ).count()

async def get_user_friends( user_obj : User, order_by_last_online : bool = False, limit : int = 12 ) -> list[User]:
    if not order_by_last_online:
        friends_obj_list : list[FriendRelationship] = FriendRelationship.query.filter( or_( FriendRelationship.first_user_id == user_obj.id, FriendRelationship.second_user_id == user_obj.id ) ).limit( limit ).all()
    else:
        friends_obj_list : list[FriendRelationship] = FriendRelationship.query.filter( or_( FriendRelationship.first_user_id == user_obj.id, FriendRelationship.second_user_id == user_obj.id ) ).join( User, or_( User.id == FriendRelationship.first_user_id, User.id == FriendRelationship.second_user_id ) ).order_by( User.lastonline_at.desc() ).limit( limit ).all()

    friends_list : list[User] = []
    for friend_obj in friends_obj_list:
        if friend_obj.first_user_id == user_obj.id:
            friends_list.append( User.query.filter_by( id = friend_obj.second_user_id ).first() )
        else:
            friends_list.append( User.query.filter_by( id = friend_obj.first_user_id ).first() )
            
    return friends_list

def get_follow_relationship( follower_id : int, following_id : int ) -> FollowRelationship | None:
    return FollowRelationship.query.filter_by( follower_id = follower_id, following_id = following_id ).first()

async def create_follow_relationship( follower_id : int, following_id : int ) -> FollowRelationship:
    if follower_id == following_id:
        raise ValueError("Follower and following IDs cannot be the same")
    with redis_lock.Lock( redis_client = sync_redis_controller, name = f"create_follow_relationship:{follower_id}:{following_id}", expire = 10, auto_renewal = True ):
        if get_follow_relationship( follower_id, following_id ) is not None:
            raise Exceptions.UserAlreadyFollowing()
        
        follow_relationship = FollowRelationship( follower_id = follower_id, following_id = following_id )
        db.session.add( follow_relationship )
        db.session.commit()
        
        return follow_relationship