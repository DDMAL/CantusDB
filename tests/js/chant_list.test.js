"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "../../django/cantusdb_project/static/js/chant_list.js"), "utf8");
const fieldName = "manuscript_full_text_std_spelling";
const flush = () => new Promise(resolve => setImmediate(resolve));

// Exercise the shipped page script with a small DOM, fetch and timer stand-in.
// The local browser check separately covers real HTML, Celery and rendering.
function element() {
    const classes = new Set();
    return {
        value: "", textContent: "", children: [], disabled: false,
        listeners: {},
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
            toggle: name => classes.has(name) ? classes.delete(name) : classes.add(name),
        },
        addEventListener(type, callback) { this.listeners[type] = callback; },
        fire(type, event = {}) { this.listeners[type]?.(event); },
        appendChild(child) { this.children.push(child); child.parent = this; },
        replaceChildren() { this.children = []; },
        remove() { this.parent.children = this.parent.children.filter(child => child !== this); },
        insertAdjacentElement(_position, child) { this.parent.appendChild(child); },
        scrollIntoView() {},
    };
}

function harness() {
    const ids = new Map();
    const byId = id => {
        if (!ids.has(id)) ids.set(id, element());
        return ids.get(id);
    };
    byId("data-user-can-edit-chants").textContent = "true";
    const form = byId("bulkChantEditForm");
    const fields = [element(), element()];
    const names = fields.map((field, index) => {
        field.value = index ? "Kyrie !" : "Gloria ! Deo";
        form.appendChild(field);
        return `chant_set-${index}-${fieldName}`;
    });
    form.elements = { namedItem: name => fields[names.indexOf(name)] || null };
    byId("formsetTextWarningAlert").classList.add("d-none");
    const requests = [];
    const timers = [];
    let reloads = 0;
    const context = {
        window: {
            addEventListener: (_type, callback) => callback(),
            location: { href: "http://localhost/source/1/chants/", search: "", reload: () => reloads++ },
        },
        document: {
            URL: "http://localhost/source/1/chants/",
            getElementById: byId,
            querySelectorAll: () => [],
            createElement: () => element(),
        },
        URL, URLSearchParams,
        FormData: class {
            constructor() { this.values = new Map(names.map((name, index) => [name, fields[index].value])); }
            get(name) { return this.values.get(name); }
        },
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })),
        setTimeout: callback => timers.push(callback),
    };
    vm.runInNewContext(source, context);
    const h = {
        byId, form, fields, requests, timers,
        get reloads() { return reloads; },
        save: () => byId("bulkChantEditSubmit").fire("click"),
        async respond(request, data, status = 200) {
            request.resolve({ status, json: async () => data });
            await flush();
        },
        async start() {
            h.save();
            await h.respond(requests.at(-1), { taskID: "bulk-task" });
            timers.shift()();
        },
        async complete(result) {
            await h.respond(requests.at(-1), { status: "SUCCESS", result });
        },
    };
    return h;
}

function warning(form_num = 0) {
    return { form_num, field: fieldName, label: "Full text (standard spelling)", message: "contains nonstandard characters.", marked_html: "Gloria <mark>!</mark> Deo" };
}
function result(warnings = []) {
    return { error_count: 0, form_errors: [], non_form_errors: [], text_warnings: warnings };
}
function text(element) {
    return element.textContent + (element.innerText || "") + element.children.map(text).join("");
}

test("saved warnings stay visible, mark both rows, and Stop Editing refreshes saved values", async () => {
    const h = harness();
    await h.start();
    await h.complete(result([warning(0), warning(1)]));
    assert.equal(h.reloads, 0);
    const alert = h.byId("formsetTextWarningAlert");
    assert.match(text(alert), /Changes saved/);
    assert.match(text(alert), /Chant 1, Full text/);
    assert.match(text(alert), /Chant 2, Full text/);
    assert.equal(alert.classList.contains("d-none"), false);
    h.fields.forEach(field => assert.equal(field.classList.contains("chant-text-warning-field"), true));
    assert.equal(h.form.children[2].children[0].innerHTML, warning().marked_html);
    assert.equal(h.byId("bulkChantEditSubmit").disabled, false);
    h.byId("bulkChantEditToggle").fire("click");
    assert.equal(h.reloads, 1);
});

test("valid text and older task results retain successful reload behavior", async () => {
    for (const payload of [result(), { error_count: 0, form_errors: [], non_form_errors: [] }]) {
        const h = harness();
        await h.start();
        await h.complete(payload);
        assert.equal(h.reloads, 1);
        assert.equal(h.byId("formsetTextWarningAlert").classList.contains("d-none"), true);
    }
});

test("ordinary validation errors do not claim changes were saved", async () => {
    const h = harness();
    await h.start();
    await h.complete({ error_count: 2, non_form_errors: [{ message: "Missing form data" }], form_errors: [[1, "folio", "This field is required."]], text_warnings: [] });
    assert.equal(h.reloads, 0);
    assert.match(text(h.byId("formsetErrorAlert")), /Missing form data/);
    assert.match(text(h.byId("formsetErrorAlert")), /Error on chant 2, folio: This field is required/);
    assert.equal(h.byId("formsetTextWarningAlert").classList.contains("d-none"), true);
    assert.equal(h.byId("bulkChantEditSubmit").disabled, false);
});

test("text changed while saving is not marked with warnings about the old value", async () => {
    const h = harness();
    await h.start();
    h.fields[0].value = "Gloria in excelsis deo";
    await h.complete(result([warning()]));
    assert.match(text(h.byId("formsetTextWarningAlert")), /submitted chants/);
    assert.equal(h.fields[0].classList.contains("chant-text-warning-field"), false);
    assert.equal(h.form.children.length, 2);
    assert.equal(h.reloads, 0);
});

test("editing clears the stale echo and a second save clears the old warning", async () => {
    const h = harness();
    await h.start();
    await h.complete(result([warning()]));
    h.fields[0].value = "Gloria in excelsis deo";
    h.form.fire("input", { target: h.fields[0] });
    assert.equal(h.fields[0].classList.contains("chant-text-warning-field"), false);
    assert.equal(h.form.children.length, 2);
    await h.start();
    assert.equal(h.byId("formsetTextWarningAlert").classList.contains("d-none"), true);
    await h.complete(result());
    assert.equal(h.reloads, 1);
});

test("repeated saves and slow polls cannot consume a task result twice", async () => {
    const h = harness();
    await h.start();
    h.save();
    h.byId("bulkChantEditToggle").fire("click");
    assert.equal(h.requests.filter(request => request.options?.method === "POST").length, 1);
    assert.equal(h.byId("bulkChantEditSubmit").disabled, true);
    assert.equal(h.timers.length, 0);
    await h.respond(h.requests.at(-1), { status: "PROCESSING" });
    assert.equal(h.timers.length, 1);
    h.timers.shift()();
    await h.complete(result([warning()]));
    assert.equal(h.timers.length, 0);
});

test("a failed task or status request releases the save controls with an error", async () => {
    for (const failure of ["task", "network", "http"]) {
        const h = harness();
        await h.start();
        if (failure === "task") await h.respond(h.requests.at(-1), { status: "FAILURE" });
        if (failure === "network") { h.requests.at(-1).reject(new Error("offline")); await flush(); }
        if (failure === "http") await h.respond(h.requests.at(-1), {}, 500);
        assert.equal(h.byId("bulkChantEditSubmit").disabled, false);
        assert.equal(h.byId("bulkEditLoading").classList.contains("d-none"), true);
        assert.equal(h.byId("formsetErrorAlert").classList.contains("d-none"), false);
        assert.equal(h.reloads, 0);
        assert.equal(h.timers.length, 0);
    }
});

test("a failed submission releases controls and warning prose is inserted as text", async () => {
    const h = harness();
    h.save();
    await h.respond(h.requests[0], {}, 500);
    assert.equal(h.byId("bulkChantEditSubmit").disabled, false);
    assert.match(text(h.byId("formsetErrorAlert")), /Form submission failed/);
    await h.start();
    await h.complete(result([{ ...warning(), message: '<img src=x onerror="alert(1)">' }]));
    const item = h.byId("formsetTextWarningAlert").children[1].children[0];
    assert.match(item.textContent, /<img/);
    assert.equal(item.innerHTML, undefined);
});
