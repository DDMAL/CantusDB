"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
    path.join(__dirname, "../../django/cantusdb_project/static/js/filter_form_autosubmit.js"),
    "utf8",
);

// Exercise the shipped script with a small DOM and a manual clock. Real
// browser focus, pointer and dropdown behaviour is checked by hand.
function target() {
    const listeners = {};
    return {
        listeners,
        addEventListener(type, callback) {
            (listeners[type] = listeners[type] || []).push(callback);
        },
        dispatch(type, event = {}) {
            (listeners[type] || []).forEach(callback => callback(event));
        },
    };
}

function harness({ companionValue = "x" } = {}) {
    const form = target();
    const window = target();
    const document = target();
    let now = 0;
    let nextId = 1;
    let timers = [];
    const submissions = [];

    function control(tagName, props) {
        return {
            tagName,
            dataset: {},
            matches(selector) {
                return selector.split(",").some(part => {
                    part = part.trim();
                    return part === tagName.toLowerCase()
                        || (part === 'input[type="radio"]' && tagName === "INPUT" && this.type === "radio");
                });
            },
            closest(selector) {
                return selector === "select" && tagName === "SELECT" ? this : null;
            },
            ...props,
        };
    }

    const radios = ["all", "inventoried", "nonInventoried"].map(value =>
        control("INPUT", { type: "radio", name: "inventoried", value, checked: value === "all" }));
    const country = control("SELECT", { value: "" });
    const operator = control("SELECT", { value: "contains" });
    operator.dataset.autosubmitRequires = "#keyword";
    const keyword = control("INPUT", { type: "text", value: companionValue });
    const label = { tagName: "LABEL", closest: () => null };

    form.elements = [...radios, country, operator, keyword];
    form.querySelector = selector => (selector === "#keyword" ? keyword : null);
    form.requestSubmit = () => submissions.push({
        inventoried: radios.find(radio => radio.checked).value,
        country: country.value,
    });

    const context = {
        window,
        document: Object.assign(document, {
            querySelectorAll: () => [form],
        }),
        setTimeout(callback, delay = 0) {
            const id = nextId++;
            timers.push({ id, callback, at: now + delay });
            return id;
        },
        clearTimeout(id) {
            timers = timers.filter(timer => timer.id !== id);
        },
    };
    vm.runInNewContext(source, context);
    window.dispatch("load");

    const h = {
        form, radios, country, operator, keyword, label, submissions, document, window,
        advance(ms) {
            now += ms;
            let due;
            while ((due = timers.filter(timer => timer.at <= now).sort((a, b) => a.at - b.at)[0])) {
                timers = timers.filter(timer => timer !== due);
                due.callback();
            }
        },
        // A key press whose default action changes `changed` (if given).
        press(key, changed, apply) {
            let prevented = false;
            form.dispatch("keydown", { key, preventDefault: () => { prevented = true; } });
            if (!prevented && changed) {
                apply();
                form.dispatch("change", { target: changed });
            }
            h.advance(0);
            return prevented;
        },
        selectRadio(value) {
            radios.forEach(radio => { radio.checked = radio.value === value; });
            return radios.find(radio => radio.value === value);
        },
        // A mouse click whose default action (if any) changes `changed`.
        click(on, changed, apply) {
            form.dispatch("pointerdown", { target: on });
            form.dispatch("focusout", {});
            document.dispatch("pointerup", {});
            if (changed) {
                apply();
                form.dispatch("change", { target: changed });
            }
            h.advance(0);
        },
    };
    return h;
}

test("a mouse choice submits immediately, once", () => {
    const h = harness();
    h.click(h.radios[1], h.radios[1], () => h.selectRadio("inventoried"));
    assert.deepEqual(h.submissions, [{ inventoried: "inventoried", country: "" }]);
    h.form.dispatch("change", { target: h.country });
    assert.equal(h.submissions.length, 1);
});

test("arrow keys wait for the keyboard to settle", () => {
    const h = harness();
    h.press("ArrowRight", h.radios[1], () => h.selectRadio("inventoried"));
    h.advance(900);
    h.press("ArrowRight", h.radios[2], () => h.selectRadio("nonInventoried"));
    h.advance(900);
    assert.equal(h.submissions.length, 0);
    h.advance(100);
    assert.deepEqual(h.submissions, [{ inventoried: "nonInventoried", country: "" }]);
});

test("dropdown type-ahead waits until typing stops", () => {
    const h = harness();
    for (const [key, value] of [["c", "Canada"], ["z", "Czechia"]]) {
        h.press(key, h.country, () => { h.country.value = value; });
        h.advance(500);
    }
    assert.equal(h.submissions.length, 0);
    h.advance(500);
    assert.deepEqual(h.submissions, [{ inventoried: "all", country: "Czechia" }]);
});

test("Enter applies a pending keyboard choice at once", () => {
    const h = harness();
    h.press("ArrowDown", h.country, () => { h.country.value = "Canada"; });
    assert.equal(h.press("Enter"), true);
    assert.deepEqual(h.submissions, [{ inventoried: "all", country: "Canada" }]);
    h.advance(2000);
    assert.equal(h.submissions.length, 1);
});

test("confirming an option in an open dropdown list submits immediately", () => {
    const h = harness();
    // Alt+Down opens the list; the keys used inside it don't reach the page,
    // so the change that confirms the option arrives with no key pending.
    h.press("ArrowDown");
    h.country.value = "France";
    h.form.dispatch("change", { target: h.country });
    assert.deepEqual(h.submissions, [{ inventoried: "all", country: "France" }]);
});

test("clicking another radio's label submits the clicked option", () => {
    const h = harness();
    h.press("ArrowRight", h.radios[1], () => h.selectRadio("inventoried"));
    h.click(h.label, h.radios[2], () => h.selectRadio("nonInventoried"));
    assert.deepEqual(h.submissions, [{ inventoried: "nonInventoried", country: "" }]);
    h.advance(2000);
    assert.equal(h.submissions.length, 1);
});

test("a click that changes nothing applies the pending choice", () => {
    const h = harness();
    h.press("ArrowRight", h.radios[1], () => h.selectRadio("inventoried"));
    h.click(h.label);
    assert.deepEqual(h.submissions, [{ inventoried: "inventoried", country: "" }]);
});

test("a key pressed just after a click still waits to settle", () => {
    const h = harness();
    // Browsers can deliver the key before the click's follow-up timer runs.
    h.form.dispatch("pointerdown", { target: h.radios[0] });
    h.document.dispatch("pointerup", {});
    h.form.dispatch("keydown", { key: "ArrowRight", preventDefault() {} });
    h.selectRadio("inventoried");
    h.form.dispatch("change", { target: h.radios[1] });
    h.advance(0);
    assert.equal(h.submissions.length, 0);
    h.advance(1000);
    assert.deepEqual(h.submissions, [{ inventoried: "inventoried", country: "" }]);
});

test("opening a dropdown with the mouse keeps a pending choice waiting", () => {
    const h = harness();
    h.press("ArrowDown", h.country, () => { h.country.value = "Canada"; });
    h.click(h.country);
    h.advance(2000);
    assert.equal(h.submissions.length, 0);
    h.form.dispatch("focusout", {});
    assert.deepEqual(h.submissions, [{ inventoried: "all", country: "Canada" }]);
});

test("leaving the control applies a pending choice", () => {
    const h = harness();
    h.press("ArrowRight", h.radios[1], () => h.selectRadio("inventoried"));
    h.form.dispatch("focusout", {});
    assert.equal(h.submissions.length, 1);
});

test("arrow keys across a radio group keep waiting while focus moves", () => {
    const h = harness();
    // An arrow key moves focus to the next radio, then checks it.
    function arrowTo(from, to) {
        h.form.dispatch("keydown", { key: "ArrowRight", preventDefault() {} });
        h.form.dispatch("focusout", { target: from, relatedTarget: to });
        h.selectRadio(to.value);
        h.form.dispatch("change", { target: to });
        h.advance(0);
    }
    arrowTo(h.radios[0], h.radios[1]);
    arrowTo(h.radios[1], h.radios[2]);
    assert.equal(h.submissions.length, 0);
    h.advance(1000);
    assert.deepEqual(h.submissions, [{ inventoried: "nonInventoried", country: "" }]);
});

test("leaving the radio group applies the pending choice", () => {
    const h = harness();
    h.press("ArrowRight", h.radios[1], () => h.selectRadio("inventoried"));
    h.form.dispatch("focusout", { target: h.radios[1], relatedTarget: h.country });
    assert.deepEqual(h.submissions, [{ inventoried: "inventoried", country: "" }]);
});

test("an operator waits for its search field", () => {
    const h = harness({ companionValue: "  " });
    h.operator.value = "starts_with";
    h.form.dispatch("change", { target: h.operator });
    assert.equal(h.submissions.length, 0);
    h.keyword.value = "Deus";
    h.form.dispatch("change", { target: h.operator });
    assert.equal(h.submissions.length, 1);
});

test("Back restores the loaded values and allows filtering again", () => {
    const h = harness();
    h.click(h.country, h.country, () => { h.country.value = "Canada"; });
    assert.equal(h.submissions.length, 1);
    h.window.dispatch("pageshow", { persisted: true });
    assert.equal(h.country.value, "");
    assert.equal(h.radios[0].checked, true);
    assert.equal(h.submissions.length, 1, "restoring must not submit");
    h.click(h.country, h.country, () => { h.country.value = "Canada"; });
    assert.equal(h.submissions.length, 2);
});

test("an ordinary page show leaves the form alone", () => {
    const h = harness();
    h.country.value = "Canada";
    h.window.dispatch("pageshow", { persisted: false });
    assert.equal(h.country.value, "Canada");
});
