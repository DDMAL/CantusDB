window.addEventListener("load", function () {
    const feastSelect = document.getElementById("feastSelect");
    const folioSelect = document.getElementById("folioSelect");
    const copyTextButton = document.getElementById("copyFullTextBelow");
    if (copyTextButton) {
        copyTextButton.addEventListener("click", copyText);
    }

    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("feast")) {
        feastSelect.value = urlParams.get("feast");
    }
    if (urlParams.has("folio")) {
        folioSelect.value = urlParams.get("folio");
    }

    feastSelect.addEventListener("change", setFeastRight);
    folioSelect.addEventListener("change", setFolio);

    // functions for the auto-jump of various selectors and input fields on the page
    // the folio selector and folio-feast selector on the right half do source-wide Selecting
    // the feast selector, genre selector, and text search on the left half do folio-wide Selecting
    var url = new URL(window.location.href);

    function copyText() {
        const standardText = document.getElementById('id_manuscript_full_text_std_spelling').value;
        const fullTextField = document.getElementById('id_manuscript_full_text');
        if (!fullTextField.disabled) { // locked once proofread
            fullTextField.value = standardText;
        }
    }

    // A ticked proofread box locks the fields it covers. The server enforces
    // the lock; this mirrors it as a proofreader ticks and unticks the boxes.
    const proofreadLocksData = document.getElementById("proofread-locks");
    const proofreadLocks = proofreadLocksData ? JSON.parse(proofreadLocksData.textContent) : {};
    for (const [checkboxId, fieldIds] of Object.entries(proofreadLocks || {})) {
        const checkbox = document.getElementById(checkboxId);
        if (!checkbox || checkbox.disabled) {
            continue; // not a proofreader: the locks can't change
        }
        const fields = fieldIds
            .map((fieldId) => document.getElementById(fieldId))
            .filter(Boolean);
        const submittedCopies = new Map();
        function unlock(field) {
            submittedCopies.get(field)?.remove();
            submittedCopies.delete(field);
            field.disabled = false;
        }
        // Lock a field the proofreader is approving, so nothing more can be
        // typed into it. The browser doesn't submit a disabled input, so its
        // value is submitted from a hidden copy: the server saves the value the
        // proofreader approved, not whatever is stored by then (#170).
        function lockApproved(field) {
            unlock(field);
            field.disabled = true;
            const copy = document.createElement("input");
            copy.type = "hidden";
            copy.name = field.name;
            copy.value = field.value;
            field.after(copy);
            submittedCopies.set(field, copy);
        }
        if (checkbox.checked) {
            // A page shown again after a failed save leaves the fields the
            // proofreader submitted unlocked, even under a ticked box.
            fields.filter((field) => !field.disabled).forEach(lockApproved);
        }
        checkbox.addEventListener("change", function () {
            fields.forEach(checkbox.checked ? lockApproved : unlock);
        });
    }

    // if the feast on the right is reset, reset every selector but keep the source unchanged
    function setFeastRight() {
        url.searchParams.set('folio', '');
        url.searchParams.set('pk', '');
        const feast = feastSelect.options[feastSelect.selectedIndex].value;
        url.searchParams.set('feast', feast);
        window.location.assign(url);
    }

    // if the folio is reset, reset every selector but keep the source unchanged
    function setFolio() {
        url.searchParams.set('feast', '');
        url.searchParams.set('pk', '');
        const folio = folioSelect.options[folioSelect.selectedIndex].value;
        url.searchParams.set('folio', folio);
        window.location.assign(url);
    }

    // Add an event listener to the project select field.
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
    projectSelectElem.dispatchEvent(new Event('change')); // ensures that the event listener is called on page load
})

function autoFillSuggestedFullText(fullText) {
    var fullTextField = document.getElementById('id_manuscript_full_text_std_spelling');
    if (fullTextField.value === "") {
        fullTextField.value = fullText;
    }
}