window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want. The source filters shared
    // with chant search are restored by source_filters.js.
    const segmentFilter = document.getElementById("segmentFilter");

    const urlParams = new URLSearchParams(window.location.search);
    if (segmentFilter && urlParams.has("segment")) {
        segmentFilter.value = urlParams.get("segment");
    }
});
