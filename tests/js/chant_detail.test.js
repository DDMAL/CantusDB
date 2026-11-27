"use strict";

// The melodies and concordances tables on the chant page add values from our
// database and from Cantus Index as text, never as HTML, and only link to
// http(s) addresses (#2384). The script runs against a small stand-in DOM
// whose innerHTML throws, so any use of it in these paths fails the test.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
    path.join(__dirname, "../../django/cantusdb_project/static/js/chant_detail.js"),
    "utf8",
);

const escape = text =>
    text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

class TextNode {
    constructor(text) {
        this.text = text;
    }
    get textContent() {
        return this.text;
    }
    toHTML() {
        return escape(this.text);
    }
}

class Element {
    constructor(tag) {
        this.tagName = tag.toLowerCase();
        this.children = [];
        this.attributes = {};
        this.classes = [];
        this.classList = { add: (...names) => this.classes.push(...names) };
    }
    appendChild(child) {
        this.children.push(child);
        return child;
    }
    setAttribute(name, value) {
        this.attributes[name] = String(value);
    }
    get textContent() {
        return this.children.map(child => child.textContent).join("");
    }
    set textContent(value) {
        this.children = value ? [new TextNode(String(value))] : [];
    }
    set innerHTML(value) {
        throw new Error(`innerHTML used with: ${value}`);
    }
    toHTML() {
        const attrs = Object.entries(this.attributes)
            .map(([name, value]) => ` ${name}="${value}"`)
            .join("");
        const classes = this.classes.length ? ` class="${this.classes.join(" ")}"` : "";
        const inner = this.children.map(child => child.toHTML()).join("");
        return `<${this.tagName}${attrs}${classes}>${inner}</${this.tagName}>`;
    }
}

function load() {
    const context = {
        window: { location: { origin: "https://cantusdatabase.org" } },
        document: {
            createElement: tag => new Element(tag),
            createTextNode: text => new TextNode(text),
        },
        URL,
        encodeURIComponent,
    };
    vm.runInNewContext(source, context);
    return context;
}

const MARKUP = '<img src="x" onerror="probe()">';

test("melody rows show database values as text", () => {
    const { melodyRow } = load();
    const row = melodyRow({
        siglum: MARKUP,
        source_link: "/source/123",
        folio: MARKUP,
        service__name: MARKUP,
        genre__name: MARKUP,
        position: MARKUP,
        feast__name: MARKUP,
        cantus_id: MARKUP,
        ci_link: "https://cantusindex.org/id/001234",
        volpiano: MARKUP,
        mode: MARKUP,
        manuscript_full_text_std_spelling: MARKUP,
        chant_link: "/chant/456",
    });
    const html = row.toHTML();
    assert.ok(!html.includes("<img"), html);
    assert.ok(html.includes("&lt;img"));
    assert.ok(html.includes('href="https://cantusdatabase.org/source/123"'));
    assert.ok(html.includes('href="https://cantusdatabase.org/chant/456"'));
    assert.ok(html.includes('href="https://cantusindex.org/id/001234"'));
});

test("melody rows don't link to unsafe addresses", () => {
    const { melodyRow } = load();
    const html = melodyRow({
        siglum: "A-Wn 1799",
        source_link: "javascript:probe()",
        cantus_id: "001234",
        ci_link: "javascript:probe()",
        manuscript_full_text_std_spelling: "Ave",
        chant_link: "javascript:probe()",
    }).toHTML();
    assert.ok(!html.includes("javascript:"), html);
    assert.ok(html.includes("<span>A-Wn 1799</span>"));
});

test("concordance rows show Cantus Index values as text", () => {
    const { concordanceRow } = load();
    const row = concordanceRow({
        siglum: MARKUP,
        srclink: "https://example.org/source/1",
        folio: MARKUP,
        image: "https://example.org/image.jpg",
        incipit: MARKUP,
        chantlink: "https://example.org/chant/1",
        office: MARKUP,
        genre: "A",
        position: null,
        feast: MARKUP,
        mode: MARKUP,
        db: MARKUP,
    });
    const html = row.toHTML();
    assert.ok(!html.includes("<img"), html);
    assert.ok(html.includes('href="https://example.org/source/1"'));
    assert.ok(html.includes('href="https://example.org/chant/1"'));
    assert.ok(html.includes('class="bi-camera-fill"'));
    assert.ok(!html.includes("null"), "missing values are left blank");
});

test("concordance rows drop unsafe and invalid links", () => {
    const { concordanceRow } = load();
    const html = concordanceRow({
        siglum: "CH-SGs 390",
        srclink: "javascript:probe()",
        folio: "12r",
        image: "0",
        incipit: "Ave",
        chantlink: "data:text/html,probe",
    }).toHTML();
    assert.ok(!html.includes("javascript:"), html);
    assert.ok(!html.includes("data:"), html);
    assert.ok(!html.includes("bi-camera-fill"), "no image link for an invalid address");
});

test("safeHref accepts only http(s) addresses", () => {
    const { safeHref } = load();
    assert.equal(safeHref("https://example.org/a"), "https://example.org/a");
    assert.equal(safeHref("http://example.org/a"), "http://example.org/a");
    assert.equal(safeHref("javascript:probe()"), "");
    assert.equal(safeHref("0"), "", "relative links from Cantus Index are refused");
    assert.equal(safeHref("/chant/1", true), "https://cantusdatabase.org/chant/1");
    assert.equal(safeHref(null), "");
});

test("the melodies table is built without innerHTML", () => {
    const { renderMelodies } = load();
    const div = new Element("div");
    renderMelodies(div, {
        concordance_count: 1,
        concordances: [{ siglum: "A", cantus_id: "001234", volpiano: "1---a" }],
    });
    const html = div.toHTML();
    assert.ok(html.startsWith("<div>Displaying <b>1</b> melodies"), html);
    assert.ok(html.includes("<table"), html);
});
