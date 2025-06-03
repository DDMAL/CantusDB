window.addEventListener("load", function () {
    const searchText = document.getElementById("search");
    const sourceFilter = document.getElementById("sourceFilter");
    const feastFilter = document.getElementById("feastFilter");
    const feastSelect = document.getElementById("feastSelect");
    const genreFilter = document.getElementById("genreFilter");
    const folioFilter = document.getElementById("folioFilter");

    // Proofreading filters (radio buttons)
    const manuscriptFullTextStdProofread = document.querySelectorAll('input[name="manuscript_full_text_std_proofread"]');
    const manuscriptFullTextProofread = document.querySelectorAll('input[name="manuscript_full_text_proofread"]');
    const volpianoProofread = document.querySelectorAll('input[name="volpiano_proofread"]');

    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("source")) {
        sourceFilter.value = urlParams.get("source");
    }
    if (urlParams.has("feast")) {
        feastFilter.value = urlParams.get("feast");
        feastSelect.value = urlParams.get("feast");
    }
    if (urlParams.has("genre")) {
        genreFilter.value = urlParams.get("genre");
    }
    if (urlParams.has("folio")) {
        folioFilter.value = urlParams.get("folio");
    }

    // Set the initial state of proofreading filters based on URL parameters
    if (urlParams.has("manuscript_full_text_std_proofread")) {
        document.querySelector(`input[name="manuscript_full_text_std_proofread"][value="${urlParams.get("manuscript_full_text_std_proofread")}"]`).checked = true;
    }
    if (urlParams.has("manuscript_full_text_proofread")) {
        document.querySelector(`input[name="manuscript_full_text_proofread"][value="${urlParams.get("manuscript_full_text_proofread")}"]`).checked = true;
    }
    if (urlParams.has("volpiano_proofread")) {
        document.querySelector(`input[name="volpiano_proofread"][value="${urlParams.get("volpiano_proofread")}"]`).checked = true;
    }

    // Event listeners for the select fields and search input
    searchText.addEventListener("change", setSearch);
    sourceFilter.addEventListener("change", setSource);
    feastFilter.addEventListener("change", setFeastLeft);
    feastSelect.addEventListener("change", setFeastRight);
    genreFilter.addEventListener("change", setGenre);
    folioFilter.addEventListener("change", setFolio);

    // Event listeners for the proofreading radio buttons
    manuscriptFullTextStdProofread.forEach(radio => {
        radio.addEventListener("change", setProofreadingFilter);
    });
    manuscriptFullTextProofread.forEach(radio => {
        radio.addEventListener("change", setProofreadingFilter);
    });
    volpianoProofread.forEach(radio => {
        radio.addEventListener("change", setProofreadingFilter);
    });

    // functions for the auto-jump of various selectors and input fields on the page
    // the folio selector and folio-feast selector on the right half do source-wide filtering
    // the feast selector, genre selector, and text search on the left half do folio-wide filtering
    var url = new URL(window.location.href);

    // Handle text search change
    function setSearch() {
        const searchTerm = searchText.value;
        url.searchParams.set('search_text', searchTerm);
        window.location.assign(url);
    }

    // if the source is reset, redirect to source/<int:source_id>/chants/
    function setSource() {
        const sourceId = sourceFilter.options[sourceFilter.selectedIndex].value;
        url.pathname = "/source/" + sourceId + "/chants/";
        url.searchParams.delete('source');
        url.searchParams.delete('feast');
        url.searchParams.delete('search_text');
        url.searchParams.delete('genre');
        url.searchParams.delete('folio');
        window.location.assign(url);
    }

    // if the feast on the right is reset, reset every selector but keep the source unchanged
    function setFeastRight() {
        url.searchParams.set('folio', '');
        url.searchParams.set('search_text', '');
        url.searchParams.set('genre', '');
        const feast = feastSelect.options[feastSelect.selectedIndex].value;
        url.searchParams.set('feast', feast);
        window.location.assign(url);
    }

    // if the feast on the left is reset, keep everything else unchanged
    function setFeastLeft() {
        const feast = feastFilter.options[feastFilter.selectedIndex].value;
        url.searchParams.set('feast', feast);
        window.location.assign(url);
    }

    // if the genre is reset, keep everything else unchanged
    function setGenre() {
        const genre = genreFilter.options[genreFilter.selectedIndex].value;
        url.searchParams.set('genre', genre);
        window.location.assign(url);
    }

    // if the folio is reset, reset every selector but keep the source unchanged
    function setFolio() {
        url.searchParams.set('feast', '');
        url.searchParams.set('search_text', '');
        url.searchParams.set('genre', '');
        const folio = folioFilter.options[folioFilter.selectedIndex].value;
        url.searchParams.set('folio', folio);
        window.location.assign(url);
    }

    // Helper function to update URL parameters
    function updateURLParam(name, value) {
        if (value === "") {
            url.searchParams.delete(name);
        } else {
            url.searchParams.set(name, value);
        }
    }

    // Handle proofreading filters (radio buttons)
    function setProofreadingFilter() {
        const stdProofread = document.querySelector('input[name="manuscript_full_text_std_proofread"]:checked')?.value;
        const proofread = document.querySelector('input[name="manuscript_full_text_proofread"]:checked')?.value;
        const volpianoProof = document.querySelector('input[name="volpiano_proofread"]:checked')?.value;

        updateURLParam('manuscript_full_text_std_proofread', stdProofread);
        updateURLParam('manuscript_full_text_proofread', proofread);
        updateURLParam('volpiano_proofread', volpianoProof);
        window.location.assign(url);
    }

    function clearErrors() {
        const alert = document.getElementById("formsetErrorAlert");
        alert.replaceChildren();
        alert.classList.add("d-none");
    }

    function addError(msg) {
        const alert = document.getElementById("formsetErrorAlert");
        const alertMessage = document.createElement("div");
        alertMessage.innerText = msg;
        alert.appendChild(alertMessage);
        if (alert.classList.contains("d-none")) {
            alert.classList.remove("d-none");
        }
    };

    function toggleBulkEditForm(bulkChantEditForm, chantDisplayTable, bulkChantEditSubmit, bulkChantEditToggle) {
        bulkChantEditForm.classList.toggle("d-none");
        chantDisplayTable.classList.toggle("d-none");
        bulkChantEditSubmit.classList.toggle("d-none");
        bulkChantEditToggle.textContent = bulkChantEditForm.classList.contains("d-none") ? "Bulk Edit Chants" : "Stop Editing";
    }

    function submitBulkEditForm(bulkChantEditForm, bulkEditLoading) {
        const editFormData = new FormData(bulkChantEditForm);
        fetch(document.URL, { method: "POST", body: editFormData })
            .then(response => {
                clearErrors();
                if (response.status === 200) {
                    return response.json();
                } else {
                    throw new Error("Form submission failed. Please try again.");
                }
            })
            .then(data => {
                const taskID = data["taskID"];
                bulkEditLoading.classList.remove("d-none");
                const interval = setInterval(() => {
                    fetch(`/task-status?taskID=${taskID}`)
                        .then(response => {
                            if (response.status === 200) {
                                return response.json();
                            }
                        })
                        .then(data => {
                            if (data.status === "SUCCESS") {
                                clearInterval(interval);
                                bulkEditLoading.classList.add("d-none");
                                const result = data.result;
                                if (result.error_count === 0) {
                                    window.location.reload();
                                } else {
                                    result.non_form_errors.forEach(error => addError(error));
                                    result.form_errors.forEach(error => {
                                        addError(`Error on chant ${error[0] + 1}, ${error[1]}: ${error[2]}`);
                                    });
                                }
                            } else if (data.status === "FAILURE") {
                                clearInterval(interval);
                                addError("Form submission failed. Please try again.");
                                bulkEditLoading.classList.add("d-none");
                            }
                        });
                }, 3000);
            }, (e) => { addError(e.message) });
    }

    const userCanEditChants = document.getElementById("data-user-can-edit-chants").textContent === "true";
    if (userCanEditChants) {
        const bulkChantEditToggle = document.getElementById("bulkChantEditToggle");
        const bulkChantEditForm = document.getElementById("bulkChantEditForm");
        const chantDisplayTable = document.getElementById("chantDisplayTable");
        const bulkChantEditSubmit = document.getElementById("bulkChantEditSubmit");
        const bulkEditLoading = document.getElementById("bulkEditLoading");

        bulkChantEditToggle.addEventListener("click", () => toggleBulkEditForm(bulkChantEditForm, chantDisplayTable, bulkChantEditSubmit, bulkChantEditToggle));
        bulkChantEditSubmit.addEventListener("click", () => submitBulkEditForm(bulkChantEditForm, bulkEditLoading));
    }
});
