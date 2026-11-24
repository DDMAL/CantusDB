"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "../../django/cantusdb_project/static/js/search_bar.js"), "utf8");

// Run the global search bar's live suggestions with a stand-in search bar,
// results area and XMLHttpRequest, and record the URLs it requests.
function harness() {
    const searchBar = {
        value: "",
        listeners: {},
        addEventListener(type, callback) { this.listeners[type] = callback; },
    };
    const chantsDiv = { innerHTML: "previous results" };
    const requested = [];
    class FakeXMLHttpRequest {
        open(_method, url) { requested.push(new URL(url)); }
        send() {}
        abort() {}
    }
    const context = {
        window: {
            addEventListener: (_type, callback) => callback(),
            location: { origin: "http://localhost" },
        },
        document: { getElementById: id => ({ searchBar, chantsDiv })[id] },
        XMLHttpRequest: FakeXMLHttpRequest,
        URL,
        console,
    };
    vm.runInNewContext(source, context);
    const type = value => {
        searchBar.value = value;
        searchBar.listeners.input();
    };
    return { type, requested, chantsDiv };
}

test("live suggestions ignore leading and trailing spaces", () => {
    const { type, requested } = harness();
    type(" Alleluia ");
    assert.equal(requested.length, 1);
    assert.equal(requested[0].pathname, "/ajax/search-bar/Alleluia");
});

test("a search bar holding only spaces clears the suggestions without searching", () => {
    const { type, requested, chantsDiv } = harness();
    type("   ");
    assert.equal(requested.length, 0);
    assert.equal(chantsDiv.innerHTML, "");
});
