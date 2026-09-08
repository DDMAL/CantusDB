/*
 * Tests for the chant cluster composer's submit-time guards (#2165, review follow-up).
 *
 * The composer is a DOM-heavy browser script and most of it can only be verified by hand,
 * but the decision behind the submit guards is pure: given how many element tokens the
 * composer holds and whether any auto-split separators are still in it, should the save be
 * blocked, and with which message. That decision lives in `clusterSubmissionError`, hung on
 * `window.ChantClusterComposer` exactly as chant_create_auto_split.js exposes its rules, so
 * it runs here under Node with no browser and no DOM.
 *
 * What these pin: an empty composer is blocked (its native `required` is dropped while
 * composing, so without this the save would fail silently on a hidden field), and leftover
 * separators are blocked (they would otherwise be saved as elements, with their bare pipes
 * ending up in the full text). Both were reported on the PR; these keep the regressions out.
 */

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const COMPOSER_PATH = path.join(
    __dirname,
    "..",
    "..",
    "django",
    "cantusdb_project",
    "static",
    "js",
    "chant_create_clusters.js"
);

// The composer hangs its testable API on `window`. Its DOMContentLoaded hook is guarded on
// `document`, so evaluating the file against a stub window (no document) runs it exactly as
// the browser would minus the wiring, and leaves the pure API to read off.
function loadComposer() {
    const source = fs.readFileSync(COMPOSER_PATH, "utf8");
    const window = {};
    new Function("window", source)(window);
    return window.ChantClusterComposer;
}

const { submissionError } = loadComposer();

describe("cluster submit validation", () => {
    it("blocks an empty composer", () => {
        const result = submissionError(0, false);
        assert.equal(result.reason, "empty");
        assert.match(result.message, /at least one element/);
    });

    it("treats an empty composer as empty even if a separator flag is set", () => {
        // tokenCount 0 can't really carry a separator, but the empty check must win
        // regardless so the message names the real problem.
        assert.equal(submissionError(0, true).reason, "empty");
    });

    it("blocks leftover auto-split separators", () => {
        const result = submissionError(3, true);
        assert.equal(result.reason, "separators");
        assert.match(result.message, /Remove the split separators/);
    });

    it("allows a cluster with elements and no separators", () => {
        const result = submissionError(3, false);
        assert.equal(result.reason, "");
        assert.equal(result.message, "");
    });
});
