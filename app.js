const signInSection = document.getElementById("signInSection");
const signInForm = document.getElementById("signInForm");
const openLoginButton = document.getElementById("openLoginButton");
const loginSection = document.getElementById("loginSection");
const backToSignInButton = document.getElementById("backToSignInButton");
const loginForm = document.getElementById("loginForm");
const loginNameInput = document.getElementById("loginNameInput");
const otpSection = document.getElementById("otpSection");
const otpInput = document.getElementById("otpInput");
const otpInstructions = document.querySelector(".otp-instructions");

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
    signInSection.hidden = true;
    otpSection.hidden = false;
    otpInput.focus();
});

loginForm.addEventListener("submit", function (event) {
    event.preventDefault();
    loginSection.hidden = true;
    otpSection.hidden = false;
    otpInput.focus();
});
