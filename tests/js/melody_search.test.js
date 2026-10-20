"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "../../django/cantusdb_project/static/js/melody_search.js"), "utf8");

function element() {
    let content = "";
    return {
        value: "", style: {}, children: [], listeners: {}, parentElement: { addEventListener() {} },
        get innerHTML() { return content; },
        set innerHTML(value) { content = value; this.children = []; },
        get textContent() { return content; },
        set textContent(value) { content = value; this.children = []; },
        getBoundingClientRect() { return { left: 0, right: 500, top: 0, bottom: 150 }; },
        addEventListener(type, callback) { this.listeners[type] = callback; },
        fire(type, event = {}) { this.listeners[type]?.(event); },
        appendChild(child) { this.children.push(child); },
    };
}

function harness() {
    const ids = new Map();
    const byId = id => {
        if (!ids.has(id)) ids.set(id, element());
        return ids.get(id);
    };
    const rows = [];
    byId("resultsTable").getElementsByTagName = () => [{
        rows,
        insertRow() { const row = { innerHTML: "" }; rows.push(row); return row; },
    }];
    const requests = [];
    const context = {
        window: {
            addEventListener(type, callback) { if (type === "load") callback(); },
            location: { origin: "http://localhost", search: "?source=17" },
        },
        document: { getElementById: byId, body: element(), createElement: element },
        URL, URLSearchParams,
        XMLHttpRequest: class {
            open(_method, url) { this.url = url; }
            send() { requests.push(this); }
            abort() { this.aborted = true; }
            respond(status, response) { this.status = status; this.response = response; this.onload(); }
        },
        setTimeout() { throw new Error("Search must not retry automatically"); },
    };
    vm.runInNewContext(source, context);
    return {
        byId, rows, requests,
        note: pageY => byId("drawArea").fire("click", { pageY }),
        get prompt() { return byId("searchingPrompt").style.display; },
        get result() { return byId("resultsDiv"); },
    };
}

test("a busy melody search shows a message, stops loading and retries only on a click", () => {
    const h = harness();
    h.note(85);
    assert.equal(h.prompt, "inline");
    h.requests[0].respond(429, "Search is busy.\n");
    assert.match(h.result.textContent, /Search is busy/);
    assert.equal(h.prompt, "none");
    assert.equal(h.requests.length, 1);
    const retry = h.result.children[0];
    assert.equal(retry.textContent, "Try again");
    retry.fire("click");
    assert.equal(h.requests.length, 2);
    assert.equal(h.requests[1].url.href, h.requests[0].url.href);
    assert.equal(h.requests[1].url.searchParams.get("source"), "17");
    h.requests[1].respond(200, '{"result_count":0,"results":[]}');
    assert.match(h.result.innerHTML, /0 melodies/);
    assert.equal(h.result.children.length, 0);
    assert.equal(h.prompt, "none");
});

test("server, malformed and network responses stop loading and offer a manual retry", () => {
    for (const failure of ["server", "json", "network"]) {
        const h = harness();
        h.note(85);
        if (failure === "server") h.requests[0].respond(504, "<html>Gateway timeout</html>");
        if (failure === "json") h.requests[0].respond(200, "<html>Unexpected response</html>");
        if (failure === "network") h.requests[0].onerror();
        assert.match(h.result.textContent, /could not finish/);
        assert.equal(h.prompt, "none");
        assert.equal(h.result.children[0].textContent, "Try again");
        assert.equal(h.requests.length, 1);
    }
});

test("new notes immediately abort the old request and keep the newest search in control", () => {
    const h = harness();
    h.note(85);
    h.note(95);
    assert.equal(h.requests[0].aborted, true);
    assert.equal(h.requests.length, 2);
    assert.equal(h.requests[1].url.searchParams.get("notes"), "gf");
    h.requests[0].respond(429, "Search is busy");
    h.requests[0].onerror();
    assert.equal(h.result.textContent, "");
    assert.equal(h.prompt, "inline");
    h.requests[1].respond(200, JSON.stringify({
        result_count: 1,
        results: [{ computed_siglum: "CD", folio: "1r", genre__name: "Antiphon", mode: "1",
            chant_link: "/chant/123/", incipit: "Alleluia", volpiano: "1---g-f---4", feast__name: "Test" }],
    }));
    assert.match(h.result.innerHTML, /1 melodies/);
    assert.match(h.rows[0].innerHTML, /Alleluia/);
    assert.equal(h.prompt, "none");
});

test("clearing the melody aborts the search and removes its results or retry button", () => {
    const h = harness();
    h.note(85);
    h.byId("deleteAll").fire("click");
    assert.equal(h.requests[0].aborted, true);
    assert.equal(h.result.textContent, "");
    assert.equal(h.prompt, "none");
    h.byId("textSearch").fire("input");
    assert.equal(h.requests.length, 1);
    h.note(85);
    h.requests[1].respond(429, "Search is busy");
    h.byId("deleteOne").fire("click");
    assert.equal(h.result.textContent, "");
    assert.equal(h.result.children.length, 0);
});
