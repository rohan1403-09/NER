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

    function formError(form, message) {
        let p = form.querySelector(".form-error");
        if (!p) {
            p = document.createElement("p");
            p.className = "form-error";
            p.setAttribute("role", "alert");
            form.appendChild(p);
        }
        p.textContent = message;
        p.hidden = !message;
    }

    function goToOtp(fromSection, phone, name) {
        try {
            sessionStorage.setItem("pendingPhone", phone);
            sessionStorage.setItem("pendingName", name || "");
        } catch (e) { /* storage blocked; the flow still works for this page load */ }
        fromSection.hidden = true;
        otpSection.hidden = false;
        otpInput.focus();
    }

    async function submit(form, section, path, payload, name) {
        const button = form.querySelector("button[type=submit]");
        formError(form, "");
        button.disabled = true;
        try {
            const data = await api(path, { method: "POST", json: payload });
            if (data.devOtp) console.info("DEV OTP (console SMS provider):", data.devOtp);
            goToOtp(section, payload.phone, name);
        } catch (e) {
            formError(form, e.message);
        } finally {
            button.disabled = false;
        }
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
        const d = new FormData(signInForm);
        submit(signInForm, signInSection, "/api/auth/register", {
            email: String(d.get("email") || "").trim(),
            password: String(d.get("password") || ""),
            phone: String(d.get("phone") || "").trim(),
            location: String(d.get("location") || "").trim()
        }, "");
    });

    loginForm.addEventListener("submit", function (event) {
        event.preventDefault();
        const d = new FormData(loginForm);
        const name = String(d.get("name") || "").trim();
        submit(loginForm, loginSection, "/api/auth/login", { phone: String(d.get("phone") || "").trim(), name: name }, name);
    });
})();
