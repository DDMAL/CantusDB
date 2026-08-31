/**
 * Unit tests for the Markdown widget's pure editing logic (issue #2216 / PR #2226).
 *
 * These cover the string/selection transforms that back the toolbar buttons,
 * keyboard shortcuts, list continuation, indentation and URL-paste. They run in
 * Node with zero dependencies via the built-in runner:
 *
 *     node --test js_tests/
 *
 * The widget exports its helpers under `typeof module !== "undefined"`, so no DOM
 * or browser is needed here — the functions operate on a plain textarea-like
 * object. Real browser behaviour (event wiring, Bootstrap tabs, marked preview)
 * is verified manually in the running app.
 */

const { test } = require("node:test");
const assert = require("node:assert/strict");

const md = require("../django/cantusdb_project/static/js/markdown_widget.js");

// A minimal stand-in for a <textarea>: just the properties the widget reads and
// writes. `focus()` is a no-op — selection state persists on the object.
function ta(value, selectionStart, selectionEnd) {
    if (selectionStart === undefined) {
        selectionStart = value.length;
    }
    if (selectionEnd === undefined) {
        selectionEnd = selectionStart;
    }
    return {
        value,
        selectionStart,
        selectionEnd,
        focus() {},
    };
}

// Assert the full post-condition: text plus where the selection/caret landed.
function expectState(el, value, selectionStart, selectionEnd) {
    assert.deepEqual(
        {
            value: el.value,
            selectionStart: el.selectionStart,
            selectionEnd: el.selectionEnd,
        },
        { value, selectionStart, selectionEnd }
    );
}

// A synthetic paste event carrying `text` on the clipboard.
function pasteEvent(text) {
    let prevented = false;
    return {
        clipboardData: { getData: () => text },
        preventDefault() {
            prevented = true;
        },
        get defaultPrevented() {
            return prevented;
        },
    };
}

// --------------------------------------------------------------------------
// bold / italic  (wrapInline, via the toolbar action table)
// --------------------------------------------------------------------------

test("bold wraps the selection and selects the inner text", () => {
    const el = ta("hello", 0, 5);
    md.actions.bold(el);
    expectState(el, "**hello**", 2, 7);
});

test("bold with no selection inserts the placeholder, selected for typing over", () => {
    const el = ta("", 0, 0);
    md.actions.bold(el);
    expectState(el, "**bold text**", 2, 11);
});

test("bold toggles off when the markers are inside the selection", () => {
    const el = ta("**hello**", 0, 9);
    md.actions.bold(el);
    expectState(el, "hello", 0, 5);
});

test("bold toggles off when the markers sit just outside the selection", () => {
    const el = ta("**hello**", 2, 7);
    md.actions.bold(el);
    expectState(el, "hello", 0, 5);
});

test("italic wraps with a single asterisk", () => {
    const el = ta("hello", 0, 5);
    md.actions.italic(el);
    expectState(el, "*hello*", 1, 6);
});

test("italic does not strip a bold run's markers (selection includes **)", () => {
    // isWrapped("**hello**", "*") is false, so italic adds a layer rather than
    // mistaking the bold markers for its own.
    const el = ta("**hello**", 0, 9);
    md.actions.italic(el);
    expectState(el, "***hello***", 1, 10);
});

test("italic inside a bold run adds italic markers, not strips the bold ones", () => {
    // "hello" selected inside **...**: the italic-in-bold guard prevents the
    // adjacent ** from being treated as italic markers to remove.
    const el = ta("**hello**", 2, 7);
    md.actions.italic(el);
    expectState(el, "***hello***", 3, 8);
});

// --------------------------------------------------------------------------
// link  (insertLink)
// --------------------------------------------------------------------------

test("link wraps the selection and leaves the url selected", () => {
    const el = ta("see docs", 4, 8);
    md.actions.link(el);
    expectState(el, "see [docs](url)", 11, 14);
});

test("link with no selection inserts a text/url skeleton", () => {
    const el = ta("", 0, 0);
    md.actions.link(el);
    expectState(el, "[text](url)", 7, 10);
});

// --------------------------------------------------------------------------
// heading / quote / lists  (toggleLinePrefix)
// --------------------------------------------------------------------------

test("heading prefixes a single line", () => {
    const el = ta("Title", 0, 5);
    md.actions.heading(el);
    expectState(el, "# Title", 0, 7);
});

test("heading toggles off when every line already has it", () => {
    const el = ta("# Title", 0, 7);
    md.actions.heading(el);
    expectState(el, "Title", 0, 5);
});

test("heading re-applies without stacking markers on a mixed selection", () => {
    // One line marked, one not => not all-marked => normalize + (re)apply.
    const el = ta("# A\nB", 0, 5);
    md.actions.heading(el);
    expectState(el, "# A\n# B", 0, 7);
});

test("quote prefixes and toggles off", () => {
    const on = ta("a", 0, 1);
    md.actions.quote(on);
    expectState(on, "> a", 0, 3);

    const off = ta("> a", 0, 3);
    md.actions.quote(off);
    expectState(off, "a", 0, 1);
});

test("unordered list prefixes each selected line and toggles off", () => {
    const on = ta("a\nb", 0, 3);
    md.actions["unordered-list"](on);
    expectState(on, "- a\n- b", 0, 7);

    const off = ta("- a\n- b", 0, 7);
    md.actions["unordered-list"](off);
    expectState(off, "a\nb", 0, 3);
});

test("ordered list numbers lines sequentially and toggles off", () => {
    const on = ta("a\nb\nc", 0, 5);
    md.actions["ordered-list"](on);
    expectState(on, "1. a\n2. b\n3. c", 0, 14);

    const off = ta("1. a\n2. b", 0, 9);
    md.actions["ordered-list"](off);
    expectState(off, "a\nb", 0, 3);
});

test("list marker toggles off without eating the line's indentation", () => {
    const el = ta("  - item", 0, 8);
    md.actions["unordered-list"](el);
    expectState(el, "  item", 0, 6);
});

test("list marker is inserted after the indentation, not before it", () => {
    const el = ta("  item", 0, 6);
    md.actions["unordered-list"](el);
    expectState(el, "  - item", 0, 8);
});

test("nested list levels keep their own indentation through a toggle", () => {
    const on = ta("- a\n  - b\n    - c", 0, 17);
    md.actions["unordered-list"](on);
    expectState(on, "a\n  b\n    c", 0, 11);

    const off = ta("a\n  b\n    c", 0, 11);
    md.actions["unordered-list"](off);
    expectState(off, "- a\n  - b\n    - c", 0, 17);
});

test("quote marker toggles off an indented line without losing the indent", () => {
    const el = ta("  > a", 0, 5);
    md.actions.quote(el);
    expectState(el, "  a", 0, 3);
});

test("quote marker is inserted after the indentation", () => {
    const el = ta("  a", 0, 3);
    md.actions.quote(el);
    expectState(el, "  > a", 0, 5);
});

test("ordered list keeps indentation on both directions of the toggle", () => {
    const on = ta("  a\n  b", 0, 7);
    md.actions["ordered-list"](on);
    expectState(on, "  1. a\n  2. b", 0, 13);

    const off = ta("  1. a\n  2. b", 0, 13);
    md.actions["ordered-list"](off);
    expectState(off, "  a\n  b", 0, 7);
});

test("heading does not stack markers on an already-marked indented line", () => {
    const el = ta("  # Title", 0, 9);
    md.actions.heading(el);
    expectState(el, "  Title", 0, 7);
});

test("line prefix only touches the lines the selection spans", () => {
    // Caret sits inside "bar"; "foo" and "baz" are untouched.
    const el = ta("foo\nbar\nbaz", 5, 5);
    md.actions["unordered-list"](el);
    expectState(el, "foo\n- bar\nbaz", 4, 9);
});

// --------------------------------------------------------------------------
// Tab / Shift+Tab  (indentLines)
// --------------------------------------------------------------------------

test("Tab indents a single line by two spaces", () => {
    const el = ta("item", 0, 0);
    md.indentLines(el, false);
    expectState(el, "  item", 2, 2);
});

test("Tab indents every line the selection touches", () => {
    const el = ta("a\nb", 0, 3);
    md.indentLines(el, false);
    expectState(el, "  a\n  b", 2, 7);
});

test("Shift+Tab outdents two spaces", () => {
    const el = ta("  item", 6, 6);
    md.indentLines(el, true);
    expectState(el, "item", 4, 4);
});

test("Shift+Tab outdents a leading tab", () => {
    const el = ta("\titem", 5, 5);
    md.indentLines(el, true);
    expectState(el, "item", 4, 4);
});

test("Shift+Tab outdents a single leading space", () => {
    const el = ta(" item", 5, 5);
    md.indentLines(el, true);
    expectState(el, "item", 4, 4);
});

test("Shift+Tab on an unindented line is a no-op and never moves the caret before the line", () => {
    const el = ta("item", 0, 0);
    md.indentLines(el, true);
    expectState(el, "item", 0, 0);
});

// --------------------------------------------------------------------------
// Enter continuation  (continueList)
// --------------------------------------------------------------------------

test("Enter continues an unordered list", () => {
    const el = ta("- item");
    assert.equal(md.continueList(el), true);
    expectState(el, "- item\n- ", 9, 9);
});

test("Enter increments an ordered list", () => {
    const el = ta("1. item");
    assert.equal(md.continueList(el), true);
    expectState(el, "1. item\n2. ", 11, 11);
});

test("Enter continues an ordered list that uses ')' as the delimiter", () => {
    const el = ta("1) item");
    assert.equal(md.continueList(el), true);
    expectState(el, "1) item\n2) ", 11, 11);
});

test("Enter continues a blockquote", () => {
    const el = ta("> quote");
    assert.equal(md.continueList(el), true);
    expectState(el, "> quote\n> ", 10, 10);
});

test("Enter keeps every level of a nested blockquote", () => {
    const el = ta("> > text");
    assert.equal(md.continueList(el), true);
    expectState(el, "> > text\n> > ", 13, 13);
});

test("Enter keeps a nested blockquote's leading indentation", () => {
    const el = ta("  > > text");
    assert.equal(md.continueList(el), true);
    expectState(el, "  > > text\n  > > ", 17, 17);
});

test("Enter on an empty nested blockquote clears the markers and exits", () => {
    const el = ta("> > ");
    assert.equal(md.continueList(el), true);
    expectState(el, "", 0, 0);
});

test("Enter preserves indentation when continuing a nested list", () => {
    const el = ta("  - item");
    assert.equal(md.continueList(el), true);
    expectState(el, "  - item\n  - ", 13, 13);
});

test("Enter on an empty list item clears the marker and exits the list", () => {
    const el = ta("- ");
    assert.equal(md.continueList(el), true);
    expectState(el, "", 0, 0);
});

test("Enter on a plain line is not handled (lets the newline through)", () => {
    const el = ta("hello");
    assert.equal(md.continueList(el), false);
    expectState(el, "hello", 5, 5);
});

test("Enter with a non-collapsed selection is not handled", () => {
    const el = ta("- item", 2, 4);
    assert.equal(md.continueList(el), false);
    expectState(el, "- item", 2, 4);
});

// --------------------------------------------------------------------------
// Paste-over-selection → link  (handlePaste)
// --------------------------------------------------------------------------

test("pasting a URL over a selection turns it into a markdown link", () => {
    const el = ta("click here", 6, 10);
    const e = pasteEvent("https://example.com");
    md.handlePaste(el, e);
    assert.equal(e.defaultPrevented, true);
    expectState(el, "click [here](https://example.com)", 33, 33);
});

test("pasting a URL trims surrounding whitespace", () => {
    const el = ta("here", 0, 4);
    md.handlePaste(el, pasteEvent("  https://example.com  "));
    assert.equal(el.value, "[here](https://example.com)");
});

test("pasting non-URL text is left to the browser's default handling", () => {
    const el = ta("here", 0, 4);
    const e = pasteEvent("not a url");
    md.handlePaste(el, e);
    assert.equal(e.defaultPrevented, false);
    expectState(el, "here", 0, 4);
});

test("pasting a 'URL' containing a space is not treated as a link", () => {
    const el = ta("here", 0, 4);
    const e = pasteEvent("https://example.com other");
    md.handlePaste(el, e);
    assert.equal(e.defaultPrevented, false);
    assert.equal(el.value, "here");
});

test("pasting with no selection is left to the browser (no link wrapping)", () => {
    const el = ta("text", 4, 4);
    const e = pasteEvent("https://example.com");
    md.handlePaste(el, e);
    assert.equal(e.defaultPrevented, false);
    expectState(el, "text", 4, 4);
});
