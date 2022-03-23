window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const segmentFilter = document.getElementById("segmentFilter");
    const provenanceFilter = document.getElementById("provenanceFilter");
    const centuryFilter = document.getElementById("centuryFilter");
    const fullSourceFilter = document.getElementById("fullSourceFilter");

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("segment")) {
        segmentFilter.value = urlParams.get("segment");
    }
    if (urlParams.has("provenance")) {
        provenanceFilter.value = urlParams.get("provenance");
    }
    if (urlParams.has("century")) {
        centuryFilter.value = urlParams.get("century");
    }
    if (urlParams.has("fullSource")) {
        fullSourceFilter.value = urlParams.get("fullSource");
    }
});
