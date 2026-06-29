window.addEventListener("load", function () {
    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const segmentFilter = document.getElementById("segmentFilter");
    const countryFilter = document.getElementById("countryFilter")
    const provenanceFilter = document.getElementById("provenanceFilter");
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

    const dateStart = document.getElementById("dateStartFilter");
    const dateEnd = document.getElementById("dateEndFilter");
    const rangeFill = document.getElementById("rangeSliderFill");
    const selectedLabel = document.getElementById("rangeSelectedLabel");

    if (dateStart && dateEnd && rangeFill && selectedLabel) {
        const min = parseInt(dateStart.min);
        const max = parseInt(dateStart.max);

        function updateRangeSlider() {
            const startVal = parseInt(dateStart.value);
            const endVal = parseInt(dateEnd.value);
            const startPct = ((startVal - min) / (max - min)) * 100;
            const endPct = ((endVal - min) / (max - min)) * 100;
            rangeFill.style.left = startPct + "%";
            rangeFill.style.width = (endPct - startPct) + "%";
            selectedLabel.textContent = `${startVal} – ${endVal}`;
        }

        const minGap = 25;
        dateStart.addEventListener("input", function () {
            if (parseInt(dateStart.value) > parseInt(dateEnd.value) - minGap) {
                dateStart.value = Math.max(min, parseInt(dateEnd.value) - minGap);
            }
            updateRangeSlider();
        });
        dateEnd.addEventListener("input", function () {
            if (parseInt(dateEnd.value) < parseInt(dateStart.value) + minGap) {
                dateEnd.value = Math.min(max, parseInt(dateStart.value) + minGap);
            }
            updateRangeSlider();
        });

        const resetBtn = document.getElementById("rangeResetBtn");
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                dateStart.value = min;
                dateEnd.value = max;
                updateRangeSlider();
            });
        }

        updateRangeSlider();
    }
});
