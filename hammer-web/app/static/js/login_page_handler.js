document.addEventListener('DOMContentLoaded', async function() {
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const rememberMeCheckbox = document.getElementById('remember-session');
    const loginErrorText = document.getElementById('login-error-text');

    const loadingContainer = document.getElementById('loading-container');
    var XCSRFToken = this.body.getAttribute('data-csrf-token');
    const twoFactorRequestContainer = document.getElementById('two-factor-request-container');
    const twoFactorInput = document.getElementById('two-factor-code');
    const twoFactorSubmitButton = document.getElementById('two-factor-button');
    const twoFactorErrorText = document.getElementById('two-factor-error-text');

    var isProcessingLogin = false;
    var isWaitingForTwoFactor = false;
    var twoFactorAttempts = 0;
    var currentTwoFactorToken = '';

    async function isRequirementsMet() {
        if (usernameInput.value === '' || passwordInput.value === '' || isProcessingLogin ) {
            return false;
        }
        return true;
    }

    async function updateButtonState() {
        if ( await isRequirementsMet() ) { 
            loginButton.disabled = false;
            loginButton.classList.remove('disabled');
        } else { 
            loginButton.disabled = true; 
            loginButton.classList.add('disabled');
        }
    }

    twoFactorInput.addEventListener('input', async function(event) {
        if ( !isWaitingForTwoFactor ) {
            return;
        }
        if (twoFactorInput.value.length === 6) {
            twoFactorSubmitButton.disabled = false;
            twoFactorSubmitButton.classList.remove('disabled');
        } else {
            twoFactorSubmitButton.disabled = true;
            twoFactorSubmitButton.classList.add('disabled');
        }
    })

    async function handleTwoFactorRequest() {
        isWaitingForTwoFactor = true;
        twoFactorRequestContainer.style.display = 'block';
        loadingContainer.style.display = 'none';

        async function handle2FASubmit() {
            if (twoFactorInput.value.length !== 6) {
                return;
            }
            twoFactorSubmitButton.disabled = true;
            twoFactorSubmitButton.classList.add('disabled');

            isWaitingForTwoFactor = false;
            twoFactorSubmitButton.removeEventListener('click', handle2FASubmit);
        }
        twoFactorSubmitButton.addEventListener('click', handle2FASubmit);

        while (isWaitingForTwoFactor) {
            await new Promise(r => setTimeout(r, 50));
        }

        twoFactorRequestContainer.style.display = 'none';
        loadingContainer.style.display = 'block';

        var rememberMeValue = rememberMeCheckbox.checked;
        var loginData = { next_step_token: currentTwoFactorToken, remember_me: rememberMeValue, two_factor_code: twoFactorInput.value };

        twoFactorAttempts += 1;
        await sendLoginTwoFactorRequest(loginData);
    }

    async function updateErrorText( message ) {
        if ( message === '' ) {
            loginErrorText.style.display = 'none';
        }
        loginErrorText.textContent = message;
        loginErrorText.style.display = 'block';
    }

    async function sendLoginTwoFactorRequest( loginData ) {
        var fetch_response = await fetch( await HammerLib.get_endpoint('login_two_factor'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': XCSRFToken
            },
            body: JSON.stringify(loginData),
        })
        var responseData = await fetch_response.json();
        switch (responseData.status) {
            case 1:
                window.location.href = responseData.data.redirect_url;
                break;
            case 3:
                await updateErrorText("Internal server error, please try again later.");
                break;
            case 4:
                if ( twoFactorAttempts >= 3 ) {
                    await updateErrorText("Too many failed attempts, please try again later.");
                    break;
                }
                twoFactorErrorText.textContent = 'Invalid code, please try again.';
                twoFactorErrorText.style.display = 'block';
                await handleTwoFactorRequest();
                break;
            case 6:
                window.location.href = responseData.data.redirect_url;
                break;
            case 11:
                await updateErrorText("Too many login attempts, please try again later.");
                break;
            case 13:
                XCSRFToken = fetch_response.headers.get("X-CSRFToken");
                await sendLoginTwoFactorRequest( loginData );
                break;
            default:
                await updateErrorText("Unexpected error, please report this issue in our Discord server.");
                break;
        }
    }

    async function sendLoginRequest( loginData ) {
        var fetch_response = await fetch( await HammerLib.get_endpoint('login'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': XCSRFToken
            },
            body: JSON.stringify(loginData),
        });

        var responseData = await fetch_response.json();
        switch (responseData.status) {
            case 1:
                window.location.href = responseData.data.redirect_url;
                break;
            case 2:
                await updateErrorText("Failed to login, please report this issue in our Discord server.")
                break;
            case 3:
                await updateErrorText("Logins are temporarily disabled, please try again later.");
                break;
            case 4:
                await updateErrorText("Invalid username or password.");
                break;
            case 5: // Two-factor authentication required
                currentTwoFactorToken = responseData.next_step_token;
                await handleTwoFactorRequest();
                break;
            case 6: // User is suspended
                window.location.href = responseData.data.redirect_url;
                break;
            case 7: // Two-factor invalid code
                if ( twoFactorAttempts >= 3 ) {
                    await updateErrorText("Too many attempts, please try again later.");
                    break;
                }
                twoFactorErrorText.textContent = 'Invalid code, please try again.';
                twoFactorErrorText.style.display = 'block';
                await handleTwoFactorRequest();
                break;
            case 11: // Rate limited
                await updateErrorText("Too many login attempts, please try again later.");
                break;
            case 13: // CSRF token expired or invalid retry with new token
                XCSRFToken = fetch_response.headers.get("X-CSRFToken")
                await sendLoginRequest( loginData );
                break;
            default:
                await updateErrorText("Login failed unexpected status code, please report this issue in our Discord server.");
                break;
        }
    }

    usernameInput.addEventListener('input', async function(event) {
        await updateButtonState();
    });
    passwordInput.addEventListener('input', async function(event) {
        await updateButtonState();
    });

    loginButton.addEventListener('click', async function() {
        var requirementsMet = await isRequirementsMet();
        if (!requirementsMet) {
            await updateButtonState();
            return;
        }
        await updateErrorText("");
        loadingContainer.style.display = 'block';

        isProcessingLogin = true;
        twoFactorAttempts = 0;
        await updateButtonState();
        twoFactorErrorText.style.display = 'none';

        var usernameValue = usernameInput.value;
        var passwordValue = passwordInput.value;
        var rememberMeValue = rememberMeCheckbox.checked;

        var loginData = { username: usernameValue, password: passwordValue, remember_me: rememberMeValue };

        await sendLoginRequest(loginData);

        loadingContainer.style.display = 'none';
        isProcessingLogin = false;
        await updateButtonState();
    });

    await updateButtonState();
})