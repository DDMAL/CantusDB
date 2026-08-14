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
    const startInput = document.getElementById("rangeStartInput");
    const endInput = document.getElementById("rangeEndInput");

    if (dateStart && dateEnd && rangeFill && startInput && endInput) {
        const min = parseInt(dateStart.min);
        const max = parseInt(dateStart.max);
        const minGap = 25;

        function updateFill(startVal, endVal) {
            const startPct = ((startVal - min) / (max - min)) * 100;
            const endPct = ((endVal - min) / (max - min)) * 100;
            rangeFill.style.left = startPct + "%";
            rangeFill.style.width = (endPct - startPct) + "%";
        }

        // Slider dragging: snaps to step=5, updates text inputs to match
        dateStart.addEventListener("input", function () {
            if (parseInt(dateStart.value) > parseInt(dateEnd.value) - minGap) {
                dateStart.value = Math.max(min, parseInt(dateEnd.value) - minGap);
            }
            const startVal = parseInt(dateStart.value);
            startInput.value = startVal;
            updateFill(startVal, parseInt(dateEnd.value));
        });
        dateEnd.addEventListener("input", function () {
            if (parseInt(dateEnd.value) < parseInt(dateStart.value) + minGap) {
                dateEnd.value = Math.min(max, parseInt(dateStart.value) + minGap);
            }
            const endVal = parseInt(dateEnd.value);
            endInput.value = endVal;
            updateFill(parseInt(dateStart.value), endVal);
        });

        // Typing: clamp to valid range, move slider visually, keep exact typed value
        startInput.addEventListener("change", function () {
            const typed = parseInt(startInput.value);
            if (isNaN(typed)) { startInput.value = parseInt(dateStart.value); return; }
            const clamped = Math.min(Math.max(typed, min), parseInt(endInput.value) - minGap);
            startInput.value = clamped;
            dateStart.value = clamped; // slider snaps to nearest 5 visually only
            updateFill(clamped, parseInt(endInput.value));
        });
        endInput.addEventListener("change", function () {
            const typed = parseInt(endInput.value);
            if (isNaN(typed)) { endInput.value = parseInt(dateEnd.value); return; }
            const clamped = Math.max(Math.min(typed, max), parseInt(startInput.value) + minGap);
            endInput.value = clamped;
            dateEnd.value = clamped;
            updateFill(parseInt(startInput.value), clamped);
        });

        const resetBtn = document.getElementById("rangeResetBtn");
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                dateStart.value = min;
                dateEnd.value = max;
                startInput.value = min;
                endInput.value = max;
                updateFill(min, max);
            });
        }

        updateFill(parseInt(dateStart.value), parseInt(dateEnd.value));
    }
});
