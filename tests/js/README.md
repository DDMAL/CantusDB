# JavaScript tests

Tests for the front-end logic that is worth testing on its own — the automatic split of Cantus
Index text on the Create Chant page and the cluster composer's submit-time guards (#2165).

## Running them

```bash
node --test "tests/js/**/*.test.js"
```

Node's built-in test runner (`node:test` + `node:assert`), so there is **nothing to install** and
no `package.json`. Node 21 or newer, since `node --test` only learned to expand glob patterns in
21 (CI runs 22). (Quote the glob — passing the bare directory does not work on current Node.)

These are not Django tests — `manage.py test` does not reach them — but they do run in CI, via
`.github/workflows/js_tests.yml`.

## What is here

| Path | What |
|---|---|
| `auto_split.test.js` | the split rules — one test per convention, the three ground-truth chants asserted exactly, and the invariants the feature rests on |
| `composer_logic.test.js` | the composer's pure decisions — CI result ranking, typeahead row building, merge eligibility, the split boundary, the persisted-element payload, the flattened text, and the drop-target geometry |
| `cluster_submit.test.js` | the composer's submit-time guards — empty composer and leftover auto-split separators are both blocked, with the right message and precedence |
| `fixtures/cantus_index_texts.json` | 48 real Cantus Index chant texts, each labelled with the convention it exercises |

All three suites load the exact file that ships and read a plain object off a stub `window` — the
same object the page reads. `chant_create_auto_split.js` is pure functions over a string, so it
loads directly. `chant_create_clusters.js` is the composer itself; it guards its
`DOMContentLoaded` hook on `document`, so with no document present the wiring never runs and its
pure API (`window.ChantClusterComposer`) is left to read off.

That pure API is the composer's decision layer, pulled out from the DOM plumbing that calls it so
it can be pinned here: `rankResults` / `rowsFromResults` / `ciErrorRows` / `messageRowText` /
`isNavigable` (the typeahead), `mergeKindMatches` (which runs may merge), `splitWords` /
`canSplitText` (the split), `serializeElements` / `joinElementTexts` (what the server receives and
the flattened field), `nearestPoint` (the drag drop-target), and `submissionError` (the submit
guard). The wrappers that call these are thin by construction — a `tokenDescriptor` snapshot in,
a DOM edit out — so pinning the core pins most of what can go wrong.

**The DOM plumbing itself is still not covered here.** The parts that only exist as DOM — drag and
drop, the caret bookkeeping, the floating menus, the shift-click run and the ⌘/Ctrl-click pick,
undo, the restore tray, the hotkey gating — are verified by hand in the browser and by the
local-only Playwright harness (`.e2e/`, gitignored). Covering them *in CI* would need a DOM (jsdom)
or a browser driver, i.e. the repo's first front-end dependency, which nobody has signed off on;
the pure layer above is the coverage that fits within Node's built-in runner and no dependency.

## The fixture

Real chant texts fetched from Cantus Index:

- `https://cantusindex.org/json-text/<search term>` for bulk sampling,
- `https://cantusindex.org/json-cid/<cantus id>` for one chant.

It is curated, not exhaustive: two or three texts per convention, plus every chant named in the
rules' header comment, plus the three chants (`g04828`, `ah47439`, `g01349.tp14`) whose elements
Cantus Index catalogues separately as `<parent>:NN` and which are therefore the only ground truth
available. The `category` field records why each text is in the file, and failing invariants
print it.

`g01349` is in the file for the opposite reason: it is the *base* chant the composer now seeds
`g01349.tp14` from (#2189), and what it pins is that clean text yields nothing to split.

To add a case, add the text to `fixtures/cantus_index_texts.json` with a `category`, and — if it
demonstrates a new convention — require that category in the `describe("the fixture")` block so a
later edit cannot quietly drop it.

## Sweeping a larger sample

The rules were originally derived from about 4,325 Cantus Index texts — too many, and too
incidental, to commit. If you change a rule it is worth rebuilding that sample locally and
checking the invariants over all of it rather than trusting 48 texts.

There is no script in the repo for this; it is a dozen lines. Fetch `/json-text/<term>` for a
spread of common Latin incipit words (`sanctus`, `agnus`, `gloria`, `benedictus`, `kyrie`, …),
keep each result's `cid`, `genre` and `fulltext`, then run every text through `splitText` and
assert the same invariants the `describe("what the rules must never do…")` block asserts here.
Be polite to the server: it is a public catalogue, so sample once and cache to a file.
