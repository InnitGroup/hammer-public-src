document.addEventListener('DOMContentLoaded', async function() {
    const registerContainer = document.getElementById('register-container');

    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const inviteKeyInput = document.getElementById('invite-key');
    const agreeToTermsCheckbox = document.getElementById('agreeTermsAndPrivacy');
    const agreeMetAgeRequirementCheckbox = document.getElementById('agreeAgeRequirement');
    const registerButton = document.getElementById('register-button');

    const usernameErrorText = document.getElementById('username-input-error-text');
    const passwordErrorText = document.getElementById('password-input-error-text');
    const confirmPasswordErrorText = document.getElementById('confirm-password-input-error-text');
    const inviteKeyErrorText = document.getElementById('invite-key-input-error-text');
    const registerErrorText = document.getElementById('register-error-text');
    
    const loadingContainer = document.getElementById('loading-container');
    var XCSRFToken = this.body.getAttribute('data-csrf-token');

    async function isLetter(str) {
        return str.length === 1 && str.match(/[a-z]/i);
    }
    async function isAlphanumeric(str) {
        return str.length === 1 && str.match(/[a-z0-9]/i);
    }

    async function updateErrorText( errorElement, newText ) {
        if (newText === '') {
            errorElement.style.display = 'none';
        }
        errorElement.innerText = newText;
        errorElement.style.display = 'block';
    }

    async function updateRequirementsErrors() {
        var hasFailedValidation = false;
        if (usernameInput.value === '' ) {
            hasFailedValidation = true;
            updateErrorText( usernameErrorText, 'this field is required' );
        } else if (usernameInput.value.length < 3 || usernameInput.value.length > 20) {
            hasFailedValidation = true;
            updateErrorText( usernameErrorText, 'must be between 3 - 20 characters long' );
        } else if (!usernameInput.value.match(/^[a-z0-9_]+$/i)) {
            hasFailedValidation = true;
            updateErrorText( usernameErrorText, 'only letters, numbers and one underscore' );
        } else if (!await isLetter(usernameInput.value[0])) {
            hasFailedValidation = true;
            updateErrorText( usernameErrorText, 'must start with a letter' );
        } else if (!await isAlphanumeric(usernameInput.value[usernameInput.value.length - 1])) {
            hasFailedValidation = true;
            updateErrorText( usernameErrorText, 'must end with a letter or number' );
        } else {
            updateErrorText( usernameErrorText, '' );
        }
        if (passwordInput.value === '' ) {
            hasFailedValidation = true;
            updateErrorText( passwordErrorText, 'this field is required' );
        } else if (passwordInput.value.length < 8 || passwordInput.value.length > 50) {
            hasFailedValidation = true;
            updateErrorText( passwordErrorText, 'must be between 8 - 128 characters long' );
        } else {
            updateErrorText( passwordErrorText, '' );
        }
        if (passwordInput.value !== confirmPasswordInput.value) {
            hasFailedValidation = true;
            updateErrorText( confirmPasswordErrorText, 'does not match password' );
        } else {
            updateErrorText( confirmPasswordErrorText, '' );
        }

        if (inviteKeyInput.value === '' ) {
            hasFailedValidation = true;
            updateErrorText( inviteKeyErrorText, 'this field is required' );
        } else if ( !inviteKeyInput.value.startsWith('hammer-') || inviteKeyInput.value.length > 90) {
            hasFailedValidation = true;
            updateErrorText( inviteKeyErrorText, 'invalid invite key' );
        } else {
            updateErrorText( inviteKeyErrorText, '' );
        }
        

        if (!agreeToTermsCheckbox.checked) {
            hasFailedValidation = true;
            updateErrorText( registerErrorText, 'must agree to terms and privacy' );
        } else if (!agreeMetAgeRequirementCheckbox.checked) {
            hasFailedValidation = true;
            updateErrorText( registerErrorText, 'must confirm to be 13 years or older' );
        } else {
            updateErrorText( registerErrorText, '' );
        }

        return hasFailedValidation;
    }

    registerButton.addEventListener('click', async function(event) {
        event.preventDefault();
        if (await updateRequirementsErrors()) {
            return;
        }
        
        registerButton.disabled = true;
        registerButton.classList.add('disabled');

        loadingContainer.style.display = 'block';

        var usernameValue = usernameInput.value;
        var passwordValue = passwordInput.value;
        
        var register_req_response = await fetch( await HammerLib.get_endpoint('register'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': XCSRFToken
            },
            body: JSON.stringify({
                username: usernameValue,
                password: passwordValue,
                invite_key: inviteKeyInput.value,
                agree_to_terms : agreeToTermsCheckbox.checked,
                agree_meet_age_requirements: agreeMetAgeRequirementCheckbox.checked
            })
        });
        var register_req_json = await register_req_response.json();
        if (register_req_response.status === 200) {
            window.location.href = register_req_json.data.redirect_url;
        } else if ( register_req_response.status === 429 ) {
            await updateErrorText( registerErrorText, 'ratelimited, please try again later' );
        } else if ( register_req_response.status === 400 ) {
            switch ( register_req_json.status ) {
                case 2:
                    await updateErrorText( registerErrorText, register_req_json.message );
                    break;
                case 5:
                    await updateErrorText( usernameErrorText, "this name is already taken" );
                    break;
                case 7:
                    await updateErrorText( registerErrorText, "this name is not appropriate for hammer" );
                    break;
                case 13:
                    // CSRF token expired or invalid retry with new token
                    XCSRFToken = register_req_response.headers.get("X-CSRFToken")
                    await updateErrorText( registerErrorText, "session expired, please try again" );
            }
        } else if ( register_req_response.status === 500 ) {
            await updateErrorText( registerErrorText, 'internal server error, please try again later' );
        }

        loadingContainer.style.display = 'none';
        registerButton.disabled = false;
        registerButton.classList.remove('disabled');
    })
})