window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const opFilter = document.getElementById("opFilter");
    const genreFilter = document.getElementById("genreFilter");
    const melodiesFilter = document.getElementById("melodiesFilter");

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("op")) {
        opFilter.value = urlParams.get("op");
    }
    if (urlParams.has("genre")) {
        genreFilter.value = urlParams.get("genre");
    }
    if (urlParams.has("melodies")) {
        melodiesFilter.value = urlParams.get("melodies");
    }
});
