
(function () {
    const otpForm = document.getElementById("otpForm");
    const otpInput = document.getElementById("otpInput");
    const validOtp = "123456";
    const otpSection = document.getElementById("otpSection");
    const dashboardSection = document.getElementById("dashboardSection");

    otpForm.addEventListener("submit", function (event) {
        event.preventDefault();

        if (otpInput.value.trim() !== validOtp) {
            alert("Invalid OTP. Please try again.");
            otpInput.focus();
            return;
        }

        otpSection.hidden = true;
        dashboardSection.hidden = false;
    });
})();
