  (function () {
    const otpForm = document.getElementById("otpForm");
    const otpInput = document.getElementById("otpInput");
    const otpError = document.getElementById("otpError");
    const otpSection = document.getElementById("otpSection");
    const dashboardSection = document.getElementById("dashboardSection");

    function showError(message) { otpError.textContent = message; otpError.hidden = false; }
    function clearError() { otpError.textContent = ""; otpError.hidden = true; }

    otpInput.addEventListener("input", clearError);

    otpForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const button = otpForm.querySelector("button[type=submit]");
        let phone = "", name = "";
        try { phone = sessionStorage.getItem("pendingPhone") || ""; name = sessionStorage.getItem("pendingName") || ""; } catch (e) {}

        button.disabled = true;
        try {
            const data = await api("/api/auth/otp/verify", {
                method: "POST",
                json: { phone: phone, otp: otpInput.value.trim(), name: name }
            });
            sessionStorage.setItem("token", data.token);
            sessionStorage.removeItem("pendingPhone");
            clearError();
            otpSection.hidden = true;
            dashboardSection.hidden = false;
            document.dispatchEvent(new CustomEvent("trailsense:loggedin"));
        } catch (e) {
            showError(e.message);
            otpInput.value = "";
            otpInput.focus();
        } finally {
            button.disabled = false;
        }
    });
})();
