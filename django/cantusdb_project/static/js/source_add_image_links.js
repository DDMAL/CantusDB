// Reads the CSV the administrator selects on the Add Image Links page, shows
// it, checks it, and writes it into the form.
//
// The form carries one hidden field holding the rows of the selected file, as
// a JSON list of [folio, image link] pairs. A field per folio would send more
// fields than Django accepts in one request for a source the size of Tours 149
// (1044 folios), and rebuilding the single field on every selection is what
// keeps a replaced file from leaving its predecessor's links behind.

function getSourceFolios() {
    // The page lists the source's folios once, as JSON.
    const element = document.getElementById('sourceFolios');
    return element ? JSON.parse(element.textContent) : [];
}

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

function detectDelimiter(firstRow, sourceFolios) {
    // Some locales (e.g. French) export semicolon-delimited CSVs, but both
    // characters are legal inside a URL, so the delimiter can't be inferred
    // from mere presence: a comma-delimited row whose link contains a
    // semicolon would otherwise be split on the semicolon, swallowing the
    // whole URL into the folio field.
    const candidates = [',', ';'];
    const firstFields = candidates.map(d => splitCSVRow(firstRow, d)[0].trim());
    // A header row names the column outright.
    const header = candidates.findIndex(
        (_, i) => firstFields[i].toLowerCase() === 'folio'
    );
    if (header !== -1) return candidates[header];
    // Otherwise, a first field naming a folio this source has is decisive.
    const known = candidates.findIndex((_, i) => sourceFolios.has(firstFields[i]));
    if (known !== -1) return candidates[known];
    // Failing both — the CSV may legitimately list folios the source lacks —
    // prefer the delimiter giving the shorter first field. A folio is short;
    // the losing split swallows the image URL, so it is much longer.
    return firstFields[1].length < firstFields[0].length ? ';' : ',';
}

function parseImageLinkCSV(csv, sourceFolios) {
    // Parse the CSV file into the rows it lists, in file order, as objects
    // with folio and imageLink keys.
    const rows = csv.split('\n');
    // Work from the first row with content: a leading blank line would
    // otherwise defeat both the delimiter and the header check below.
    const firstRowIndex = rows.findIndex(row => row.trim());
    const firstRow = firstRowIndex === -1 ? '' : rows[firstRowIndex];
    const delimiter = detectDelimiter(firstRow, sourceFolios);
    // Check if a header row is present by looking at the first column name.
    // Sniffing the second column for a URL instead would swallow the first
    // row of a headerless CSV whenever its image link is blank.
    const firstColumn = splitCSVRow(firstRow, delimiter)[0].trim().toLowerCase();
    let start;
    if (firstRowIndex === -1) {
        start = rows.length; // nothing but blank lines
    } else {
        start = firstColumn === 'folio' ? firstRowIndex + 1 : firstRowIndex;
    }
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
        parsedCSV.push({ "folio": folio, "imageLink": imageLink });
    }
    return parsedCSV;
}

function displayPreview(parsedCSV) {
    // Show the rows just parsed, replacing whatever the last file left.
    const tableBody = document.getElementById('csvPreviewBody');
    tableBody.innerHTML = '';
    parsedCSV.forEach(row => addPreviewTableRow(tableBody, row.folio, row.imageLink));
    document.getElementById("csvPreviewDiv").hidden = false;
}

function setImageLinkFormData(parsedCSV) {
    // Rebuild the whole field from the rows just parsed. Selecting another
    // file therefore replaces the submission rather than adding to it, so the
    // links that get saved are the ones the preview shows.
    document.getElementById('imgLinkData').value = JSON.stringify(
        parsedCSV.map(row => [row.folio, row.imageLink])
    );
}

function getDuplicatedFolios(parsedCSV) {
    // Return the folios the file lists more than once, sorted. The importer
    // applies the last row for such a folio.
    const folioCounts = {};
    parsedCSV.forEach(row => {
        folioCounts[row.folio] = (folioCounts[row.folio] || 0) + 1;
    });
    return Object.keys(folioCounts).filter(folio => folioCounts[folio] > 1).sort();
}

function groupFoliosBySharedImageLink(parsedCSV) {
    // Group the folios that share an image link, one array of folios per link.
    const foliosByLink = new Map();
    parsedCSV.forEach(({ folio, imageLink }) => {
        if (!imageLink) return;
        if (!foliosByLink.has(imageLink)) foliosByLink.set(imageLink, []);
        foliosByLink.get(imageLink).push(folio);
    });
    return Array.from(foliosByLink.values()).filter(folios => folios.length > 1);
}

function checkSharedImageLinks(parsedCSV) {
    // Describe how the file shares image links between folios. One photograph
    // showing two facing folios gives each of them the same link, so pairs are
    // ordinary; a link on three or more folios usually means rows have slipped.
    const linkedRows = parsedCSV.filter(row => row.imageLink);
    const shared = groupFoliosBySharedImageLink(parsedCSV);
    if (shared.length === 0) {
        return { folios: [], success: 'Every folio has its own image link' };
    }
    if (shared.length === 1 && shared[0].length === linkedRows.length) {
        return { folios: [], success: 'All folios share one image link' };
    }
    const crowded = shared.filter(folios => folios.length > 2);
    if (crowded.length === 0) {
        const pairs = shared.length;
        return {
            folios: [],
            success: `${pairs} image link${pairs === 1 ? '' : 's'} shared by two `
                + 'folios each, as photographs of facing folios are',
        };
    }
    return {
        folios: crowded.flat().sort(),
        error: 'The following folios share an image link with two or more others',
    };
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

function displayCSVChecks(parsedCSV, sourceFolios) {
    // Display duplicated folios, if they exist.
    displayCheckResults('folioDuplication', getDuplicatedFolios(parsedCSV),
        "The following folios are duplicated in the CSV");
    // Check whether there are any folios in the source that are not in the CSV
    // Display these folios with missing Links in the preview table.
    const csvFolios = new Set(parsedCSV.map(row => row.folio));
    const missingLinks = Array.from(sourceFolios).filter(folio => !csvFolios.has(folio));
    displayCheckResults('folioCompleteness', missingLinks,
        "Image links missing for the following folios");
    // Check whether there are any folios in the CSV that are not in the source
    // Display these folios as extra folios in the preview table.
    const extraFolios = Array.from(csvFolios).filter(folio => !sourceFolios.has(folio));
    displayCheckResults('extraFolios', extraFolios.sort(),
        "The following folios do not exist in the source");
    const sharedLinks = checkSharedImageLinks(parsedCSV);
    displayCheckResults('imageLinkDuplication', sharedLinks.folios,
        sharedLinks.error || '', sharedLinks.success || '');
    document.getElementById('csvTestingDiv').hidden = false;
}

function csvLoadCallback(csv) {
    // Callback function for when a CSV file is loaded.
    // Parse the CSV file, display it in the table, put it in the form,
    // then run checks for completeness and uniqueness.
    const sourceFolios = new Set(getSourceFolios());
    const parsedCSV = parseImageLinkCSV(csv, sourceFolios);
    displayPreview(parsedCSV);
    setImageLinkFormData(parsedCSV);
    displayCSVChecks(parsedCSV, sourceFolios);
    return parsedCSV;
}

function initializeCSVImport() {
    const input = document.getElementById('imgLinksCSV');
    const submit = document.getElementById('imgLinkFormSubmitBtn');
    const error = document.getElementById('csvReadError');
    let selection = 0;
    // A returned form may hold an invalid previous submission. Require a file
    // selection so the user always sees the rows they are about to save.
    document.getElementById('imgLinkData').value = '';
    submit.disabled = true;
    input.addEventListener('change', function (event) {
        const currentSelection = ++selection;
        submit.disabled = true;
        document.getElementById('imgLinkData').value = '';
        document.getElementById('csvPreviewBody').innerHTML = '';
        document.getElementById('csvPreviewDiv').hidden = true;
        document.getElementById('csvTestingDiv').hidden = true;
        error.hidden = true;
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (event) {
            if (currentSelection !== selection) return;
            const rows = csvLoadCallback(event.target.result);
            submit.disabled = rows.length === 0;
            if (!rows.length) {
                error.textContent = 'The file contains no folio rows. Select another CSV file.';
                error.hidden = false;
            }
        };
        reader.onerror = function () {
            if (currentSelection !== selection) return;
            error.textContent = 'The file could not be read. Select the CSV file again.';
            error.hidden = false;
        };
        reader.readAsText(file);
    });
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', initializeCSVImport);
}

// Exported for the Node tests; the browser loads this file as a plain script.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeCSVImport,
        checkSharedImageLinks,
        csvLoadCallback,
        detectDelimiter,
        getDuplicatedFolios,
        parseImageLinkCSV,
        splitCSVRow,
    };
}
