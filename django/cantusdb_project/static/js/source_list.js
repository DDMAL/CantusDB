window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const segmentFilter = document.getElementById("segmentFilter");
    const countryFilter = document.getElementById("countryFilter")
    const provenanceFilter = document.getElementById("provenanceFilter");
    const centuryFilter = document.getElementById("centuryFilter");
    const prodMethodFilter = document.getElementById("prodMethodFilter");

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("segment")) {
        segmentFilter.value = urlParams.get("segment");
    }
    if (urlParams.has("country")) {
        countryFilter.value = urlParams.get("country");
    }
    if (urlParams.has("provenance")) {
        provenanceFilter.value = urlParams.get("provenance");
    }
    if (urlParams.has("century")) {
        centuryFilter.value = urlParams.get("century");
    }
    if (urlParams.has("sourceCompleteness")) {
        const sourceCompletenessValues = urlParams.getAll("sourceCompleteness");
        // We start out with all checkboxes checked, so we uncheck the ones not
        // in the URL
        for (let i = 1; i <= 4; i++) {
            if (!sourceCompletenessValues.includes(i.toString())) {
                document.getElementById(`sourceCompleteness-${i}`).checked = false;
            }
        }
    }
    if (urlParams.has("prodMethod")) {
        prodMethodFilter.value = urlParams.get("prodMethod");
    }
});
