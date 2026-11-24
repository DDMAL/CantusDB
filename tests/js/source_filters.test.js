"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
    path.join(__dirname, "../../django/cantusdb_project/static/js/source_filters.js"),
    "utf8",
);

function element(props = {}) {
    const listeners = {};
    return {
        listeners,
        style: {},
        addEventListener(type, callback) { listeners[type] = callback; },
        fire(type) { listeners[type](); },
        ...props,
    };
}

// Run the shipped script against the given elements and query string.
function run(search, elements = {}, boxes = []) {
    vm.runInNewContext(source, {
        window: {
            location: { search },
            addEventListener: (_type, callback) => callback(),
        },
        document: {
            getElementById: id => elements[id] || null,
            querySelectorAll: () => boxes,
        },
        URLSearchParams,
    });
}

function slider() {
    return {
        dateStartFilter: element({ min: "800", max: "1900", value: "800" }),
        dateEndFilter: element({ min: "800", max: "1900", value: "1900" }),
        rangeSliderFill: element(),
        rangeStartInput: element({ value: "800" }),
        rangeEndInput: element({ value: "1900" }),
        rangeResetBtn: element(),
    };
}

test("restores the chosen source filters from the URL", () => {
    const elements = {
        countryFilter: element({ value: "" }),
        provenanceFilter: element({ value: "" }),
        prodMethodFilter: element({ value: "" }),
    };
    const boxes = ["1", "4", "2", "3", "5"].map(value => element({ value, checked: true }));
    run("?country=Spain&provenance=12&prodMethod=1&sourceCompleteness=2&sourceCompleteness=5", elements, boxes);
    assert.equal(elements.countryFilter.value, "Spain");
    assert.equal(elements.provenanceFilter.value, "12");
    assert.equal(elements.prodMethodFilter.value, "1");
    // status 5 used to be skipped by a loop that stopped at 4
    assert.deepEqual(boxes.map(box => [box.value, box.checked]), [
        ["1", false], ["4", false], ["2", true], ["3", false], ["5", true],
    ]);
});

test("leaves the fields alone without matching parameters", () => {
    const elements = { countryFilter: element({ value: "" }) };
    const boxes = ["1", "2"].map(value => element({ value, checked: true }));
    run("?keyword=Ave", elements, boxes);
    assert.equal(elements.countryFilter.value, "");
    assert.ok(boxes.every(box => box.checked));
});

test("runs on a page without the source filters", () => {
    assert.doesNotThrow(() => run("?country=Spain&dateStart=1000"));
});

test("the year slider keeps the inputs, fill and reset in step", () => {
    const elements = slider();
    run("", elements);
    elements.dateStartFilter.value = "1000";
    elements.dateStartFilter.fire("input");
    assert.equal(elements.rangeStartInput.value, 1000);
    assert.equal(elements.rangeSliderFill.style.left, `${(200 / 1100) * 100}%`);
    elements.rangeEndInput.value = "1010";
    elements.rangeEndInput.fire("change");
    assert.equal(elements.rangeEndInput.value, 1025, "kept 25 years apart");
    elements.rangeResetBtn.fire("click");
    assert.equal(elements.dateStartFilter.value, 800);
    assert.equal(elements.dateEndFilter.value, 1900);
});
