const locationForm = document.getElementById("locationForm");
const locationInput = document.getElementById("locationInput");
const map = document.getElementById("map");
const currentLocationBtn = document.getElementById("currentLocationBtn");

locationForm.addEventListener("submit", function (event) {
    event.preventDefault();

    const location = locationInput.value.trim();

    if (location === "") {
        return;
    }

    map.src =
        "https://www.google.com/maps?q=" +
        encodeURIComponent(location) +
        "&output=embed";
});

currentLocationBtn.addEventListener("click", function () {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        function (position) {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            map.src =
                "https://www.google.com/maps?q=" +
                latitude + "," + longitude +
                "&output=embed";
        },
        function () {
            alert(
                "Unable to access your location. Please allow location permission."
            );
        }
    );
});
