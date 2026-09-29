/*
 * Tests for the client side of the nonblocking chant text warning (#1681).
 *
 * The promise this feature makes is that the check never stands between the
 * user and a save. The failure modes that can break that promise all live in
 * the submit handler of `chant_text_validation.js`, which disables the save
 * buttons while the check runs: a request that stalls, a response that arrives
 * after we have given up on it, a browser that refuses the programmatic submit
 * on its own constraint validation. None of them are reachable from Python, so
 * they are pinned here.
 *
 * The script is a DOM script with no exported API, so these load the file that
 * ships and hand it stand-ins for the globals it reads -- a small page, a
 * Bootstrap modal, `fetch`, and a clock the test advances by hand. Everything
 * else about the page (styling, the real modal markup, Bootstrap itself) still
 * needs a browser.
 */

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const SCRIPT_PATH = path.join(
    __dirname,
    "..",
    "..",
    "django",
    "cantusdb_project",
    "static",
    "js",
    "chant_text_validation.js"
);
const SOURCE = fs.readFileSync(SCRIPT_PATH, "utf8");

// The deadline the script gives the check, in milliseconds. Kept here rather
// than imported because the script is an IIFE with nothing to import from; a
// change to it should be a deliberate change to these tests too.
const VALIDATION_TIMEOUT_MS = 5000;

const TEXT_FIELD = "manuscript_full_text_std_spelling";

// Let every pending promise callback run. `setImmediate` is a real macrotask,
// so it fires only once the microtask queue has drained.
function flush() {
    return new Promise((resolve) => setImmediate(resolve));
}

function escapeText(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

// Enough of a CSS selector to cover what the script asks for: an optional
// leading class, then any number of `[attribute="value"]` tests.
function matches(element, selector) {
    const wantedClass = selector.match(/^\.([\w-]+)/);
    if (wantedClass) {
        const classes = String(element.className || "").split(/\s+/);
        if (!classes.includes(wantedClass[1])) {
            return false;
        }
    }
    const attribute = /\[([\w-]+)="([^"]*)"\]/g;
    let test;
    while ((test = attribute.exec(selector)) !== null) {
        if (element.getAttribute(test[1]) !== test[2]) {
            return false;
        }
    }
    return true;
}

function makeElement(tag, attributes) {
    const element = {
        tag,
        attributes: Object.assign({}, attributes),
        innerHTML: "",
        value: "",
        disabled: false,
        container: null,
        listeners: new Map(),
    };
    const classes = new Set();
    element.classList = {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        contains: (name) => classes.has(name),
    };
    element.getAttribute = (name) =>
        Object.prototype.hasOwnProperty.call(element.attributes, name)
            ? element.attributes[name]
            : null;
    element.setAttribute = (name, value) => {
        element.attributes[name] = String(value);
    };
    // `name` and `type` reflect to the matching content attribute, as they do
    // on a real input: the script sets them as properties and then finds the
    // element again by attribute selector.
    for (const reflected of ["name", "type"]) {
        Object.defineProperty(element, reflected, {
            get: () => element.getAttribute(reflected),
            set: (value) => element.setAttribute(reflected, value),
        });
    }
    element.addEventListener = (type, handler) => {
        if (!element.listeners.has(type)) {
            element.listeners.set(type, []);
        }
        element.listeners.get(type).push(handler);
    };
    element.dispatch = (type, event) => {
        for (const handler of element.listeners.get(type) || []) {
            handler(event);
        }
    };
    element.remove = () => {
        if (!element.container) {
            return;
        }
        const index = element.container.indexOf(element);
        if (index >= 0) {
            element.container.splice(index, 1);
        }
    };
    // The script escapes text by round-tripping it through an element, the way
    // a browser does.
    Object.defineProperty(element, "textContent", {
        get: () => element.text || "",
        set: (value) => {
            element.text = String(value);
            element.innerHTML = escapeText(element.text);
        },
    });
    return element;
}

// A clock the test drives, so a stalled request doesn't mean a stalled test.
function makeClock() {
    let nextId = 1;
    const timers = new Map();
    return {
        setTimeout(callback, delay) {
            const id = nextId++;
            timers.set(id, { callback, delay });
            return id;
        },
        clearTimeout(id) {
            timers.delete(id);
        },
        pending: () => timers.size,
        tick(elapsed) {
            for (const [id, timer] of Array.from(timers)) {
                if (timer.delay <= elapsed) {
                    timers.delete(id);
                    timer.callback();
                }
            }
        },
    };
}

/*
 * Build a chant edit page with one text field and two save buttons, load the
 * script against it, and hand back the controls a test needs: the requests the
 * script made, the submits it asked the browser for, and the clock.
 *
 * `options.abortController` replaces the `AbortController` the script is given;
 * pass `undefined` for a browser that has `fetch` but not `AbortController`,
 * where the deadline still has to work.
 */
function makeHarness(options) {
    const settings = Object.assign({ abortController: AbortController }, options);
    const contents = [];
    const requests = [];
    const submits = [];
    const modalCalls = { shown: 0, hidden: 0 };
    const clock = makeClock();

    const form = makeElement("form");
    form.querySelector = (selector) =>
        contents.find((element) => matches(element, selector)) || null;
    form.querySelectorAll = (selector) =>
        contents.filter((element) => matches(element, selector));
    form.appendChild = (element) => {
        element.container = contents;
        contents.push(element);
        return element;
    };

    const csrf = makeElement("input", { name: "csrfmiddlewaretoken" });
    csrf.value = "csrf-token";
    form.appendChild(csrf);

    const field = makeElement("textarea", { name: TEXT_FIELD });
    field.form = form;
    field.insertAdjacentElement = (position, element) => {
        assert.equal(position, "afterend");
        form.appendChild(element);
    };
    form.appendChild(field);

    const saveButton = makeElement("button", { type: "submit" });
    const saveAndAnotherButton = makeElement("button", { type: "submit" });
    form.appendChild(saveButton);
    form.appendChild(saveAndAnotherButton);

    const harness = {
        form,
        field,
        saveButton,
        saveAndAnotherButton,
        contents,
        requests,
        submits,
        modalCalls,
        clock,
        flush,
        // Set to make the browser refuse the script's programmatic submit, as
        // native constraint validation does when a required field is empty.
        nativeValidationBlocks: false,
    };

    form.requestSubmit = (submitter) => {
        const acknowledgement = form.querySelector(
            '[name="confirm_invalid_text"]'
        );
        submits.push({
            submitter,
            confirmInvalidText: acknowledgement ? acknowledgement.value : null,
            saveButtonDisabled: saveButton.disabled,
        });
        if (harness.nativeValidationBlocks) {
            return;
        }
        // A browser that accepts the submit fires the event first; the script's
        // own listener has to let that one through.
        form.dispatch("submit", {
            preventDefault: () => {},
            submitter,
        });
    };

    const modal = makeElement("div", {
        id: "chant-text-warning-modal",
        "data-validate-url": "/validate-chant-text/",
    });
    const modalBody = makeElement("div", {
        id: "chant-text-warning-modal-body",
    });
    const saveAnywayButton = makeElement("button", {
        id: "chant-text-warning-save-anyway",
    });
    harness.modalBody = modalBody;
    harness.saveAnywayButton = saveAnywayButton;

    const byId = {
        "chant-text-warning-modal": modal,
        "chant-text-warning-modal-body": modalBody,
        "chant-text-warning-save-anyway": saveAnywayButton,
    };
    const documentStub = {
        readyState: "complete",
        getElementById: (id) => byId[id] || null,
        querySelector: (selector) =>
            contents.find((element) => matches(element, selector)) || null,
        createElement: (tag) => makeElement(tag),
        addEventListener: () => {},
    };

    const bootstrapStub = {
        Modal: function () {
            this.show = () => {
                modalCalls.shown += 1;
            };
            this.hide = () => {
                modalCalls.hidden += 1;
            };
        },
    };

    // Each call hands back a promise the test settles, so a request can be left
    // hanging, answered late, or failed at will.
    const fetchStub = (url, init) => {
        let settle;
        const promise = new Promise((resolve, reject) => {
            settle = { resolve, reject };
        });
        requests.push({
            url,
            init,
            respond(problems) {
                settle.resolve({
                    ok: true,
                    json: () => Promise.resolve({ problems }),
                });
            },
            // Headers arrive, the body does not. `fetch` resolves here, so this
            // is the point past which a deadline around `fetch` alone would
            // already have been cleared. Returns the handle to settle the body.
            respondHeadersOnly() {
                let settleBody;
                const body = new Promise((resolve, reject) => {
                    settleBody = {
                        resolve: (problems) => resolve({ problems }),
                        reject: () => reject(new Error("body read failed")),
                    };
                });
                settle.resolve({ ok: true, json: () => body });
                return settleBody;
            },
            fail() {
                settle.reject(new Error("network error"));
            },
        });
        return promise;
    };

    harness.submit = (submitter) => {
        form.dispatch("submit", {
            preventDefault: () => {},
            submitter: submitter || saveButton,
        });
    };
    harness.echoFor = (name) =>
        form.querySelector('.chant-text-warning-echo[data-field="' + name + '"]');

    new Function(
        "document",
        "bootstrap",
        "fetch",
        "setTimeout",
        "clearTimeout",
        "AbortController",
        SOURCE
    )(
        documentStub,
        bootstrapStub,
        fetchStub,
        clock.setTimeout,
        clock.clearTimeout,
        settings.abortController
    );

    return harness;
}

function problem(message) {
    return {
        field: TEXT_FIELD,
        label: "Full text as in Source (standardized spelling)",
        kind: "invalid_characters",
        message: message || 'contains character(s) that aren\'t allowed: "#".',
        marked_html: 'Gloria <mark>#</mark> Deo',
    };
}

describe("chant text validation: the ordinary flow", () => {
    it("submits once, unacknowledged, when the text is fine", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria in excelsis Deo";

        harness.submit();
        assert.equal(harness.requests.length, 1);
        assert.equal(harness.saveButton.disabled, true);

        harness.requests[0].respond([]);
        await flush();

        assert.equal(harness.submits.length, 1);
        // No acknowledgement flag: there was nothing to acknowledge, and the
        // server must stay free to warn about anything it finds.
        assert.equal(harness.submits[0].confirmInvalidText, "");
        assert.equal(harness.saveButton.disabled, false);
        assert.equal(harness.modalCalls.shown, 0);
    });

    it("warns instead of saving, then saves once the user accepts", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.requests[0].respond([problem()]);
        await flush();

        assert.equal(harness.submits.length, 0);
        assert.equal(harness.modalCalls.shown, 1);
        // The user has to be able to act on the warning.
        assert.equal(harness.saveButton.disabled, false);

        harness.saveAnywayButton.dispatch("click", {});

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "1");
        // The acknowledged submit goes straight through rather than starting
        // the check over.
        assert.equal(harness.requests.length, 1);
    });

    it("drops a field's echo as soon as the user edits it", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.requests[0].respond([problem()]);
        await flush();
        assert.ok(harness.echoFor(TEXT_FIELD));

        harness.field.value = "Gloria Deo";
        harness.field.dispatch("input", {});

        // The echo shows the text as it was when the check ran, so it must go
        // rather than linger over text it no longer describes.
        assert.equal(harness.echoFor(TEXT_FIELD), null);
    });

    it("runs one check however often the user clicks save", () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.submit();
        harness.submit();

        assert.equal(harness.requests.length, 1);
    });
});

describe("chant text validation: the check must never block a save", () => {
    it("saves anyway once a stalled check passes its deadline", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        // Nothing has come back; the buttons are disabled and the save is stuck.
        assert.equal(harness.saveButton.disabled, true);
        assert.equal(harness.submits.length, 0);

        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();

        assert.equal(harness.submits.length, 1);
        // Unacknowledged, because the user never saw a warning: the server's
        // own non-blocking warning still has to reach them.
        assert.equal(harness.submits[0].confirmInvalidText, "");
        assert.equal(harness.saveButton.disabled, false);
        assert.equal(harness.modalCalls.shown, 0);
        assert.equal(harness.requests[0].init.signal.aborted, true);
    });

    it("ignores a response that arrives after the deadline", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();
        assert.equal(harness.submits.length, 1);

        // The request was abandoned, not cancelled everywhere: a server that
        // answers late must not submit the form a second time or raise a modal
        // over a page the user has already left.
        harness.requests[0].respond([problem()]);
        await flush();

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.modalCalls.shown, 0);
    });

    it("keeps the deadline running while the response body stalls", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        // The server sends headers and then nothing. `fetch` has resolved, so a
        // deadline that covered only `fetch` would have been cleared by now and
        // the save buttons would stay disabled for good.
        const body = harness.requests[0].respondHeadersOnly();
        await flush();
        assert.equal(harness.submits.length, 0);
        assert.equal(harness.saveButton.disabled, true);

        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
        assert.equal(harness.saveButton.disabled, false);
        assert.equal(harness.modalCalls.shown, 0);

        // The body finally arrives, too late to matter.
        body.resolve([problem()]);
        await flush();
        assert.equal(harness.submits.length, 1);
        assert.equal(harness.modalCalls.shown, 0);
    });

    it("ignores a response body that fails after the deadline", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        const body = harness.requests[0].respondHeadersOnly();
        await flush();
        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();
        assert.equal(harness.submits.length, 1);

        body.reject();
        await flush();

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.modalCalls.shown, 0);
    });

    it("meets the deadline without a native AbortController", async () => {
        // Older browsers have `fetch` but no `AbortController`. The request
        // can't be cancelled there, but the user must still get their save.
        const harness = makeHarness({ abortController: undefined });
        harness.field.value = "Gloria # Deo";

        harness.submit();
        assert.equal(harness.requests[0].init.signal, undefined);

        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
        assert.equal(harness.saveButton.disabled, false);

        // The uncancelled request answers eventually; it must be ignored.
        harness.requests[0].respond([problem()]);
        await flush();
        assert.equal(harness.submits.length, 1);
        assert.equal(harness.modalCalls.shown, 0);
    });

    it("ignores the abandoned request failing after the deadline", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();

        // Aborting makes the browser's own fetch reject. That rejection has
        // nowhere left to go, and must neither submit again nor surface as an
        // unhandled rejection (which this runner fails the test for).
        harness.requests[0].fail();
        await flush();

        assert.equal(harness.submits.length, 1);
    });

    it("saves anyway when the endpoint can't be reached, and drops the deadline", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.requests[0].fail();
        await flush();

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
        assert.equal(harness.clock.pending(), 0);

        // A deadline left running would fire a second save.
        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();
        assert.equal(harness.submits.length, 1);
    });

    it("drops the deadline once the check answers in time", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria in excelsis Deo";

        harness.submit();
        harness.requests[0].respond([]);
        await flush();

        assert.equal(harness.clock.pending(), 0);
        harness.clock.tick(VALIDATION_TIMEOUT_MS);
        await flush();
        assert.equal(harness.submits.length, 1);
    });
});

describe("chant text validation: only what the user saw is acknowledged", () => {
    it("does not warn about text the user has already replaced", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        // The fields stay editable while the check runs.
        harness.field.value = "Gloria % Deo";
        harness.requests[0].respond([problem()]);
        await flush();

        // The problems describe the old text, so showing them would mark and
        // describe characters that are no longer there.
        assert.equal(harness.modalCalls.shown, 0);
        assert.equal(harness.echoFor(TEXT_FIELD), null);
        // The save still goes through, unacknowledged, so the server checks the
        // text it actually receives and warns about it.
        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
    });

    it("notices a replacement made without an input event", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        // The page's own helpers (the Cantus Index suggestion buttons) assign
        // to `.value` directly, so watching for edits would miss this.
        harness.field.value = "Gloria % Deo";
        harness.requests[0].respond([problem()]);
        await flush();

        assert.equal(harness.modalCalls.shown, 0);
        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
    });

    it("will not acknowledge a warning for text edited behind the dialog", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.requests[0].respond([problem()]);
        await flush();
        assert.equal(harness.modalCalls.shown, 1);

        // The dialog is open, but the field is still reachable. Whatever the
        // user does to it, they have not been warned about the result.
        harness.field.value = "Gloria % Deo";
        harness.saveAnywayButton.dispatch("click", {});

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "");
        // The markings described the old text and have to go with it.
        assert.equal(harness.echoFor(TEXT_FIELD), null);
    });

    it("still acknowledges the warning when the text is untouched", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();
        harness.requests[0].respond([problem()]);
        await flush();
        harness.saveAnywayButton.dispatch("click", {});

        assert.equal(harness.submits.length, 1);
        assert.equal(harness.submits[0].confirmInvalidText, "1");
    });
});

describe("chant text validation: the browser's own rules still apply", () => {
    it("checks again after the browser refuses the submit", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria in excelsis Deo";
        // A required field elsewhere on the form is empty, so the browser
        // refuses the programmatic submit and the user stays on the page.
        harness.nativeValidationBlocks = true;

        harness.submit();
        harness.requests[0].respond([]);
        await flush();
        assert.equal(harness.submits.length, 1);

        // Having fixed that field, the user saves again. The text has to be
        // checked again rather than waved through.
        harness.nativeValidationBlocks = false;
        harness.field.value = "Gloria # Deo";
        harness.submit();

        assert.equal(harness.requests.length, 2);
    });

    it("carries the clicked button through to the submit it makes", async () => {
        const harness = makeHarness();
        harness.field.value = "Gloria in excelsis Deo";

        harness.submit(harness.saveAndAnotherButton);
        harness.requests[0].respond([]);
        await flush();

        // Which button was pressed decides where the save goes next, so it has
        // to survive the detour through the check.
        assert.equal(harness.submits[0].submitter, harness.saveAndAnotherButton);
    });

    it("sends only the text fields the page actually has", () => {
        const harness = makeHarness();
        harness.field.value = "Gloria # Deo";

        harness.submit();

        const sent = new URLSearchParams(harness.requests[0].init.body);
        assert.deepEqual(Array.from(sent.keys()), [TEXT_FIELD]);
        assert.equal(sent.get(TEXT_FIELD), "Gloria # Deo");
        assert.equal(
            harness.requests[0].init.headers["X-CSRFToken"],
            "csrf-token"
        );
    });
});
