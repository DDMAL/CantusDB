function containsOnlyLettersAndSpaces(str) {
    return /^[A-Za-z\s]*$/.test(str);
  }

window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const opFilter = document.getElementById("opFilter");
    const genreFilter = document.getElementById("genreFilter");
    const melodiesFilter = document.getElementById("melodiesFilter");
    const keywordField = document.getElementById("keywordSearch");
    const cantusIDField = document.getElementById("cantus_id");

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
    if (urlParams.has("search_bar")) {
        search_term = urlParams.get("search_bar");
        if (containsOnlyLettersAndSpaces(search_term)) {
            // assume user is doing an incipit search
            opFilter.value = "starts_with"
            keywordField.value = search_term
        } else {
            // if search term contains other characters, assume user
            // is doing a Cantus ID search
            cantusIDField.value = search_term
        }
    }
});
