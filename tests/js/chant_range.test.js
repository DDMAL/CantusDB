"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const script = fs.readFileSync(path.join(__dirname, "../../django/cantusdb_project/static/js/chant_range.js"), "utf8");

function form(melody, range, disabled = false) {
    let input;
    const volpiano = { value: melody, addEventListener: (event, fn) => { input = fn; } };
    const chantRange = { value: range, disabled };
    const note = { hidden: true };
    const elements = { id_volpiano: volpiano, id_chant_range: chantRange, chantRangeDerivedNote: note };
    vm.runInNewContext(script, {
        window: { addEventListener: (event, fn) => fn() },
        document: { getElementById: id => elements[id] },
    });
    return { chantRange, note, type: value => { volpiano.value = value; input(); } };
}

test("adding a melody disables a manual range and clearing it restores the value", () => {
    const page = form("", "1-c-g-4");
    assert.equal(page.chantRange.disabled, false);
    page.type("1---d--h---4");
    assert.equal(page.chantRange.disabled, true);
    assert.equal(page.note.hidden, false);
    page.type("   ");
    assert.equal(page.chantRange.disabled, false);
    assert.equal(page.chantRange.value, "1-c-g-4");
    assert.equal(page.note.hidden, true);
});

test("an existing melody can be cleared to enter a manual range in the same edit", () => {
    const page = form("1---c--g---4", "1-c-g-4", true);
    page.type("");
    assert.equal(page.chantRange.disabled, false);
    assert.equal(page.note.hidden, true);
    page.type("2---d--h---4");
    assert.equal(page.chantRange.disabled, true);
});
