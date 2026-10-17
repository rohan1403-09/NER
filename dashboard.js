(function () {
    const locationForm = document.getElementById("locationForm");
    const locationInput = document.getElementById("locationInput");
    const locationError = document.getElementById("locationError");
    const map = document.getElementById("map");
    const currentLocationBtn = document.getElementById("currentLocationBtn");

    const MAP_BASE = "https://www.google.com/maps?q=";

    function showError(message) {
        locationError.textContent = message;
        locationError.hidden = false;
    }

    function clearError() {
        locationError.textContent = "";
        locationError.hidden = true;
    }

    locationInput.addEventListener("input", clearError);

    locationForm.addEventListener("submit", function (event) {
        event.preventDefault();
        clearError();

        const location = locationInput.value.trim();

        if (location === "") {
            return;
        }

        map.src = MAP_BASE + encodeURIComponent(location) + "&output=embed";
    });

    currentLocationBtn.addEventListener("click", function () {
        clearError();

        if (!navigator.geolocation) {
            showError("Geolocation is not supported by your browser.");
            return;
        }

        currentLocationBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            function (position) {
                currentLocationBtn.disabled = false;

                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                map.src =
                    MAP_BASE +
                    encodeURIComponent(latitude + "," + longitude) +
                    "&output=embed";
            },
            function (error) {
                currentLocationBtn.disabled = false;

                if (error.code === error.PERMISSION_DENIED) {
                    showError("Location permission was denied. Please allow it in your browser settings.");
                } else if (error.code === error.TIMEOUT) {
                    showError("Finding your location took too long. Please try again.");
                } else {
                    showError("Your location is currently unavailable. Please try again.");
                }
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
        );
    });
})();
