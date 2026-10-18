// Photo / video report upload
(function () {
    const form = document.getElementById("reportForm");
    if (!form) return;
    const status = document.getElementById("reportStatus");
    const MAX_FILES = 5;

    function say(msg, isError) { status.textContent = msg; status.className = isError ? "form-error" : ""; status.hidden = false; }

    function getPosition() {
        return new Promise(function (resolve) {
            if (!navigator.geolocation) return resolve(null);
            navigator.geolocation.getCurrentPosition(
                function (p) { resolve(p.coords); }, function () { resolve(null); }, { timeout: 8000 });
        });
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const files = form.querySelector("input[type=file]").files;
        if (files.length > MAX_FILES) return say("Choose at most " + MAX_FILES + " files.", true);

        const fd = new FormData();
        fd.append("category", form.elements.category.value);
        fd.append("description", form.elements.description.value);
        Array.prototype.forEach.call(files, function (f) { fd.append("media", f); });
        if (form.elements.attachLocation.checked) {
            const c = await getPosition();
            if (c) { fd.append("lat", c.latitude); fd.append("lon", c.longitude); }
        }

        const button = form.querySelector("button[type=submit]");
        button.disabled = true;
        say("Uploading...", false);
        try {
            const r = await api("/api/reports", { method: "POST", form: fd });
            say(r.message, false);
            form.reset();
        } catch (e) {
            say(e.message, true);
        } finally {
            button.disabled = false;
        }
    });
})();
