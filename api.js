// Shared API helper. Must load BEFORE app.js, otp.js, dashboard.js and reports.js.
(function () {
    window.API_BASE = "http://localhost:4000";   // change to your deployed backend URL

    window.getToken = function () {
        try { return sessionStorage.getItem("token"); } catch (e) { return null; }
    };

    // api("/api/auth/login", { method: "POST", json: {...} })   or   { form: FormData }
    window.api = async function (path, opts) {
        opts = opts || {};
        const headers = {};
        const token = window.getToken();
        if (token) headers.Authorization = "Bearer " + token;
        let body;
        if (opts.json) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
        else if (opts.form) { body = opts.form; }          // browser sets the multipart boundary itself

        let res;
        try {
            res = await fetch(window.API_BASE + path, { method: opts.method || "GET", headers: headers, body: body });
        } catch (e) {
            throw new Error("Cannot reach the server. Check your connection.");
        }
        let data = null;
        try { data = await res.json(); } catch (e) { /* empty body */ }
        if (!res.ok) throw new Error((data && data.error) || "Request failed (" + res.status + ")");
        return data;
    };
})();
