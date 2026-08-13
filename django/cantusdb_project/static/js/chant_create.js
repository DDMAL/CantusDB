window.addEventListener("load", function () {
    const copyTextButton = document.getElementById("copyFullTextBelow");
    if (copyTextButton) {
        copyTextButton.addEventListener("click", copyText);
    }
    function copyText() {
        const standardText = document.getElementById('id_manuscript_full_text_std_spelling').value;
        document.getElementById('id_manuscript_full_text').value = standardText;
    }
    // Add an event listener to the segment project field.
    // If the user selects "Benedicamus Domino", show the additional fields
    // in the "benedicamus-domino-project-fields" div. By default, these
    // are hidden.
    const projectSelectElem = document.getElementById("id_project");
    projectSelectElem.addEventListener("change", function () {
        const benedicamusDominoProjectFields = document.getElementById("benedicamus-domino-project-fields");
        const selectedElemText = projectSelectElem.options[projectSelectElem.selectedIndex].text;
        if (selectedElemText === "Benedicamus Domino") {
            benedicamusDominoProjectFields.hidden = false;
        } else {
            benedicamusDominoProjectFields.hidden = true;
        }
    });
})

function autoFillSuggestedChant(genreName, genreID, cantusID, fullText) {
    const cantusIdField = document.getElementById('id_cantus_id');
    cantusIdField.value = cantusID;
    document.getElementById('id_manuscript_full_text_std_spelling').value = fullText;
    // The cluster composer (chant_create_clusters.js) listens for a native "change" on this
    // field to reload its element bank, reseed the base text, and warn before discarding any
    // composed elements. A plain .value assignment fires no such event, so without this the
    // composer would silently keep the previous chant's elements under the new Cantus ID.
    cantusIdField.dispatchEvent(new Event('change', { bubbles: true }));

    // in case suggestion.genre_id was None, don't try to change the #id_genre selector
    if (genreID === null) {
        return
    }

    // Since we're using a django-autocomplete-light widget for the Genre selector,
    // we need to follow a special process in selecting a value from the widget:
    // Set the value, creating a new option if necessary
    const genreSelect = document.getElementById('id_genre');
    let option = genreSelect.querySelector(`option[value='${genreID}']`);

    if (option) {
        genreSelect.value = genreID;
    } else {
        const newOption = new Option(genreName, genreID, true, true);
        genreSelect.appendChild(newOption);
        genreSelect.value = genreID;
    }

    // Trigger change event
    const event = new Event('change', { bubbles: true });
    genreSelect.dispatchEvent(event);
}

function autoFillFeast(feastName, feastID) {
    // Since we're using a django-autocomplete-light widget for the Genre selector,
    // we need to follow a special process in selecting a value from the widget:
    // Set the value, creating a new option if necessary
    const feastSelect = document.getElementById('id_feast');
    let option = feastSelect.querySelector(`option[value='${feastID}']`);

    if (option) {
        feastSelect.value = feastID;
    } else {
        const newOption = new Option(feastName, feastID, true, true);
        feastSelect.appendChild(newOption);
        feastSelect.value = feastID;
    }

    // Trigger change event
    const event = new Event('change', { bubbles: true });
    feastSelect.dispatchEvent(event);
}