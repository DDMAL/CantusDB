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
    const otherFieldsProofread = document.querySelectorAll('input[name="other_fields_proofread"]');

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
    if (urlParams.has("other_fields_proofread")) {
        document.querySelector(`input[name="other_fields_proofread"][value="${urlParams.get("other_fields_proofread")}"]`).checked = true;}

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
    otherFieldsProofread.forEach(radio => {
        radio.addEventListener("change", setProofreadingFilter)});

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
        const otherFieldsProof = document.querySelector('input[name="other_fields_proofread"]:checked')?.value;


        updateURLParam('manuscript_full_text_std_proofread', stdProofread);
        updateURLParam('manuscript_full_text_proofread', proofread);
        updateURLParam('volpiano_proofread', volpianoProof);
        updateURLParam('other_fields_proofread', otherFieldsProof);
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

    let bulkSaveInFlight = false;
    let bulkChangesSaved = false;
    const warningEchoes = new Map();

    function clearTextWarnings() {
        const alert = document.getElementById("formsetTextWarningAlert");
        alert.replaceChildren();
        alert.classList.add("d-none");
        warningEchoes.forEach((echo, field) => {
            echo.remove();
            field.classList.remove("chant-text-warning-field");
        });
        warningEchoes.clear();
    }

    function showTextWarnings(warnings, form, submittedData) {
        const alert = document.getElementById("formsetTextWarningAlert");
        const heading = document.createElement("p");
        heading.textContent = "Changes saved. Nonstandard text was found in the submitted chants. You can correct it below or choose Stop Editing.";
        const list = document.createElement("ul");
        warnings.forEach(warning => {
            const item = document.createElement("li");
            item.textContent = `Chant ${warning.form_num + 1}, ${warning.label}: ${warning.message}`;
            list.appendChild(item);
            const name = `chant_set-${warning.form_num}-${warning.field}`;
            const field = form.elements.namedItem(name);
            // The result describes the submitted text. A user may have kept
            // editing while the task ran; don't mark those newer values.
            if (!field || field.value !== submittedData.get(name)) return;
            let echo = warningEchoes.get(field);
            if (!echo) {
                echo = document.createElement("div");
                echo.className = "chant-text-warning-echo small";
                field.insertAdjacentElement("afterend", echo);
                field.classList.add("chant-text-warning-field");
                warningEchoes.set(field, echo);
            }
            const marked = document.createElement("div");
            marked.className = "chant-text-warning-marked";
            // Only the server's escaped text with <mark> tags is HTML.
            marked.innerHTML = warning.marked_html;
            echo.appendChild(marked);
        });
        alert.appendChild(heading);
        alert.appendChild(list);
        alert.classList.remove("d-none");
        alert.scrollIntoView({ block: "nearest" });
    }

    function toggleBulkEditForm(bulkChantEditForm, chantDisplayTable, bulkChantEditSubmit, bulkChantEditToggle) {
        if (bulkSaveInFlight) return;
        if (bulkChangesSaved) {
            window.location.reload();
            return;
        }
        bulkChantEditForm.classList.toggle("d-none");
        chantDisplayTable.classList.toggle("d-none");
        bulkChantEditSubmit.classList.toggle("d-none");
        bulkChantEditToggle.textContent = bulkChantEditForm.classList.contains("d-none") ? "Bulk Edit Chants" : "Stop Editing";
    }

    function submitBulkEditForm(bulkChantEditForm, bulkEditLoading) {
        if (bulkSaveInFlight) return;
        const editFormData = new FormData(bulkChantEditForm);
        const submit = document.getElementById("bulkChantEditSubmit");
        const toggle = document.getElementById("bulkChantEditToggle");
        bulkSaveInFlight = true;
        submit.disabled = true;
        toggle.disabled = true;
        clearErrors();
        clearTextWarnings();
        bulkEditLoading.classList.remove("d-none");

        function finish() {
            bulkSaveInFlight = false;
            submit.disabled = false;
            toggle.disabled = false;
            bulkEditLoading.classList.add("d-none");
        }

        function poll(taskID) {
            fetch(`/task-status/?taskID=${encodeURIComponent(taskID)}`)
                .then(response => {
                    if (response.status !== 200) throw new Error("Task status unavailable");
                    return response.json();
                })
                .then(data => {
                    if (data.status === "SUCCESS") {
                        finish();
                        const result = data.result;
                        if (result.error_count === 0) {
                            bulkChangesSaved = true;
                            // Older workers may finish a task without this field.
                            const warnings = result.text_warnings || [];
                            if (warnings.length) {
                                showTextWarnings(warnings, bulkChantEditForm, editFormData);
                            } else {
                                window.location.reload();
                            }
                        } else {
                            result.non_form_errors.forEach(error => addError(error.message));
                            result.form_errors.forEach(error => {
                                addError(`Error on chant ${error[0] + 1}, ${error[1]}: ${error[2]}`);
                            });
                        }
                    } else if (data.status === "FAILURE") {
                        finish();
                        addError("Form submission failed. Please try again.");
                    } else {
                        // Wait for this response before scheduling another poll:
                        // the endpoint consumes a completed task's result once.
                        setTimeout(() => poll(taskID), 3000);
                    }
                })
                .catch(() => {
                    finish();
                    addError("Unable to check whether changes were saved. Reload the page to check before trying again.");
                });
        }

        fetch(document.URL, { method: "POST", body: editFormData })
            .then(response => {
                if (response.status === 200) {
                    return response.json();
                } else {
                    throw new Error("Form submission failed. Please try again.");
                }
            })
            .then(data => {
                setTimeout(() => poll(data.taskID), 3000);
            })
            .catch(e => {
                finish();
                addError(e.message);
            });
    }

    const userCanEditChants = document.getElementById("data-user-can-edit-chants").textContent === "true";
    if (userCanEditChants) {
        const bulkChantEditToggle = document.getElementById("bulkChantEditToggle");
        const bulkChantEditForm = document.getElementById("bulkChantEditForm");
        const chantDisplayTable = document.getElementById("chantDisplayTable");
        const bulkChantEditSubmit = document.getElementById("bulkChantEditSubmit");
        const bulkEditLoading = document.getElementById("bulkEditLoading");

        bulkChantEditForm.addEventListener("input", event => {
            const echo = warningEchoes.get(event.target);
            if (echo) {
                echo.remove();
                event.target.classList.remove("chant-text-warning-field");
                warningEchoes.delete(event.target);
            }
        });
        bulkChantEditToggle.addEventListener("click", () => toggleBulkEditForm(bulkChantEditForm, chantDisplayTable, bulkChantEditSubmit, bulkChantEditToggle));
        bulkChantEditSubmit.addEventListener("click", () => submitBulkEditForm(bulkChantEditForm, bulkEditLoading));
    }
});
