// Regression tests for the Add Image Links CSV importer.
//
// Run with: node --test "tests/js/**/*.test.js"
//
// The page script is a plain browser script, so these tests stand a small DOM
// in for the page: enough to hold the elements the script reads and writes.
// They exercise the script's own parsing, form-filling and checking; they say
// nothing about how a browser renders the page.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
    initializeCSVImport,
    checkSharedImageLinks,
    csvLoadCallback,
} = require(path.join(
    __dirname, '..', '..', 'django', 'cantusdb_project',
    'static', 'js', 'source_add_image_links.js'
));

class StubElement {
    constructor(tagName) {
        this.tagName = tagName;
        this.children = [];
        this.textContent = '';
        this.className = '';
        this.value = '';
        this.href = '';
        this.target = '';
        this.hidden = true;
        this.classList = { add: () => { } };
        this._innerHTML = '';
        this.listeners = {};
        this.disabled = false;
    }

    get innerHTML() {
        return this._innerHTML;
    }

    // The script empties the preview table by assigning '', so the stub has to
    // drop the rows it holds for a replaced file to be observable.
    set innerHTML(value) {
        this._innerHTML = value;
        if (value === '') this.children = [];
    }

    addEventListener(type, callback) {
        this.listeners[type] = callback;
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }
}

const CHECKS = ['folioDuplication', 'folioCompleteness', 'extraFolios', 'imageLinkDuplication'];

function installDOM(sourceFolios) {
    const elements = new Map();
    const element = (id) => {
        if (!elements.has(id)) elements.set(id, new StubElement('div'));
        return elements.get(id);
    };
    ['csvPreviewBody', 'csvPreviewDiv', 'csvTestingDiv', 'imgLinkData', 'sourceFolios', 'imgLinksCSV', 'imgLinkFormSubmitBtn', 'csvReadError'].forEach(element);
    CHECKS.forEach((name) => {
        element(`${name}Icon`);
        element(`${name}Instances`);
    });
    element('sourceFolios').textContent = JSON.stringify(sourceFolios);
    global.document = {
        getElementById: (id) => (elements.has(id) ? elements.get(id) : null),
        createElement: (tagName) => new StubElement(tagName),
        addEventListener: () => { },
    };
    return {
        element,
        submittedLinks: () => JSON.parse(element('imgLinkData').value || '[]'),
        previewedFolios: () => element('csvPreviewBody').children.map(
            (row) => row.children[0].textContent
        ),
        previewedLinks: () => element('csvPreviewBody').children.map(
            (row) => row.children[1].children[0].textContent
        ),
        check: (name) => ({
            state: element(`${name}Icon`).className.includes('check-circle') ? 'ok' : 'warning',
            text: element(`${name}Instances`).textContent,
        }),
    };
}

test('selecting a replacement CSV replaces the links the form will submit', () => {
    const dom = installDOM(['001r', '001v']);

    csvLoadCallback('folio,image_link\n001r,https://example.com/1r\n001v,https://example.com/1v');
    assert.deepEqual(dom.submittedLinks(), [
        ['001r', 'https://example.com/1r'],
        ['001v', 'https://example.com/1v'],
    ]);

    // The second file covers only 001r. The links carried by the form, like
    // the preview, must now describe that file alone: 001v's link came from a
    // file the administrator has replaced and is no longer shown.
    csvLoadCallback('folio,image_link\n001r,https://example.com/corrected-1r');
    assert.deepEqual(dom.submittedLinks(), [['001r', 'https://example.com/corrected-1r']]);
    assert.deepEqual(dom.previewedFolios(), ['001r']);
    assert.equal(dom.check('folioCompleteness').state, 'warning');
    assert.match(dom.check('folioCompleteness').text, /001v/);
});

test('a generated IIIF mapping CSV round-trips through the form', () => {
    const dom = installDOM(['001v', '002r', '003r']);
    const sharedImage = 'https://example.com/iiif/img1/full/max,0/default.jpg';
    // As SourceIIIFMappingView writes it: four columns, an unmatched canvas
    // with no folio, an unmatched folio with no link, and a spread whose two
    // folios share one image. The URL holds a comma, so it arrives quoted.
    csvLoadCallback([
        'folio,image_link,notes,canvas_label',
        `001v,"${sharedImage}",,f. 001v - 002r`,
        `002r,"${sharedImage}",,f. 001v - 002r`,
        ',https://example.com/iiif/img2.jpg,No matching folio in source,plat supérieur',
        '003r,,No matching canvas in manifest,',
    ].join('\n'));

    assert.deepEqual(dom.submittedLinks(), [
        ['001v', sharedImage],
        ['002r', sharedImage],
        ['003r', ''],
    ]);
    assert.deepEqual(dom.previewedLinks(), [sharedImage, sharedImage, '']);
    assert.equal(dom.check('extraFolios').state, 'ok');
});

test('folios sharing one image are reported as facing folios, not as identical links', () => {
    const dom = installDOM(['001v', '002r', '002v', '003r']);
    const first = 'https://example.com/opening-1.jpg';
    const second = 'https://example.com/opening-2.jpg';
    csvLoadCallback([
        `001v,${first}`,
        `002r,${first}`,
        `002v,${second}`,
        `003r,${second}`,
    ].join('\n'));

    const result = dom.check('imageLinkDuplication');
    assert.equal(result.state, 'ok');
    assert.match(result.text, /2 image links shared by two folios each/);
    assert.doesNotMatch(result.text, /identical/);
});

test('one image for the whole source still reads as one shared link', () => {
    const dom = installDOM(['001r', '001v']);
    csvLoadCallback('001r,https://example.com/all.jpg\n001v,https://example.com/all.jpg');

    const result = dom.check('imageLinkDuplication');
    assert.equal(result.state, 'ok');
    assert.equal(result.text, 'All folios share one image link');
});

test('an image link shared by three folios is flagged', () => {
    const dom = installDOM(['001r', '001v', '002r', '002v', '003r']);
    const crowded = 'https://example.com/three.jpg';
    csvLoadCallback([
        `001r,${crowded}`,
        `001v,${crowded}`,
        `002r,${crowded}`,
        '002v,https://example.com/pair.jpg',
        '003r,https://example.com/pair.jpg',
    ].join('\n'));

    const result = dom.check('imageLinkDuplication');
    assert.equal(result.state, 'warning');
    assert.match(result.text, /001r, 001v, 002r/);
    // The ordinary pair is not part of the complaint.
    assert.doesNotMatch(result.text, /002v/);
});

test('unique image links pass the shared-link check', () => {
    const dom = installDOM(['001r', '001v']);
    csvLoadCallback('001r,https://example.com/1r\n001v,https://example.com/1v');

    assert.deepEqual(dom.check('imageLinkDuplication'), {
        state: 'ok',
        text: 'Every folio has its own image link',
    });
});

test('a folio listed twice is reported and both rows are submitted in file order', () => {
    const dom = installDOM(['001r']);
    csvLoadCallback('001r,https://example.com/first\n001r,https://example.com/second');

    assert.equal(dom.check('folioDuplication').state, 'warning');
    assert.match(dom.check('folioDuplication').text, /001r/);
    // The server applies the last row for a folio, so both must arrive in order.
    assert.deepEqual(dom.submittedLinks(), [
        ['001r', 'https://example.com/first'],
        ['001r', 'https://example.com/second'],
    ]);
});

test('folios the source does not have are previewed, submitted and flagged', () => {
    const dom = installDOM(['001r']);
    csvLoadCallback('folio,image_link\n001r,https://example.com/1r\n999v,https://example.com/999v');

    assert.equal(dom.check('extraFolios').state, 'warning');
    assert.match(dom.check('extraFolios').text, /999v/);
    // The submission matches the preview; the server drops folios that are
    // not this source's.
    assert.deepEqual(dom.submittedLinks(), [
        ['001r', 'https://example.com/1r'],
        ['999v', 'https://example.com/999v'],
    ]);
});

test('semicolon-delimited files parse, and quoted links keep their commas', () => {
    const dom = installDOM(['001r', '001v']);
    csvLoadCallback([
        'folio;image_link',
        '001r;"https://example.com/iiif/1/full/500,/0/default.jpg"',
        '001v;"https://example.com/iiif/2?size=500;region=full"',
    ].join('\n'));

    assert.deepEqual(dom.submittedLinks(), [
        ['001r', 'https://example.com/iiif/1/full/500,/0/default.jpg'],
        ['001v', 'https://example.com/iiif/2?size=500;region=full'],
    ]);
});

test('a source-sized file is carried in full', () => {
    // Tours 149 (source 123640) has 1044 folios, which is what broke the
    // previous one-field-per-folio form.
    const folios = [];
    for (let leaf = 1; leaf <= 522; leaf++) {
        const number = String(leaf).padStart(3, '0');
        folios.push(`${number}r`, `${number}v`);
    }
    const dom = installDOM(folios);
    const csv = ['folio,image_link']
        .concat(folios.map((folio) => `${folio},https://example.com/${folio}.jpg`))
        .join('\n');

    csvLoadCallback(csv);

    assert.equal(dom.submittedLinks().length, 1044);
    assert.equal(dom.check('folioCompleteness').state, 'ok');
    assert.deepEqual(dom.submittedLinks()[1043], ['522v', 'https://example.com/522v.jpg']);
});

test('checkSharedImageLinks ignores rows with no image link', () => {
    const result = checkSharedImageLinks([
        { folio: '001r', imageLink: '' },
        { folio: '001v', imageLink: '' },
        { folio: '002r', imageLink: 'https://example.com/2r.jpg' },
    ]);
    assert.deepEqual(result, { folios: [], success: 'Every folio has its own image link' });
});


test('file selection clears stale data and ignores a superseded file read', () => {
    const dom = installDOM(['001r', '001v']);
    const readers = [];
    global.FileReader = class {
        constructor() { readers.push(this); }
        readAsText(file) { this.file = file; }
    };
    initializeCSVImport();
    const change = dom.element('imgLinksCSV').listeners.change;
    const button = dom.element('imgLinkFormSubmitBtn');
    assert.equal(button.disabled, true);
    change({ target: { files: ['A.csv'] } });
    change({ target: { files: ['B.csv'] } });
    readers[1].onload({ target: { result: '001v,https://example.com/B' } });
    readers[0].onload({ target: { result: '001r,https://example.com/A' } });
    assert.deepEqual(dom.submittedLinks(), [['001v', 'https://example.com/B']]);
    assert.equal(button.disabled, false);

    change({ target: { files: ['broken.csv'] } });
    assert.deepEqual(dom.submittedLinks(), []);
    assert.equal(button.disabled, true);
    readers[2].onerror();
    assert.equal(dom.element('csvReadError').hidden, false);
    change({ target: { files: [] } });
    assert.deepEqual(dom.submittedLinks(), []);
    assert.equal(dom.element('csvPreviewDiv').hidden, true);
    assert.equal(button.disabled, true);
});

test('an empty replacement file cannot submit the previous links', () => {
    const dom = installDOM(['001r']);
    let reader;
    global.FileReader = class {
        constructor() { reader = this; }
        readAsText() { }
    };
    initializeCSVImport();
    csvLoadCallback('001r,https://example.com/old');
    dom.element('imgLinksCSV').listeners.change({ target: { files: ['empty.csv'] } });
    reader.onload({ target: { result: 'folio,image_link\n' } });
    assert.deepEqual(dom.submittedLinks(), []);
    assert.equal(dom.element('imgLinkFormSubmitBtn').disabled, true);
    assert.equal(dom.element('csvReadError').hidden, false);
});
