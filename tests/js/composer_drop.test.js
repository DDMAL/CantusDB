"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

// Exercise the shipped geometry calculation with fixture rectangles, without a DOM
// dependency. Local browser checks separately verify layout, drag events and persistence.
const source = fs.readFileSync(
    path.join(__dirname, "../../django/cantusdb_project/static/js/chant_create_clusters.js"),
    "utf8"
);
const window = {};
new Function("window", "getComputedStyle", source)(window, (token) => token.style);
const { insertionPoints, nearestPoint } = window.ChantClusterComposer;

const rect = (left, right, top) => ({ left, right, top, height: 20 });
function token(text, rects, marginLeft = "0px", marginRight = "0px") {
    return {
        text,
        style: { marginLeft, marginRight },
        getClientRects: () => rects,
        getBoundingClientRect: () => {
            throw new Error("A wrapped token must use its individual line fragments");
        },
    };
}

function drop(tokens, x, y) {
    const point = nearestPoint(insertionPoints(tokens), x, y);
    const at = point && point.token ? tokens.indexOf(point.token) : tokens.length;
    const order = tokens.map((t) => t.text);
    order.splice(at, 0, "component");
    return { point, order };
}

describe("composer drop positions", () => {
    const alpha = token("Alpha", [rect(10, 90, 0)]);
    const beta = token("Beta", [rect(100, 180, 0)]);
    const gamma = token("Gamma", [rect(10, 120, 30)]);
    const wrapped = [alpha, beta, gamma];

    it("inserts after the last element on a line when dropping to its right", () => {
        const { point, order } = drop(wrapped, 210, 10);
        assert.deepEqual(order, ["Alpha", "Beta", "component", "Gamma"]);
        assert.equal(point.top, 0);
        assert.equal(point.x, 180);
    });

    it("reaches the same gap from the start of the next line", () => {
        const { point, order } = drop(wrapped, 5, 40);
        assert.deepEqual(order, ["Alpha", "Beta", "component", "Gamma"]);
        assert.equal(point.top, 30);
    });

    it("keeps ordinary gaps at their midpoint", () => {
        const { point, order } = drop(wrapped, 95, 10);
        assert.deepEqual(order, ["Alpha", "component", "Beta", "Gamma"]);
        assert.equal(point.x, 95);
        assert.equal(insertionPoints([alpha, beta]).length, 3);
    });

    it("allows insertion before the first and after the last element", () => {
        assert.deepEqual(drop(wrapped, 0, 10).order, ["component", "Alpha", "Beta", "Gamma"]);
        assert.deepEqual(drop(wrapped, 140, 40).order, ["Alpha", "Beta", "Gamma", "component"]);
    });

    it("uses the last fragment of a wrapped element for the end-of-line gap", () => {
        const long = token("Long", [rect(100, 280, 0), rect(10, 160, 30)]);
        const next = token("Next", [rect(10, 80, 60)]);
        const { point, order } = drop([alpha, long, next], 180, 40);
        assert.deepEqual(order, ["Alpha", "Long", "component", "Next"]);
        assert.equal(point.top, 30);
        assert.equal(point.x, 160);
        assert.deepEqual(drop([alpha, long, next], 95, 10).order, [
            "Alpha", "component", "Long", "Next",
        ]);
    });

    it("keeps the gap on one line when the previous element wraps onto it", () => {
        const long = token("Long", [rect(10, 280, 0), rect(10, 160, 30)]);
        const next = token("Next", [rect(170, 250, 30)]);
        const { point, order } = drop([long, next], 165, 40);
        assert.deepEqual(order, ["Long", "component", "Next"]);
        assert.equal(point.x, 165);
        assert.equal(insertionPoints([long, next]).length, 3);
    });

    it("includes the previous element's margin at the end of a wrapped line", () => {
        const padded = token("Padded", [rect(100, 180, 0)], "2px", "6px");
        const { point, order } = drop([alpha, padded, gamma], 210, 10);
        assert.deepEqual(order, ["Alpha", "Padded", "component", "Gamma"]);
        assert.equal(point.x, 186);
    });

    it("handles empty and single-element composers", () => {
        assert.deepEqual(drop([], 10, 10), { point: null, order: ["component"] });
        assert.deepEqual(drop([alpha], 0, 10).order, ["component", "Alpha"]);
        assert.deepEqual(drop([alpha], 100, 10).order, ["Alpha", "component"]);
    });
});
