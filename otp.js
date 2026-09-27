const otpForm = document.getElementById("otpForm");
const otpInput = document.getElementById("otpInput");
const validOtp = "123456";

otpForm.addEventListener("submit", function (event) {
    event.preventDefault();

    if (otpInput.value.trim() !== validOtp) {
        alert("Invalid OTP. Please try again.");
        otpInput.focus();
        return;
    }

    window.location.href = "DASHBOARD.html";
});
