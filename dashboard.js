  (function () {
    const locationForm = document.getElementById("locationForm");
    const locationInput = document.getElementById("locationInput");
    const locationError = document.getElementById("locationError");
    const map = document.getElementById("map");
    const currentLocationBtn = document.getElementById("currentLocationBtn");
    const rainfallEl = document.querySelector(".rainfall-reading");
    const soilEl = document.querySelector(".soil-moisture-reading");
    const alertList = document.getElementById("alertList");
    const riskBadge = document.getElementById("riskBadge");

    const MAP_BASE = "https://www.google.com/maps?q=";
    let stream = null;

    function showError(message) { locationError.textContent = message; locationError.hidden = false; }
    function clearError() { locationError.textContent = ""; locationError.hidden = true; }
    function showMap(q) { map.src = MAP_BASE + encodeURIComponent(q) + "&output=embed"; }

    // ---- live data ----
    async function loadWeather(lat, lon) {
        try {
            const d = await api("/api/weather/dashboard?lat=" + lat + "&lon=" + lon);
            if (rainfallEl) rainfallEl.textContent = d.rainfallMmPerHr + " mm/hr";
            if (soilEl) soilEl.textContent = d.soilMoisturePct == null ? "n/a" : d.soilMoisturePct + "%";
            if (riskBadge) { riskBadge.textContent = "Landslide risk: " + d.risk.level.toUpperCase(); riskBadge.dataset.level = d.risk.level; }
        } catch (e) { showError(e.message); }
    }

    function addAlert(a, prepend) {
        if (!alertList) return;
        const li = document.createElement("li");
        li.dataset.level = a.level;
        const strong = document.createElement("strong");
        strong.textContent = "[" + String(a.level).toUpperCase() + "] " + a.title;
        const p = document.createElement("span");
        p.textContent = a.body ? " - " + a.body : "";
        li.append(strong, p);                       // textContent only, so alert text can never inject HTML
        if (prepend) alertList.prepend(li); else alertList.append(li);
    }

    async function loadAlerts(lat, lon) {
        try {
            const rows = await api("/api/alerts?lat=" + lat + "&lon=" + lon);
            if (alertList) alertList.textContent = "";
            rows.forEach(function (a) { addAlert(a, false); });
        } catch (e) { /* alerts are optional on first paint */ }
    }

    function openStream() {
        if (stream) return;
        stream = new EventSource(window.API_BASE + "/api/alerts/stream");
        stream.onmessage = function (ev) { try { addAlert(JSON.parse(ev.data), true); } catch (e) {} };
    }

    document.addEventListener("trailsense:loggedin", async function () {
        openStream();
        try {
            const me = await api("/api/auth/me");
            if (me.lat != null) {
                loadWeather(me.lat, me.lon);
                loadAlerts(me.lat, me.lon);
                showMap(me.lat + "," + me.lon);
            } else if (me.location) {
                showMap(me.location);
            }
        } catch (e) { showError(e.message); }
    });

    // ---- search + current location ----
    locationInput.addEventListener("input", clearError);

    locationForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        clearError();
        const location = locationInput.value.trim();
        if (location === "") return;
        showMap(location);
        try {
            const hits = await api("/api/gis/geocode?q=" + encodeURIComponent(location));
            if (hits.length) { loadWeather(hits[0].lat, hits[0].lon); loadAlerts(hits[0].lat, hits[0].lon); }
        } catch (e) { /* map still works without live data */ }
    });

    currentLocationBtn.addEventListener("click", function () {
        clearError();
        if (!navigator.geolocation) { showError("Geolocation is not supported by your browser."); return; }
        currentLocationBtn.disabled = true;
        navigator.geolocation.getCurrentPosition(
            function (position) {
                currentLocationBtn.disabled = false;
                const lat = position.coords.latitude, lon = position.coords.longitude;
                showMap(lat + "," + lon);
                loadWeather(lat, lon);
                loadAlerts(lat, lon);
            },
            function (error) {
                currentLocationBtn.disabled = false;
                if (error.code === error.PERMISSION_DENIED) showError("Location permission was denied. Please allow it in your browser settings.");
                else if (error.code === error.TIMEOUT) showError("Finding your location took too long. Please try again.");
                else showError("Your location is currently unavailable. Please try again.");
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
        );
    });
})();
