function addPreviewTableRow(tableBody, folio, imageLink) {
    // Add a row to the preview table with the folio and image link.
    const tr = document.createElement('tr');
    const tdFolio = document.createElement('td');
    tdFolio.textContent = folio;
    tdFolio.classList.add('img-link-preview-cell');
    tr.appendChild(tdFolio);
    const tdLink = document.createElement('td');
    const a = document.createElement('a');
    a.href = imageLink;
    a.textContent = imageLink;
    a.target = '_blank';
    tdLink.appendChild(a);
    tdLink.classList.add('img-link-preview-cell');
    tr.appendChild(tdLink);
    tableBody.appendChild(tr);
};

function getFormImgLinkInputs(form) {
    // Get all the input elements in the form that have the 
    // 'img-link-input' class and return them as a map of the form
    // {folio: inputElement}.
    const imgLinkInputs = form.getElementsByClassName('img-link-input');
    const imgLinkMap = {};
    for (let i = 0; i < imgLinkInputs.length; i++) {
        const folio = imgLinkInputs[i].name;
        imgLinkMap[folio] = imgLinkInputs[i];
    }
    return imgLinkMap;
};


function splitCSVRow(row, delimiter) {
    // Split one CSV line into fields, respecting quoted fields (and doubled
    // quotes within them). A plain `split` mis-handles IIIF image URLs, which
    // routinely contain commas — e.g. `/full/500,/0/default.jpg` — and which
    // Python's csv.writer therefore emits quoted.
    // Known limitation: a quoted field containing a line break is not
    // supported, since rows are split on newlines before reaching here.
    const fields = [];
    let field = '';
    let inQuotes = false;
    for (let i = 0; i < row.length; i++) {
        const char = row[i];
        if (inQuotes) {
            if (char !== '"') {
                field += char;
            } else if (row[i + 1] === '"') {
                field += '"';
                i++;
            } else {
                inQuotes = false;
            }
        } else if (char === '"' && field === '') {
            inQuotes = true;
        } else if (char === delimiter) {
            fields.push(field);
            field = '';
        } else {
            field += char;
        }
    }
    fields.push(field);
    return fields;
}

function parseAndPreviewImageLinkCSV(csv, imgLinkInputs) {
    // Parse the passed CSV file and display it in a table. 
    // Return two arrays: one with the folios and one with the image links
    // for use in testing functions.
    const rows = csv.split('\n');
    // Work from the first row with content: a leading blank line would
    // otherwise defeat both the delimiter and the header check below.
    const firstRowIndex = rows.findIndex(row => row.trim());
    const firstRow = firstRowIndex === -1 ? '' : rows[firstRowIndex];
    // Auto-detect delimiter: some locales (e.g. French) use semicolons
    const delimiter = firstRow.includes(';') ? ';' : ',';
    // Check if a header row is present by looking at the first column name.
    // Sniffing the second column for a URL instead would swallow the first
    // row of a headerless CSV whenever its image link is blank.
    const firstColumn = firstRow.split(delimiter)[0].trim().toLowerCase();
    let start;
    if (firstRowIndex === -1) {
        start = rows.length; // nothing but blank lines
    } else {
        start = firstColumn === 'folio' ? firstRowIndex + 1 : firstRowIndex;
    }
    const tableBody = document.getElementById('csvPreviewBody');
    // Clear the table and fill in the new data. Only the first two columns
    // are read; anything beyond them is ignored.
    tableBody.innerHTML = '';
    const parsedCSV = [];
    for (let i = start; i < rows.length; i++) {
        const row = rows[i].trim();
        if (!row) continue;
        const fields = splitCSVRow(row, delimiter);
        const folio = (fields[0] || '').trim();
        if (!folio) continue;
        // Any further columns (the generated IIIF CSV also carries `notes`
        // and `canvas_label`) are for the administrator to read, not for us.
        const imageLink = (fields[1] || '').trim();
        addPreviewTableRow(tableBody, folio, imageLink);
        const folioInput = imgLinkInputs[folio];
        if (folioInput) {
            folioInput.value = imageLink;
        }
        parsedCSV.push({ "folio": folio, "imageLink": imageLink });
    }
    document.getElementById("csvPreviewDiv").hidden = false;
    return parsedCSV;
}

function getFoliosAtDuplicatedValues(array) {
    // Given an array of objects with imageLink and folio keys,
    // parsed from the CSV file, return an array of folios that have
    // been duplicated and an array of folios that have duplicated image links.
    const folioCounts = {};
    const imageLinkCounts = {};
    for (let i = 0; i < array.length; i++) {
        const folio = array[i].folio;
        const imageLink = array[i].imageLink;
        folioCounts[folio] = (folioCounts[folio] || 0) + 1;
        imageLinkCounts[imageLink] = (imageLinkCounts[imageLink] || 0) + 1;
    }
    const folioDuplicates = Object.keys(folioCounts).filter(folio => folioCounts[folio] > 1);
    const imageLinkDuplicates = Object.keys(imageLinkCounts).filter(imageLink => imageLink !== '' && imageLinkCounts[imageLink] > 1);
    const folioWImageDuplicates = [];
    for (let i = 0; i < array.length; i++) {
        if (imageLinkDuplicates.includes(array[i].imageLink)) {
            folioWImageDuplicates.push(array[i].folio);
        }
    }
    return [folioDuplicates.sort(), folioWImageDuplicates.sort()];
}

function displayCheckResults(checkName, failingFolios, error_message, success_message = '') {
    const iconCell = document.getElementById(`${checkName}Icon`);
    const instancesCell = document.getElementById(`${checkName}Instances`);
    if (failingFolios.length === 0) {
        iconCell.className = 'bi bi-check-circle-fill text-success';
        instancesCell.textContent = success_message;
    } else {
        iconCell.className = 'bi bi-exclamation-circle-fill text-warning';
        instancesCell.textContent = `${error_message}: ${failingFolios.join(', ')}`;
    }
};

function csvLoadCallback(csv) {
    // Callback function for when a CSV file is loaded.
    // Parse the CSV file and display it in the table,
    // then run checks for completeness and uniqueness.
    const imgLinkInputs = getFormImgLinkInputs(document.getElementById('imgLinkForm'));
    const sourceFolios = Object.keys(imgLinkInputs);
    const parsedCSV = parseAndPreviewImageLinkCSV(csv, imgLinkInputs);
    const [dupFolios, foliosWDupImageLinks] = getFoliosAtDuplicatedValues(parsedCSV);
    // Display duplicated folios, if they exist.
    displayCheckResults('folioDuplication', dupFolios, "The following folios are duplicated in the CSV");
    // Check whether there are any folios in the source that are not in the CSV
    // Display these folios with missing Links in the preview table.
    const csvFolios = parsedCSV.map(x => x.folio);
    const missingLinks = sourceFolios.filter(folio => !csvFolios.includes(folio));
    displayCheckResults('folioCompleteness', missingLinks, "Image links missing for the following folios");
    // Check whether there are any folios in the CSV that are not in the source
    // Display these folios as extra folios in the preview table.
    const extraFolios = csvFolios.filter(folio => !sourceFolios.includes(folio));
    displayCheckResults('extraFolios', extraFolios.sort(), "The following folios do not exist in the source");
    // We expect one of two cases for the value of image links:
    // 1. All image links are identical
    // 2. All image links are unique
    // Note that a mapping might be valid that does not conform to these cases
    // (for example, if every image link shows two facing folios). In that case, the
    // check will fail and we rely on the administrator to check the data.
    if (foliosWDupImageLinks.length === csvFolios.length) {
        displayCheckResults('imageLinkDuplication', [], "", "All image links identical");
    } else {
        displayCheckResults('imageLinkDuplication', foliosWDupImageLinks, "Image links duplicated on the following subset of folios");
    }
    document.getElementById('csvTestingDiv').hidden = false;
}

document.addEventListener('DOMContentLoaded', function () {
    // Add listener to the file input field to parse and display the CSV file
    document.getElementById('imgLinksCSV').addEventListener('change', function (e) {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = function (e) {
            const csv = e.target.result;
            csvLoadCallback(csv);
        };
        reader.readAsText(file);
    });
}
);
