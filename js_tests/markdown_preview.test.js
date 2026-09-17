const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

// Drive the widget's actual listeners while controlling when HTTP replies arrive.
function harness() {
    function element() {
        return {
            listeners: {}, attrs: {}, style: {}, textContent: "", innerHTML: "",
            addEventListener(name, fn) { this.listeners[name] = fn; },
            setAttribute(name, value) { this.attrs[name] = value; },
            removeAttribute(name) { delete this.attrs[name]; },
        };
    }
    const textarea = Object.assign(element(), {
        value: "**unsaved**", clientHeight: 100,
        form: { querySelector: () => ({ value: "form-csrf-token" }) },
    });
    const preview = element(), previewTab = element(), editTab = element();
    const toolbar = Object.assign(element(), { getElementsByClassName: () => [] });
    const elements = {
        "markdown-textarea": textarea, "markdown-preview": preview,
        "preview-tab": previewTab, "edit-tab": editTab, "markdown-toolbar": toolbar,
    };
    const field = {
        getElementsByClassName: name => [elements[name]],
        getAttribute: name => name === "data-preview-url" ? "/markdown/preview/" : null,
    };
    const requests = [];
    const context = {
        AbortController, URLSearchParams,
        fetch(url, options) {
            return new Promise((resolve, reject) => requests.push({url, options, resolve, reject}));
        },
        document: {
            addEventListener() {},
            getElementsByClassName: () => [field],
        },
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.join(__dirname,
        "../django/cantusdb_project/static/js/markdown_widget.js"), "utf8"), context);
    context.MarkdownWidget.init();
    return {
        textarea, preview, toolbar, requests,
        show: () => previewTab.listeners["show.bs.tab"](),
        write: () => editTab.listeners["show.bs.tab"](),
    };
}

function reply(request, html) {
    request.resolve({ ok: true, json: async () => ({html}) });
}

test("Preview posts unsaved text and the form CSRF token to the server", async () => {
    const h = harness();
    const pending = h.show();
    const request = h.requests[0];
    assert.equal(request.url, "/markdown/preview/");
    assert.equal(request.options.method, "POST");
    assert.equal(request.options.mode, "same-origin");
    assert.equal(request.options.credentials, "same-origin");
    assert.equal(request.options.headers["X-CSRFToken"], "form-csrf-token");
    assert.equal(request.options.body.get("text"), "**unsaved**");
    assert.equal(h.preview.textContent, "Loading preview…");
    assert.equal(h.preview.attrs["aria-busy"], "true");
    reply(request, "<p><strong>unsaved</strong></p>");
    await pending;
    assert.equal(h.preview.innerHTML, "<p><strong>unsaved</strong></p>");
    assert.equal(h.preview.attrs["aria-busy"], undefined);
    assert.equal(h.textarea.value, "**unsaved**");
});

test("a slow old response cannot overwrite the newer preview", async () => {
    const h = harness();
    const first = h.show();
    h.write();
    h.textarea.value = "new text";
    const second = h.show();
    assert.equal(h.requests[0].options.signal.aborted, true);
    reply(h.requests[1], "<p>new text</p>");
    await second;
    reply(h.requests[0], "<p>old text</p>");
    await first;
    assert.equal(h.preview.innerHTML, "<p>new text</p>");
});

test("returning to Write cancels Preview and restores the toolbar", async () => {
    const h = harness();
    const pending = h.show();
    h.write();
    assert.equal(h.requests[0].options.signal.aborted, true);
    assert.equal(h.toolbar.style.visibility, "visible");
    reply(h.requests[0], "<p>cancelled</p>");
    await pending;
    assert.equal(h.preview.innerHTML, "");
});

test("failed requests preserve the draft, show an error, and allow retry", async () => {
    for (const failure of ["http", "network", "invalid-json", "missing-html"]) {
        const h = harness();
        const pending = h.show();
        const request = h.requests[0];
        if (failure === "network") request.reject(new Error("offline"));
        else if (failure === "http") request.resolve({ok: false});
        else request.resolve({ok: true, json: async () => {
            if (failure === "invalid-json") throw new Error("login HTML");
            return {};
        }});
        await pending;
        assert.match(h.preview.textContent, /Preview could not be loaded/);
        assert.equal(h.preview.innerHTML, "");
        assert.equal(h.preview.attrs["aria-busy"], undefined);
        assert.equal(h.textarea.value, "**unsaved**");
        h.write();
        const retry = h.show();
        reply(h.requests[1], "<p>retry succeeded</p>");
        await retry;
        assert.equal(h.preview.innerHTML, "<p>retry succeeded</p>");
    }
});
