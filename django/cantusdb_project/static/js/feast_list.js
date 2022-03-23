window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const dateFilter = document.getElementById("dateFilter");
    const monthFilter = document.getElementById("monthFilter");
    const sortBy = document.getElementById("sortBy");

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("date")) {
        dateFilter.value = urlParams.get("date");
    }
    if (urlParams.has("month")) {
        monthFilter.value = urlParams.get("month");
    }
    if (urlParams.has("sort_by")) {
        sortBy.value = urlParams.get("sort_by");
    }
});
