window.addEventListener("load", function () {
    const copyTextButton = document.getElementById("copyFullTextBelow");
    if (copyTextButton) {
        copyTextButton.addEventListener("click", copyText);
    }
    function copyText() {
        const standardText = document.getElementById('id_manuscript_full_text_std_spelling').value;
        document.getElementById('id_manuscript_full_text').value = standardText;
    }
    // Add an event listener to the segment select field.
    // If the user selects "Benedicamus Domino", show the additional fields
    // in the "benedicamus-domino-segment-fields" div. By default, these
    // are hidden.
    const segmentSelectElem = document.getElementById("id_segment");
    segmentSelectElem.addEventListener("change", function () {
        const benedicamusDominoSegmentFields = document.getElementById("benedicamus-domino-segment-fields");
        const selectedElemText = segmentSelectElem.options[segmentSelectElem.selectedIndex].text;
        benedicamusDominoSegmentFields.hidden = selectedElemText !== "Benedicamus Domino";
    });
})

function autoFillSuggestedChant(genreName, genreID, cantusID, fullText) {
    document.getElementById('id_cantus_id').value = cantusID;
    document.getElementById('id_manuscript_full_text_std_spelling').value = fullText;

    // in case suggestion.genre_id was None, don't try to change the #id_genre selector
    if (genreID === null) {
        return
    }

    // Since we're using a django-autocomplete-light widget for the Genre selector,
    // we need to follow a special process in selecting a value from the widget:
    // Set the value, creating a new option if necessary
    if ($('#id_genre').find("option[value='" + genreID + "']").length) {
        $('#id_genre').val(genreID).trigger('change');
    } else { 
        // Create a DOM Option and pre-select by default
        var newOption = new Option(genreName, genreID, true, true);
        // Append it to the select
        $('#id_genre').append(newOption).trigger('change');
    }
}

function autoFillFeast(feastName, feastID) {
    // Since we're using a django-autocomplete-light widget for the Genre selector,
    // we need to follow a special process in selecting a value from the widget:
    // Set the value, creating a new option if necessary
    if ($('#id_feast').find("option[value='" + feastID + "']").length) {
        $('#id_feast').val(feastID).trigger('change');
    } else { 
        // Create a DOM Option and pre-select by default
        var newOption = new Option(feastName, feastID, true, true);
        // Append it to the select
        $('#id_feast').append(newOption).trigger('change');
    }
}