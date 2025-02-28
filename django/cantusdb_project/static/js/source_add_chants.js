function updatePreviewHeader(columnHeaders) {
    // Update the header row of the preview table
    //  - columnHeaders: an array of strings with the column headers
    const tableHead = document.getElementById('csvPreviewHead');
    tableHead.innerHTML = '';
    for (let i = 0; i < columnHeaders.length; i++) {
        const th = document.createElement('th');
        th.textContent = columnHeaders[i];
        tableHead.appendChild(th);
    }
};

function createTableCell(value) {
    // Create a table cell with the given value
    // doing the necessary replacements for values
    // coming from our csv file match regex:
    // - unescape double quotes
    // - remove leading and trailing quotes
    // - remove leading and trailing commas
    // - remove leading and trailing whitespace
    value = value.replaceAll(/^[",]*|[,"]*$/g, '');
    value = value.trim().replaceAll(/""/g, '"');
    const td = document.createElement('td');
    td.textContent = value;
    return [td, value];
}

function styleTableError(elem, error_message) {
    // Style a table element (tr or td) as an error
    elem.classList.add('table-danger');
    elem.setAttribute('data-bs-title', error_message);
    new bootstrap.Tooltip(elem);
}

function csvLoadCallback(csv, relatedFieldMaps) {
    // Instantiate a FormData object with our existing
    // form data. 
    const addChantsForm = new FormData(document.getElementById('addChantsForm'));
    // Remove the values from a previously-selected file
    // from the form data 
    addChantsForm.set('new_chants', null);
    // Parse the CSV file and display it in the table.
    parseCSVUpdateFormAndPreview(csv, addChantsForm, relatedFieldMaps);
    return addChantsForm;
};


async function getRelatedFieldMap(relatedField) {
    // Get a map of name -> id for related field
    // values. Calls the endpoint provided and returns
    // a promise that resolves to the
    // map of related field values.
    // Intended to work with one of the following
    // values for relatedField:
    // - 'genres'
    // - 'services'
    // - 'feasts'
    const endpoint = `/${relatedField}/`;
    return fetch(endpoint, { headers: { 'Accept': 'application/json' } })
        .then(response => response.json())
        .then(data => {
            const fieldData = data[relatedField];
            const nameIDMap = {};
            for (let i = 0; i < fieldData.length; i++) {
                nameIDMap[fieldData[i].name] = fieldData[i].id;
            }
            return nameIDMap;
        })
        .catch((error) => {
            console.error('Error:', error);
        });
}

function parseCSVUpdateFormAndPreview(csv, formData, relatedFieldMaps) {
    // Parse the passed CSV file and update the preview
    // table and the form with the new data. 
    const rows = csv.split('\n');
    const columnHeaders = rows[0].trim().split(',');
    updatePreviewHeader(columnHeaders);
    const tableBody = document.getElementById('csvPreviewBody');
    tableBody.innerHTML = '';
    newChantsJSON = [];
    const relatedFieldNames = ['genre', 'service', 'feast'];
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        // Split the row into columns with a regex pattern that
        // accounts for commas inside quotes.
        const rowValues = row.match(/(?:"([^"]*(?:""[^"]*)*)")|([^",]+)|(?:,)()(?=,)/g)
        const tr = document.createElement('tr');
        newChantObj = {};
        for (let j = 0; j < rowValues.length; j++) {
            // Unescape double quotes
            const rowValue = rowValues[j];
            const [td, escapedRowValue] = createTableCell(rowValue);
            tr.appendChild(td);
            // If the column is a related field, add the id to the form data
            if (relatedFieldNames.includes(columnHeaders[j])) {
                // If the value of the field is blank, set it to null, but if the 
                // value is not blank but does not map to a valid id, flag it.
                if (escapedRowValue === '') {
                    newChantObj[columnHeaders[j]] = null;
                } else if (relatedFieldMaps[`${columnHeaders[j]}s`].hasOwnProperty(escapedRowValue)) {
                    newChantObj[columnHeaders[j]] = relatedFieldMaps[`${columnHeaders[j]}s`][escapedRowValue];
                } else {
                    styleTableError(td, `Invalid value for ${columnHeaders[j]}`);
                    addGeneralErrorAlert(`Found: invalid value for ${columnHeaders[j]}. See red cells for details.`);
                }
            } else {
                newChantObj[columnHeaders[j]] = escapedRowValue;
            }
        }
        tableBody.appendChild(tr);
        newChantsJSON.push(newChantObj);
        document.getElementById("csvPreviewDiv").hidden = false;
        formData.set('new_chants', JSON.stringify(newChantsJSON));
    }
};

function addLoadingSpinner(button) {
    const spinnerElem = document.createElement('div');
    spinnerElem.classList.add('spinner-border', 'spinner-border-sm');
    spinnerElem.setAttribute('role', 'status');
    const spinnerSpan = document.createElement('span');
    spinnerSpan.classList.add('visually-hidden');
    spinnerSpan.textContent = 'Loading...';
    spinnerElem.appendChild(spinnerSpan);
    button.appendChild(spinnerElem);
};

function removeLoadingSpinner(button) {
    button.removeChild(button.lastChild);
};

function addGeneralErrorAlert(error_message) {
    // Add a general error alert to the form
    const formErrorDiv = document.getElementById("formErrorAlertDiv");
    const alert = document.createElement('div');
    alert.classList.add('alert', 'alert-danger', 'alert-dismissible');
    formErrorDiv.appendChild(alert);
    alert.setAttribute('role', 'alert');
    alert.textContent = error_message;
    const closeButton = document.createElement('button');
    closeButton.classList.add('btn-close');
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');
    closeButton.setAttribute('type', 'button');
    alert.appendChild(closeButton);
    new bootstrap.Alert(alert);
};

document.addEventListener('DOMContentLoaded', function () {
    var addChantsForm;
    // Add listener to the file input field to parse and display the CSV file
    document.getElementById('addChantsCSV').addEventListener('change', function (e) {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = function (e) {
            const csv = e.target.result;
            addChantsForm = csvLoadCallback(csv, relatedFieldMaps);
        };
        reader.readAsText(file);
    });
    // Add a listener to handle the form submission
    document.getElementById('addChantsForm').addEventListener('submit', function (e) {
        e.preventDefault();
        // Add loading spinner to the submit button
        const submitButton = document.getElementById('addChantsFormSubmitBtn');
        addLoadingSpinner(submitButton);
        // Post the form data to the server
        fetch(this.action, {
            method: 'POST',
            body: addChantsForm
        })
            .then(response => {
                // Remove the loading spinner from the submit button
                removeLoadingSpinner(submitButton);
                // If the response is not ok, display the errors.
                if (!response.ok) {
                    response.json().then(data => {
                        if (data['form_error']) {
                            // If there is a form error, it is a general error
                            // that we'll show as an alert.
                            addGeneralErrorAlert(data['form_error']);
                        };
                        if (data['formset_errors']) {
                            // If there are errors, they are chant-specific errors
                            // that we'll display in the preview table.
                            const columns = document.getElementById('csvPreviewHead').children;
                            const tableBody = document.getElementById('csvPreviewBody');
                            const rows = tableBody.children;
                            for (error of data['formset_errors']) {
                                const error_row = rows[error['form_idx']];
                                if (error["field_name"] === "__all__") {
                                    styleTableError(error_row, error["error"]);
                                } else {
                                    const cellIndex = Array.from(columns).findIndex(cell => cell.textContent === error["field_name"]);
                                    const errorCell = error_row.children[cellIndex];
                                    styleTableError(errorCell, error["error"]);
                                };
                            };
                            addGeneralErrorAlert("Errors were found in individual chants. Hover over red cells to see the errors.");
                        }
                    }
                    );
                } else {
                    // If the response is ok, it is a redirect to the 
                    // browse chants page. Redirect the user to that page.
                    window.location.href = response.url;
                }
            });

    });
    var relatedFieldMaps = {};
    // Get the related field maps
    const relatedFields = ['genres', 'services', 'feasts'];
    relatedFields.forEach(async (relatedField) => {
        relatedFieldMaps[relatedField] = await getRelatedFieldMap(relatedField);
    });
}
);