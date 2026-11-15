"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
    path.join(__dirname, "../../django/cantusdb_project/static/js/chant_edit.js"),
    "utf8",
);

// Run the shipped script against a small DOM: a proofread box and the fields
// it locks. `form` lists the inputs in the order the browser would submit them.
function harness({ checked, disabled, readOnly = false }) {
    const form = [];
    function element(props) {
        const listeners = {};
        return {
            listeners,
            addEventListener(type, callback) {
                (listeners[type] = listeners[type] || []).push(callback);
            },
            dispatchEvent(event) {
                (listeners[event.type] || []).forEach(callback => callback(event));
            },
            after(node) {
                form.splice(form.indexOf(this) + 1, 0, node);
            },
            remove() {
                form.splice(form.indexOf(this), 1);
            },
            ...props,
        };
    }

    const checkbox = element({ id: "id_volpiano_proofread", checked, disabled: readOnly });
    const volpiano = element({ id: "id_volpiano", name: "volpiano", value: "1-a-3", disabled });
    const range = element({ id: "id_chant_range", name: "chant_range", value: "a", disabled });
    form.push(checkbox, volpiano, range);

    const elements = {
        feastSelect: element({}),
        folioSelect: element({}),
        id_project: element({ options: [{ text: "" }], selectedIndex: 0 }),
        "benedicamus-domino-project-fields": element({}),
        "proofread-locks": {
            textContent: JSON.stringify({
                id_volpiano_proofread: ["id_volpiano", "id_chant_range"],
            }),
        },
    };
    for (const el of form) {
        elements[el.id] = el;
    }
    const window = element({ location: { search: "", href: "http://localhost/" } });
    vm.runInNewContext(source, {
        window,
        document: {
            getElementById: id => elements[id] || null,
            createElement: () => element({}),
        },
        URL,
        URLSearchParams,
        Event: class {
            constructor(type) {
                this.type = type;
            }
        },
    });
    window.dispatchEvent({ type: "load" });

    return {
        checkbox,
        volpiano,
        range,
        toggle(value) {
            checkbox.checked = value;
            checkbox.dispatchEvent({ type: "change" });
        },
        // what the browser would submit for the box's fields
        submitted() {
            return form
                .filter(el => el !== checkbox && el.name && !el.disabled)
                .map(el => [el.name, el.value]);
        },
    };
}

test("a page loaded with the box ticked submits none of its locked fields", () => {
    // the server keeps the saved value of a field left out
    const h = harness({ checked: true, disabled: true });
    assert.equal(h.volpiano.disabled, true);
    assert.deepEqual(h.submitted(), []);
});

test("ticking the box again locks an edited field and still submits the edit", () => {
    const h = harness({ checked: true, disabled: true });
    h.toggle(false);
    assert.equal(h.volpiano.disabled, false);
    h.volpiano.value = "1-b-3";
    h.toggle(true);
    assert.equal(h.volpiano.disabled, true, "no more typing once ticked");
    assert.deepEqual(h.submitted(), [["volpiano", "1-b-3"], ["chant_range", "a"]]);
});

test("unticking again submits the field itself, once", () => {
    const h = harness({ checked: true, disabled: true });
    h.toggle(false);
    h.volpiano.value = "1-b-3";
    h.toggle(true);
    h.toggle(false);
    assert.deepEqual(h.submitted(), [["volpiano", "1-b-3"], ["chant_range", "a"]]);
    h.volpiano.value = "1-c-3";
    h.toggle(true);
    assert.deepEqual(h.submitted(), [["volpiano", "1-c-3"], ["chant_range", "a"]]);
});

test("ticking a box submits the values the proofreader approved, even unchanged ones", () => {
    // If someone saved a different melody since this page loaded, leaving the
    // field out would mark their unreviewed melody as proofread.
    const h = harness({ checked: false, disabled: false });
    h.toggle(true);
    assert.equal(h.volpiano.disabled, true);
    assert.equal(h.range.disabled, true);
    assert.deepEqual(h.submitted(), [["volpiano", "1-a-3"], ["chant_range", "a"]]);
});

test("a page shown again after a failed save keeps the unsaved edit", () => {
    // The proofreader's edit came back in an unlocked field under a ticked box.
    const h = harness({ checked: true, disabled: false });
    assert.equal(h.volpiano.disabled, true, "locked again on load");
    assert.deepEqual(h.submitted(), [["volpiano", "1-a-3"], ["chant_range", "a"]]);
    h.toggle(false);
    h.toggle(true);
    assert.deepEqual(h.submitted(), [["volpiano", "1-a-3"], ["chant_range", "a"]]);
});

test("a read-only box (not a proofreader) is left alone", () => {
    const h = harness({ checked: true, disabled: true, readOnly: true });
    assert.equal(h.checkbox.listeners.change, undefined);
    assert.equal(h.volpiano.disabled, true);
    assert.deepEqual(h.submitted(), []);
});
