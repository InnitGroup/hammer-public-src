import { initContainer } from "hammer_3d_renderer";

document.addEventListener('DOMContentLoaded', async function () {
    const profile_container = document.getElementById('user-profile-container');
    const profile_userid = profile_container.getAttribute('data-profile-userid');
    const loading_container = await HammerLib.get_loading_container();

    const avatar_preview_2d_thumb = document.getElementById('avatar-preview-2d-thumb');
    const avatar_preview_3d_container = document.getElementById('avatar-preview-3d-container');
    const avatar_preview_selector_btn = document.getElementById('avatar-preview-selector-btn');

    const avatar_preview_3d_loading_container = document.getElementById('avatar-preview-3d-loading-container');

    async function update_user_preffered_view(is3D) {
        localStorage.setItem('is_3d_preffered_view_type', is3D);
    }

    var is3DPreview = false;
    async function update_preview() {
        if (is3DPreview) {
            avatar_preview_2d_thumb.style.display = 'block';
            avatar_preview_3d_container.style.display = 'none';
            avatar_preview_selector_btn.innerText = '3D';
            is3DPreview = false;
        } else {
            avatar_preview_2d_thumb.style.display = 'none';
            avatar_preview_3d_container.style.display = 'block';
            avatar_preview_selector_btn.innerText = '2D';
            is3DPreview = true;
            try {
                var load_promise = initContainer(avatar_preview_3d_container);
                if (load_promise !== null) {
                    load_promise.then(() => {
                        avatar_preview_3d_loading_container.style.display = 'none';
                    });
                }
            } catch (error) { }
        }
        await update_user_preffered_view(is3DPreview);
    }

    avatar_preview_selector_btn.addEventListener('click', async function () {
        update_preview();
    });

    if (localStorage.getItem('is_3d_preffered_view_type') === 'true') {
        update_preview();
    }

    if (profile_userid !== HammerLib.authenticated_user_info.userid) {
        const FriendRelationshipBtn = document.getElementById('friend-relationship-action-btn');
        const FollowRelationshipBtn = document.getElementById('follow-relationship-action-btn');

        async function get_friend_relationship_status() {
            try {
                const response = await fetch(`${await HammerLib.get_endpoint('friend_status')}?userId=${profile_userid}`);
                const response_data = await response.json();
                switch (response.status) {
                    case 200:
                        return response_data.status;
                    default:
                        return null;
                }
            } catch (error) {
                return null;
            }
        }

        async function get_follow_relationship_status() {
            try {
                const response = await fetch(`${await HammerLib.get_endpoint('following_status')}?targetUserId=${profile_userid}&followerUserId=${HammerLib.authenticated_user_info.userid}`);
                const response_data = await response.json();
                switch (response.status) {
                    case 200:
                        return response_data.status;
                    default:
                        return null;
                }
            } catch (error) {
                return null;
            }
        }

        /*
            3 = Friends
            4 = Friend Request Sent
            5 = Friend Request Received
            6 = Not Friends
        */
        const _get_friend_status_promise = get_friend_relationship_status();
        const _get_follow_status_promise = get_follow_relationship_status();
        const friend_relationship_status = await _get_friend_status_promise;
        const follow_relationship_status = await _get_follow_status_promise;
        switch (friend_relationship_status) {
            case 3:
                FriendRelationshipBtn.innerText = 'Unfriend';
                FriendRelationshipBtn.setAttribute('variant', 'danger');
                break;
            case 4:
                FriendRelationshipBtn.innerText = 'Cancel Request';
                FriendRelationshipBtn.setAttribute('variant', 'warning');
                break;
            case 5:
                FriendRelationshipBtn.innerText = 'Accept Request';
                FriendRelationshipBtn.setAttribute('variant', 'success');
                break;
            case 6:
                FriendRelationshipBtn.innerText = 'Add Friend';
                break;
            default:
                FriendRelationshipBtn.innerText = 'Error';
                FriendRelationshipBtn.disabled = true;
                FriendRelationshipBtn.setAttribute('variant', 'danger');
                break;
        }

        switch (follow_relationship_status) {
            case 3:
                FollowRelationshipBtn.innerText = 'Unfollow';
                break;
            case 4:
                FollowRelationshipBtn.innerText = 'Follow';
                break;
            default:
                FollowRelationshipBtn.innerText = 'Error';
                FollowRelationshipBtn.disabled = true;
                break;
        }

        async function send_user_relationship_action(web_api_name) {
            loading_container.style.display = 'block';
            try {
                const response = await fetch(`${await HammerLib.get_endpoint(web_api_name)}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await HammerLib.get_csrf_token()
                    },
                    body: JSON.stringify({
                        target_user_id: Number(profile_userid)
                    })
                });
                const response_data = await response.json();
                switch (response.status) {
                    case 200:
                        location.reload();
                        break;
                    default:
                        await HammerLib.show_error_dialog('Failed to perform action', `An error occured while processing this request.${ response_data.message ? ` Error Msg: ${response_data.message}` : ''}`);
                        break;
                }
            } catch (error) {
                await HammerLib.show_error_dialog('Failed to perform action', 'An internal error occured while processing this request, please try again later.');
            }
        }

        FriendRelationshipBtn.addEventListener('click', async function () {
            switch (friend_relationship_status) {
                case 3:
                    const ConfirmationDialog = await HammerLib.show_confirmation_dialog(
                        "Unfriend User",
                        "Are you sure you want to unfriend this user?",
                        "Unfriend",
                        "Cancel",
                        async function () {
                            await send_user_relationship_action('unfriend_user')
                        },
                        null,
                        "bi-person-dash",
                        false
                    )
                    ConfirmationDialog.show();
                    break;
                case 4:
                    await send_user_relationship_action('revoke_friend_request');
                    break;
                case 5:
                case 6:
                    await send_user_relationship_action('friends_request_friendship');
                    break;
                default:
                    break;
            }
        })
        FriendRelationshipBtn.style.display = 'block';

        FollowRelationshipBtn.addEventListener('click', async function () {
            switch (follow_relationship_status) {
                case 3:
                    const ConfirmationDialog = await HammerLib.show_confirmation_dialog(
                        "Unfollow User",
                        "Are you sure you want to unfollow this user?",
                        "Unfollow",
                        "Cancel",
                        async function () {
                            await send_user_relationship_action('unfollow_user')
                        },
                        null,
                        "bi-person-dash",
                        false
                    )
                    ConfirmationDialog.show();
                    break;
                case 4:
                    await send_user_relationship_action('follow_user');
                    break;
                default:
                    break;
            }
        })
        FollowRelationshipBtn.style.display = 'block';
    }
});