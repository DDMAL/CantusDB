# JavaScript tests

Tests for the front-end logic that is worth testing on its own — currently the automatic split of
Cantus Index text on the Create Chant page (#2165).

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
| `fixtures/cantus_index_texts.json` | 48 real Cantus Index chant texts, each labelled with the convention it exercises |

The code under test is
`django/cantusdb_project/static/js/chant_create_auto_split.js`. It is a browser script with no
DOM access at all — pure functions over a string — which is why it can be loaded and run here.
The test evaluates that exact file against a stub `window` and reads the `ChantAutoSplit` object
off it, the same object the composer reads in the page.

**Anything that touches the DOM is not covered.** The composer's own behaviour — merge, the
shift-click run and the ⌘/Ctrl-click pick, delete, undo, the restore tray, the hotkey gating —
has no automated coverage and is verified by hand in the browser. Covering it would need a DOM
(jsdom) or a browser driver (Playwright), i.e. the repo's first front-end dependency, which
nobody has signed off on.

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
