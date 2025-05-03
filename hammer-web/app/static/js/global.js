var HammerLib = {
    'endpoints': {},
    'endpoints_loaded': false,

    'user_balance': {
        'robux': 0,
        'tickets': 0
    },
    'user_balance_loaded': false,

    'is_authenticated': false,
    'authenticated_user_info': {
        'username': null,
        'userid': null
    },
};

HammerLib.get_endpoint = async function (endpoint_name) {
    if (!HammerLib.endpoints_loaded) {
        while (!HammerLib.endpoints_loaded) {
            await new Promise(r => setTimeout(r, 10));
        }
    }
    return HammerLib.endpoints[endpoint_name];
};

HammerLib.show_error_dialog = async function(
    title,
    body_text,
    refresh_on_close = true
) {
    const ErrorDialogContainer = document.getElementById('confirmation-dialog-container-template');
    const NewErrorDialog = ErrorDialogContainer.cloneNode(true);
    NewErrorDialog.setAttribute('label', title);
    const DialogConfirmBtn = NewErrorDialog.getElementsByClassName('confirm-confirmation-button')[0];
    DialogConfirmBtn.remove();
    const DialogCancelBtn = NewErrorDialog.getElementsByClassName('cancel-confirmation-button')[0];
    DialogCancelBtn.innerText = 'Close';

    const DialogBodyText = NewErrorDialog.getElementsByClassName('dialog-body-text')[0];
    DialogBodyText.textContent = body_text;

    DialogCancelBtn.addEventListener('click', async function () {
        NewErrorDialog.hide();
        setTimeout(() => {
            NewErrorDialog.remove();
        }, 1000);
        if (refresh_on_close) {
            window.location.reload();
        }
    })

    NewErrorDialog.addEventListener('sl-request-close', event => {
        event.preventDefault();
    })

    document.body.appendChild(NewErrorDialog);
    NewErrorDialog.style.display = 'block';
    setTimeout(() => {
        NewErrorDialog.show();
    }, 20);

    return NewErrorDialog;
}

HammerLib.show_confirmation_dialog = async function(
    title,
    body_text,
    confirm_text,
    cancel_text,
    confirm_callback,
    cancel_callback,

    confirm_btn_icon = null,
    allow_close_on_background_click = true
) {
    const ConfirmationDialogContainer = document.getElementById('confirmation-dialog-container-template');
    const NewConfirmationDialog = ConfirmationDialogContainer.cloneNode(true);
    NewConfirmationDialog.setAttribute('label', title);

    const ConfirmationDialogCancelBtn = NewConfirmationDialog.getElementsByClassName('cancel-confirmation-button')[0];
    const ConfirmationDialogConfirmBtn = NewConfirmationDialog.getElementsByClassName('confirm-confirmation-button')[0];
    const DialogBodyText = NewConfirmationDialog.getElementsByClassName('dialog-body-text')[0];
    DialogBodyText.textContent = body_text;
    ConfirmationDialogCancelBtn.innerText = cancel_text;
    ConfirmationDialogConfirmBtn.innerText = confirm_text;
    ConfirmationDialogCancelBtn.addEventListener('click', async function () {
        if (cancel_callback !== null) {
            cancel_callback();
        }
        NewConfirmationDialog.hide();
        setTimeout(() => {
            NewConfirmationDialog.remove();
        }, 1000);
    })

    ConfirmationDialogConfirmBtn.addEventListener('click', async function () {
        if (confirm_callback !== null) {
            confirm_callback();
        }
        NewConfirmationDialog.hide();
        setTimeout(() => {
            NewConfirmationDialog.remove();
        }, 1000);
    })


    if (confirm_btn_icon !== null) {
        const ConfirmButttonIcon = document.createElement('i');
        ConfirmButttonIcon.classList.add('bi');
        ConfirmButttonIcon.classList.add(confirm_btn_icon);
        ConfirmButttonIcon.classList.add('ms-2');

        ConfirmationDialogConfirmBtn.appendChild(ConfirmButttonIcon);
    }

    NewConfirmationDialog.addEventListener('sl-request-close', event => {
        if (event.detail.source === 'overlay' && !allow_close_on_background_click) {
            event.preventDefault();
        }
    })

    document.body.appendChild(NewConfirmationDialog);
    NewConfirmationDialog.style.display = 'block';
    return NewConfirmationDialog;
}

HammerLib.get_loading_container = async function() {
    while (document.getElementById('loading-container') === null) {
        await new Promise(r => setTimeout(r, 10));
    }
    return document.getElementById('loading-container');
}

HammerLib.get_csrf_token = async function() {
    return document.body.getAttribute('data-csrf-token');
}

document.addEventListener('DOMContentLoaded', async function () {
    const PageNavbar = document.getElementById('global-navbar');
    const LoadingContainer = await HammerLib.get_loading_container();
    const EndpointLookupURL = this.body.getAttribute('data-endpoint-lookup-url');
    const AuthenticatedUserInfoElement = document.getElementById('authenticated-user-info');
    const isUserAuthenticated = AuthenticatedUserInfoElement !== null;
    var XCSRFToken = await HammerLib.get_csrf_token();

    async function LoadEndpoints() {
        try {
            const response = await fetch(EndpointLookupURL);
            const response_data = await response.json();
            switch (response.status) {
                case 200:
                    HammerLib.endpoints = response_data.endpoints;
                    HammerLib.endpoints_loaded = true;
                    break;
                default:
                    await HammerLib.show_error_dialog('Internal error', 'Failed to load endpoints, please report this issue in our Discord server.');
                    break;
            }
        } catch (error) {
            await HammerLib.show_error_dialog('Internal error', 'Failed to load endpoints, please report this issue in our Discord server.');
        }
    }
    LoadEndpoints();

    async function LoadUserBalance() {
        if (HammerLib.user_balance_loaded) { return; }
        if (!HammerLib.is_authenticated) { return; }

        try {
            const response = await fetch(
                await HammerLib.get_endpoint('economy_get_balance'),
                {
                    credentials: 'include'
                }
            );
            const response_data = await response.json();
            switch (response.status) {
                case 200:
                    HammerLib.user_balance.robux = response_data.data.robux_bal;
                    HammerLib.user_balance.tickets = response_data.data.tickets_bal;
                    HammerLib.user_balance_loaded = true;
                    break;
                case 401:
                    console.error('global.js LoadUserBalance > User is not authenticated, but authenticated user info is present.');
                    break;
                default:
                    console.error(`global.js LoadUserBalance > Failed to load user balance, status code: ${response.status}`);
                    break;
            }
        } catch (error) {
            console.error(`global.js LoadUserBalance > ${error}`)
        }
    }

    if (isUserAuthenticated) {
        const AuthenticatedUserName = AuthenticatedUserInfoElement.getAttribute('data-username');
        const AuthenticatedUserId = AuthenticatedUserInfoElement.getAttribute('data-userid');
        HammerLib.authenticated_user_info.username = AuthenticatedUserName;
        HammerLib.authenticated_user_info.userid = AuthenticatedUserId;
        HammerLib.is_authenticated = true;

        LoadUserBalance();
    }

    if (PageNavbar !== null) {
        const LogoutButton = document.getElementById('logout-button');
        const NavbarDropdown = document.getElementById('navbar-dropdown-menu-settings');
        const NavbarSettingsDropdownContainer = document.getElementById('navbar-settings-dropdown-container');

        async function SendLogoutRequest() {
            const response = await fetch(await HammerLib.get_endpoint('logout'), {
                method: 'POST',
                headers: {
                    'X-CSRFToken': XCSRFToken
                }
            });
            const response_data = await response.json();
            switch (response.status) {
                case 401: // Already logged out
                    window.location.href = '/';
                    break;
                case 200: // Successfully logged out
                    window.location.href = '/';
                    break;
                case 400: // Possible CSRF token expired
                    if (response_data.status === 13) {
                        XCSRFToken = response.headers.get('X-CSRFToken');
                        await SendLogoutRequest();
                    } else {
                        await HammerLib.show_error_dialog('Internal error', 'Failed to logout, please report this issue in our Discord server.');
                    }
                    break;
                default:
                    await HammerLib.show_error_dialog('Internal error', 'Failed to logout, please report this issue in our Discord server.');
                    break;
            }
        }

        LogoutButton.addEventListener('click', async function () {
            var ConfirmationDialog = await HammerLib.show_confirmation_dialog(
                'Confirm Logout',
                'Are you sure you want to logout?',
                'Logout',
                'Cancel',
                async function () {
                    LoadingContainer.style.display = 'block';
                    await SendLogoutRequest();
                },
                null,
                'bi-box-arrow-right',
                false
            );
            ConfirmationDialog.show();
        });

        NavbarDropdown.style.display = 'block';
        NavbarSettingsDropdownContainer.style.display = 'block';
    }
});