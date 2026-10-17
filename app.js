(function () {
    const signInSection = document.getElementById("signInSection");
    const signInForm = document.getElementById("signInForm");
    const openLoginButton = document.getElementById("openLoginButton");
    const loginSection = document.getElementById("loginSection");
    const backToSignInButton = document.getElementById("backToSignInButton");
    const loginForm = document.getElementById("loginForm");
    const loginNameInput = document.getElementById("loginNameInput");
    const otpSection = document.getElementById("otpSection");
    const otpInput = document.getElementById("otpInput");

    function goToOtp(fromSection, phone) {
        // Prototype only: remember which number the OTP is for.
        // Replace with a backend "send OTP" request when the API exists.
        try {
            sessionStorage.setItem("pendingPhone", phone);
        } catch (e) {
            // Storage can be blocked (private mode); the flow still works.
        }
        fromSection.hidden = true;
        otpSection.hidden = false;
        otpInput.focus();
    }

    openLoginButton.addEventListener("click", function () {
        signInSection.hidden = true;
        loginSection.hidden = false;
        loginNameInput.focus();
    });

    backToSignInButton.addEventListener("click", function () {
        loginSection.hidden = true;
        signInSection.hidden = false;
    });

    signInForm.addEventListener("submit", function (event) {
        event.preventDefault();
        const data = new FormData(signInForm);
        goToOtp(signInSection, String(data.get("phone") || "").trim());
    });

    loginForm.addEventListener("submit", function (event) {
        event.preventDefault();
        const data = new FormData(loginForm);
        goToOtp(loginSection, String(data.get("phone") || "").trim());
    });
})();
