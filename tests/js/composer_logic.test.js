/*
 * Tests for the chant cluster composer's pure decision logic (#2165, review follow-up).
 *
 * chant_create_clusters.js is a ~2,500-line DOM- and caret-heavy browser script, and the
 * plumbing around it — drag/drop, the caret bookkeeping, the floating menus, the typeahead
 * wiring — can only be verified in a real browser (the local .e2e/ Playwright harness does
 * that, and hand testing). But underneath that plumbing sit the decisions the composer keeps
 * making — how to rank Cantus Index results, which runs of elements may merge, where a split
 * falls, what JSON the server receives, which drop gap is nearest a pointer — and those are
 * pure over plain data. They are hung on `window.ChantClusterComposer` exactly as
 * chant_create_auto_split.js hangs its split rules on `window.ChantAutoSplit`, so they run
 * here under Node with no browser and no DOM.
 *
 * What these pin is the behaviour a cataloguer would notice if it regressed: an in-cluster
 * trope surfacing above unrelated matches, a "N more matches" line, a merge that should have
 * refused, a saved payload that lost a proposed flag or a Cantus ID, a drop bar jumping to
 * the wrong line. The DOM wrappers that call these (rankResults ← the typeahead, mergeTokens
 * ← the merge menu, serializeElements ← the hidden field, nearestPoint ← the drag handler)
 * are thin by construction, so pinning the core pins most of what can actually go wrong.
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

const api = loadComposer();
const {
    plural,
    ciEndpoint,
    rankResults,
    rowsFromResults,
    ciErrorRows,
    messageRowText,
    isNavigable,
    canSplitText,
    splitWords,
    mergeKindMatches,
    joinElementTexts,
    serializeElements,
    nearestPoint,
} = api;

// Small builders so the intent of each case reads clearly. A "descriptor" is the plain-object
// snapshot of a token the composer's pure logic runs over: {kind, text, cantusId, proposed,
// autoKind}. makeToken mirrors the real tokenDescriptor's fields.
function core(text, extra) {
    return Object.assign({ kind: "core", text: text, cantusId: "", proposed: false }, extra);
}
function component(text, cantusId, proposed) {
    return { kind: "component", text: text, cantusId: cantusId || "", proposed: !!proposed };
}
function separator() {
    return core("|", { autoKind: "separator" });
}

describe("plural", () => {
    it("uses the singular for exactly one", () => {
        assert.equal(plural(1, "element", "elements"), "1 element");
    });

    it("uses the plural for zero", () => {
        assert.equal(plural(0, "element", "elements"), "0 elements");
    });

    it("uses the plural for many", () => {
        assert.equal(plural(2, "element", "elements"), "2 elements");
        assert.equal(plural(17, "match", "matches"), "17 matches");
    });
});

describe("ciEndpoint", () => {
    it("fills the placeholder with the Cantus ID", () => {
        assert.equal(
            ciEndpoint("/ci-base-text/__CANTUS_ID__", "g01349"),
            "/ci-base-text/g01349"
        );
    });

    it("percent-encodes characters that would break the path", () => {
        // A component's ID like g04828:01 carries a colon; a dotted troped ID must survive.
        assert.equal(
            ciEndpoint("/ci-cluster-elements/__CANTUS_ID__", "g04828:01"),
            "/ci-cluster-elements/g04828%3A01"
        );
        assert.equal(
            ciEndpoint("/ci-base-text/__CANTUS_ID__", "g01349.tp14"),
            "/ci-base-text/g01349.tp14"
        );
    });

    it("encodes a Cantus ID that would otherwise inject path segments", () => {
        assert.equal(
            ciEndpoint("/ci-base-text/__CANTUS_ID__", "a/b"),
            "/ci-base-text/a%2Fb"
        );
    });
});

describe("rankResults", () => {
    const parent = "g01349.tp14";
    const own1 = { cid: "g01349.tp14:01", fulltext: "one" };
    const own2 = { cid: "g01349.tp14.Tp7", fulltext: "two" };
    const other = { cid: "909030", fulltext: "doxology" };
    const noId = { fulltext: "orphan" }; // no cid at all

    it("leaves order untouched when there is no parent", () => {
        const input = [other, own1];
        assert.deepEqual(rankResults(input, ""), input);
    });

    it("floats this cluster's own sub-elements to the top", () => {
        // both the "<parent>:NN" and "<parent>.Tp7" forms count as own
        assert.deepEqual(rankResults([other, own1, own2], parent), [own1, own2, other]);
    });

    it("keeps Cantus Index's order within each group", () => {
        assert.deepEqual(rankResults([own2, other, own1], parent), [own2, own1, other]);
    });

    it("treats a result with no cid as not-own", () => {
        assert.deepEqual(rankResults([noId, own1], parent), [own1, noId]);
    });

    it("does not match a different chant that merely shares a prefix", () => {
        // "g01349.tp14" must not claim "g01349.tp140:01" — the boundary is ":" or "."
        const cousin = { cid: "g01349.tp140:01", fulltext: "cousin" };
        assert.deepEqual(rankResults([cousin], parent), [cousin]);
    });

    it("returns a new array without mutating the input", () => {
        const input = [other, own1];
        const out = rankResults(input, parent);
        assert.deepEqual(input, [other, own1]); // untouched
        assert.notEqual(out, input);
    });
});

describe("rowsFromResults", () => {
    it("maps each match to a trimmed text and its Cantus ID, then a propose row", () => {
        const payload = {
            results: [{ fulltext: "AMEN ", cid: "x" }],
            total: 1,
        };
        const rows = rowsFromResults(payload, "am", "");
        assert.deepEqual(rows, [
            { kind: "match", element: { text: "AMEN", cantusId: "x" } },
            { kind: "propose", text: "am" },
        ]);
    });

    it("always ends with a propose row carrying the raw query", () => {
        const rows = rowsFromResults({ results: [], total: 0 }, "kyrie", "");
        assert.deepEqual(rows, [{ kind: "propose", text: "kyrie" }]);
    });

    it("adds an exact 'N matches' row when the filtered total exceeds the page", () => {
        const payload = { results: [{ fulltext: "a", cid: "1" }], total: 12 };
        const rows = rowsFromResults(payload, "q", "");
        assert.deepEqual(rows[1], {
            kind: "more",
            text: "12 matches — keep typing to narrow the search",
        });
        assert.equal(rows[rows.length - 1].kind, "propose");
    });

    it("adds a '100+' row when Cantus Index capped upstream, not an exact count", () => {
        const payload = {
            results: [{ fulltext: "a", cid: "1" }],
            total: 100,
            capped: true,
        };
        const rows = rowsFromResults(payload, "q", "");
        assert.deepEqual(rows[1], {
            kind: "more",
            text: "100+ Cantus Index matches — keep typing to narrow the search",
        });
    });

    it("adds no 'more' row when the page holds every match", () => {
        const payload = {
            results: [{ fulltext: "a", cid: "1" }],
            total: 1,
        };
        const rows = rowsFromResults(payload, "q", "");
        assert.equal(rows.length, 2); // the one match + propose
        assert.ok(!rows.some((r) => r.kind === "more"));
    });

    it("defaults total to the number of results when the payload omits it", () => {
        const payload = { results: [{ fulltext: "a", cid: "1" }] };
        const rows = rowsFromResults(payload, "q", "");
        assert.ok(!rows.some((r) => r.kind === "more"));
    });

    it("tolerates a payload with no results at all", () => {
        const rows = rowsFromResults({}, "q", "");
        assert.deepEqual(rows, [{ kind: "propose", text: "q" }]);
    });

    it("applies the in-cluster ranking through to the rendered rows", () => {
        const payload = {
            results: [
                { fulltext: "far", cid: "909030" },
                { fulltext: "near", cid: "g99:01" },
            ],
            total: 2,
        };
        const rows = rowsFromResults(payload, "q", "g99");
        assert.equal(rows[0].element.text, "near"); // own floated above unrelated
        assert.equal(rows[1].element.text, "far");
    });
});

describe("ciErrorRows", () => {
    it("flags the outage and still offers to propose the typed text", () => {
        assert.deepEqual(ciErrorRows("gloria"), [
            { kind: "notice", text: "Cantus Index unavailable — try again in a moment" },
            { kind: "propose", text: "gloria" },
        ]);
    });
});

describe("messageRowText", () => {
    it("names the search while a request is in flight", () => {
        assert.equal(messageRowText("loading"), "Searching Cantus Index…");
    });

    it("falls back to the prompt for anything else", () => {
        assert.equal(messageRowText("hint"), "Type to search or add component elements");
        assert.equal(messageRowText("anything"), "Type to search or add component elements");
    });
});

describe("isNavigable", () => {
    it("is true for the two rows a cataloguer can act on", () => {
        assert.equal(isNavigable({ kind: "match" }), true);
        assert.equal(isNavigable({ kind: "propose" }), true);
    });

    it("is false for the status/prompt rows", () => {
        for (const kind of ["more", "notice", "loading", "hint"]) {
            assert.equal(isNavigable({ kind }), false, kind);
        }
    });

    it("is false for a missing row", () => {
        assert.equal(isNavigable(null), false);
        assert.equal(isNavigable(undefined), false);
    });
});

describe("canSplitText", () => {
    it("is false for a one-word element", () => {
        assert.equal(canSplitText("SANCTUS"), false);
    });

    it("is false for a lone separator", () => {
        assert.equal(canSplitText("|"), false);
    });

    it("is true once there is a word boundary", () => {
        assert.equal(canSplitText("SANCTUS DEUS"), true);
    });

    it("ignores surrounding and repeated whitespace", () => {
        assert.equal(canSplitText("  SANCTUS   DEUS  "), true);
        assert.equal(canSplitText("   SANCTUS   "), false);
    });

    it("is false for empty text", () => {
        assert.equal(canSplitText(""), false);
        assert.equal(canSplitText("   "), false);
    });
});

describe("splitWords", () => {
    it("divides at the word boundary, joining each half with single spaces", () => {
        assert.deepEqual(splitWords("a b c", 1), { left: "a", right: "b c" });
        assert.deepEqual(splitWords("a b c", 2), { left: "a b", right: "c" });
    });

    it("collapses interior whitespace into the halves", () => {
        assert.deepEqual(splitWords("a   b  c", 1), { left: "a", right: "b c" });
    });

    it("yields an empty half at the ends — the caller rejects those", () => {
        assert.deepEqual(splitWords("a b c", 0), { left: "", right: "a b c" });
        assert.deepEqual(splitWords("a b c", 3), { left: "a b c", right: "" });
    });
});

describe("mergeKindMatches", () => {
    it("accepts a run of adjacent cores", () => {
        assert.equal(mergeKindMatches([core("SANCTUS"), core("DEUS")]), true);
    });

    it("accepts a run of proposed components", () => {
        assert.equal(
            mergeKindMatches([component("a", "", true), component("b", "", true)]),
            true
        );
    });

    it("refuses a single element", () => {
        assert.equal(mergeKindMatches([core("SANCTUS")]), false);
        assert.equal(mergeKindMatches([]), false);
    });

    it("refuses a run that includes an auto-split separator", () => {
        assert.equal(mergeKindMatches([core("SANCTUS"), separator()]), false);
    });

    it("refuses folding across kinds", () => {
        assert.equal(mergeKindMatches([core("SANCTUS"), component("trope", "x")]), false);
    });

    it("refuses mixing proposed with approved components", () => {
        assert.equal(
            mergeKindMatches([component("a", "", true), component("b", "y", false)]),
            false
        );
    });

    it("refuses approved components — each owns its Cantus ID for its whole text", () => {
        assert.equal(
            mergeKindMatches([component("a", "x", false), component("b", "y", false)]),
            false
        );
    });
});

describe("joinElementTexts", () => {
    it("joins element texts with single spaces", () => {
        assert.equal(joinElementTexts([core("SANCTUS"), core("DEUS")]), "SANCTUS DEUS");
    });

    it("collapses interior whitespace and trims", () => {
        assert.equal(joinElementTexts([core("  a  b "), core(" c ")]), "a b c");
    });

    it("is empty for no elements", () => {
        assert.equal(joinElementTexts([]), "");
    });
});

describe("serializeElements", () => {
    it("maps each descriptor to the persisted ChantElement shape", () => {
        const out = serializeElements([
            core("SANCTUS"),
            component("trope", "g99:01", false),
            component("new bit", "", true),
        ]);
        assert.deepEqual(out, [
            { kind: "core", text: "SANCTUS", cantus_id: "", proposed: false },
            { kind: "component", text: "trope", cantus_id: "g99:01", proposed: false },
            { kind: "component", text: "new bit", cantus_id: "", proposed: true },
        ]);
    });

    it("defaults a missing Cantus ID to the empty string", () => {
        const out = serializeElements([{ kind: "core", text: "x" }]);
        assert.equal(out[0].cantus_id, "");
    });

    it("coerces proposed to a real boolean", () => {
        const out = serializeElements([{ kind: "component", text: "x", proposed: undefined }]);
        assert.equal(out[0].proposed, false);
    });

    it("round-trips through JSON as the hidden field ships it", () => {
        const out = serializeElements([core("SANCTUS")]);
        assert.deepEqual(JSON.parse(JSON.stringify(out)), out);
    });
});

describe("nearestPoint", () => {
    // Points model the drop gaps insertionPoints() builds: {token, x, top, height}.
    const p = (label, x, top, height) => ({ token: label, x, top, height });

    it("returns null when there are no gaps", () => {
        assert.equal(nearestPoint([], 10, 10), null);
    });

    it("picks the nearest gap horizontally within a line", () => {
        const line = [p("left", 0, 0, 20), p("right", 100, 0, 20)];
        assert.equal(nearestPoint(line, 90, 5).token, "right");
        assert.equal(nearestPoint(line, 10, 5).token, "left");
    });

    it("lets vertical distance dominate, so a drop never jumps lines on x alone", () => {
        // The other-line gap is far closer in x (0 vs 40 away) but a whole line down;
        // the same-line gap must still win.
        const points = [
            p("sameLine", 100, 0, 20), // pointer is level with this line
            p("nextLine", 60, 100, 20), // closer in x, but 100px below
        ];
        assert.equal(nearestPoint(points, 60, 5).token, "sameLine");
    });

    it("scores a pointer level with a line as zero vertical distance across its height", () => {
        const points = [p("a", 0, 100, 20)];
        // y anywhere within [top, top+height] is level → distance is pure horizontal
        assert.equal(nearestPoint(points, 0, 100).token, "a");
        assert.equal(nearestPoint(points, 0, 120).token, "a");
    });

    it("keeps the first gap on a tie rather than drifting to a later one", () => {
        const points = [p("first", 50, 0, 20), p("second", 50, 0, 20)];
        assert.equal(nearestPoint(points, 50, 5).token, "first");
    });
});
