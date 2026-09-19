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

function isPreviewableImageLink(imageLink) {
    // Preview values have not passed server validation. Only web URLs may
    // become clickable links; invalid or other schemes remain plain text.
    try {
        const url = new URL(imageLink);
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
        return false;
    }
}

function addPreviewTableRow(tableBody, folio, imageLink) {
    // Add a row to the preview table with the folio and image link.
    const tr = document.createElement('tr');
    const tdFolio = document.createElement('td');
    tdFolio.textContent = folio;
    tdFolio.classList.add('img-link-preview-cell');
    tr.appendChild(tdFolio);
    const tdLink = document.createElement('td');
    if (isPreviewableImageLink(imageLink)) {
        const a = document.createElement('a');
        a.href = imageLink;
        a.textContent = imageLink;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        tdLink.appendChild(a);
    } else {
        tdLink.textContent = imageLink;
    }
    tdLink.classList.add('img-link-preview-cell');
    tr.appendChild(tdLink);
    tableBody.appendChild(tr);
};

function* readCSVRecords(csv, delimiter, startLine = 1) {
    // A quoted field may span physical lines. Keep those lines in the field
    // so a manifest label cannot become an extra folio/image-link record.
    let fields = [];
    let field = '';
    let state = 'unquoted';
    let line = startLine;
    let recordLine = startLine;
    for (let i = 0; i < csv.length; i++) {
        const char = csv[i];
        if (state === 'quoted' && char === '"') {
            if (csv[i + 1] === '"') {
                field += '"';
                i++;
            } else {
                state = 'closed';
            }
        } else if (char === '\r' || char === '\n') {
            const newline = char === '\r' && csv[i + 1] === '\n' ? '\r\n' : char;
            if (newline.length === 2) i++;
            if (state === 'quoted') {
                field += newline;
            } else {
                fields.push(field);
                if (fields.length > 1 || fields[0].trim()) {
                    yield { fields, line: recordLine };
                }
                fields = [];
                field = '';
                state = 'unquoted';
                recordLine = line + 1;
            }
            line++;
        } else if (state === 'quoted') {
            field += char;
        } else if (char === delimiter) {
            fields.push(field);
            field = '';
            state = 'unquoted';
        } else if (state === 'closed') {
            if (char !== ' ' && char !== '\t') {
                throw new Error(`CSV line ${line}: unexpected text after a closing quote.`);
            }
        } else if (char === '"') {
            if (field.trim()) {
                throw new Error(`CSV line ${line}: quotes must surround the whole field.`);
            }
            field = '';
            state = 'quoted';
        } else {
            field += char;
        }
    }
    if (state === 'quoted') {
        throw new Error(`CSV line ${recordLine}: a quoted field is missing its closing quote.`);
    }
    fields.push(field);
    if (fields.length > 1 || fields[0].trim()) yield { fields, line: recordLine };
}

function detectDelimiter(csv, sourceFolios) {
    // Read only the first record for each candidate. A delimiter in a URL
    // must not outweigh a header or a known folio in the first column.
    const candidates = [];
    let parseError;
    for (const delimiter of [',', ';']) {
        try {
            const record = readCSVRecords(csv, delimiter).next().value;
            candidates.push({ delimiter, first: record ? record.fields[0].trim() : '' });
        } catch (error) {
            parseError = error;
        }
    }
    if (!candidates.length) throw parseError;
    const header = candidates.find(candidate => candidate.first.toLowerCase() === 'folio');
    const known = candidates.find(candidate => sourceFolios.has(candidate.first));
    // Otherwise the incorrect delimiter usually swallows the URL into the
    // first field, making it longer than the folio under the correct split.
    return (header || known || candidates.sort((a, b) => a.first.length - b.first.length)[0]).delimiter;
}

function parseImageLinkCSV(csv, sourceFolios) {
    if (/[\uFFFD\0]/.test(csv)) {
        throw new Error('The file contains unreadable characters. Export it as UTF-8 CSV and select it again.');
    }
    csv = csv.replace(/^\uFEFF/, '');
    // Excel can precede the header with a delimiter declaration.
    const declaration = csv.match(/^sep=([,;])(?:\r\n|\r|\n)/i);
    if (declaration) csv = csv.slice(declaration[0].length);
    const delimiter = declaration ? declaration[1] : detectDelimiter(csv, sourceFolios);
    const parsedCSV = [];
    let columns;
    for (const { fields, line } of readCSVRecords(csv, delimiter, declaration ? 2 : 1)) {
        if (columns === undefined) {
            const hasHeader = fields[0].trim().toLowerCase() === 'folio';
            columns = hasHeader ? fields.length : 2;
            if (columns < 2) {
                throw new Error('The CSV needs folio and image-link columns separated by commas or semicolons.');
            }
            if (hasHeader) continue;
        }
        if (fields.length !== columns) {
            throw new Error(`CSV line ${line}: expected ${columns} columns, found ${fields.length}. `
                + 'Quote links containing delimiters and keep the header when importing extra columns.');
        }
        const folio = fields[0].trim();
        const imageLink = fields[1].trim();
        if (/[\r\n\t]/.test(folio + imageLink)) {
            throw new Error(`CSV line ${line}: folios and image links cannot contain tabs or line breaks.`);
        }
        if (!folio) continue;
        parsedCSV.push({ folio, imageLink });
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
    // Earlier rows for a repeated folio are superseded, including when its
    // final row has a blank link. Count only the links that will be applied.
    const finalRows = new Map(parsedCSV.map(row => [row.folio, row]));
    const linkedRows = Array.from(finalRows.values()).filter(row => row.imageLink);
    const shared = groupFoliosBySharedImageLink(linkedRows);
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
    function clearImport() {
        submit.disabled = true;
        document.getElementById('imgLinkData').value = '';
        document.getElementById('csvPreviewBody').innerHTML = '';
        document.getElementById('csvPreviewDiv').hidden = true;
        document.getElementById('csvTestingDiv').hidden = true;
        error.hidden = true;
        error.textContent = '';
    }
    // A returned form may hold an invalid previous submission. Require a file
    // selection so the user always sees the rows they are about to save.
    clearImport();
    input.addEventListener('change', function (event) {
        const currentSelection = ++selection;
        clearImport();
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (event) {
            if (currentSelection !== selection) return;
            try {
                const rows = csvLoadCallback(event.target.result);
                submit.disabled = rows.length === 0;
                if (!rows.length) {
                    error.textContent = 'The file contains no folio rows. Select another CSV file.';
                    error.hidden = false;
                }
            } catch (cause) {
                clearImport();
                error.textContent = cause.message;
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
    };
}
