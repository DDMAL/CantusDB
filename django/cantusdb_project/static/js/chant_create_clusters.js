/*
 * Chant cluster prototype (issue #2128) — enhancement to the Create Chant page.
 *
 * Turns the "Full text (standardized spelling)" field into an element composer.
 * A chant cluster's full text is an ordered sequence of typed elements, each
 * carrying its own text and Cantus ID (position is just the order in the field):
 *
 *   - core elements   — chunks of the base chant's own text (share the base
 *                        Cantus ID), pre-filled when a cluster is selected and
 *                        NOT removable (the base text must stay intact).
 *   - general elements — troped/added, reusable, each with its own Cantus ID.
 *                        Revealed by "Has general elements"; found by TYPING in
 *                        the field, which offers a dropdown to insert one inline
 *                        between the core chunks (or before/after them).
 *
 * Only elements count: free text typed into the field is just a search query for
 * the dropdown. It is never saved (the hidden textarea is built from tokens only)
 * and is discarded when it isn't turned into an element.
 *
 * Data is hardcoded for now. Eventually the clusters come from a table, and the
 * typeahead can query Cantus Index live (its /json-text endpoint already backs
 * the sidebar "Input Tool") instead of this local demo pool. Cantus IDs below
 * are illustrative and not musicologically vetted.
 */
(function () {
    "use strict";

    // Anna's #2128 examples both trope the same base chant (g02711), so they
    // share a general-element pool but split the base text differently.
    const G02711_TROPES = [
        { id: "g-tp7", text: "Hodie regi archangelorum laudes promamus cum psalmista", cantusId: "g02711.Tp7" },
        { id: "g-tp8", text: "Ipsum collaudantes in quem cernere cupitis semper", cantusId: "g02711.Tp8" },
        { id: "g-tp9", text: "Vim habentes divinam per quam geritis mirabiles res", cantusId: "g02711.Tp9" },
        { id: "g-tp10", text: "Adimplentes jussa jugiter domini", cantusId: "g02711.Tp10" },
        { id: "g-36", text: "Humani superas jungentes vocibus odas", cantusId: "g02711.36" },
        { id: "g-37", text: "Et vos concentu pariter celebrate faventes", cantusId: "g02711.37" },
        { id: "g-38", text: "Nuntia dum geritis per quae bene corda paratis", cantusId: "g02711.38" },
    ];

    const CLUSTER_DEMO_DATA = [
        {
            // Anna's first worked example: g02711 troped for St Michael, split 4 ways.
            key: "g02711-ex1",
            label: "g02711 Benedicite domino (troped, ex. 1)",
            baseCantusId: "g02711",
            core: [
                { id: "c-g02711a-1", text: "Benedicite domino omnes angeli ejus", cantusId: "g02711" },
                { id: "c-g02711a-2", text: "Potentes virtutes", cantusId: "g02711" },
                { id: "c-g02711a-3", text: "Qui facitis verbum ejus", cantusId: "g02711" },
                { id: "c-g02711a-4", text: "ad audiendam vocem sermonum ejus", cantusId: "g02711" },
            ],
            general: G02711_TROPES,
        },
        {
            // Anna's second example: same base chant, but it does not divide before
            // "qui facitis", so that word stays in the second core chunk. Three chunks.
            key: "g02711-ex2",
            label: "g02711 Benedicite domino (troped, ex. 2)",
            baseCantusId: "g02711",
            core: [
                { id: "c-g02711b-1", text: "Benedicite domino omnes angeli ejus", cantusId: "g02711" },
                { id: "c-g02711b-2", text: "Potentes virtutes qui facitis", cantusId: "g02711" },
                { id: "c-g02711b-3", text: "Ad audiendam vocem sermonum ejus", cantusId: "g02711" },
            ],
            general: G02711_TROPES,
        },
        {
            key: "kyrie-trope",
            label: "Kyrie eleison (troped)",
            baseCantusId: "g02549",
            core: [
                { id: "c-kyrie-1", text: "Kyrie", cantusId: "g02549" },
                { id: "c-eleison-1", text: "eleison", cantusId: "g02549" },
                { id: "c-christe", text: "Christe", cantusId: "g02549" },
                { id: "c-eleison-2", text: "eleison", cantusId: "g02549" },
                { id: "c-kyrie-2", text: "Kyrie", cantusId: "g02549" },
                { id: "c-eleison-3", text: "eleison", cantusId: "g02549" },
            ],
            general: [
                { id: "g-fons-bonitatis", text: "fons bonitatis", cantusId: "g02549.Tp1" },
                { id: "g-pater-ingenite", text: "pater ingenite", cantusId: "g02549.Tp2" },
                { id: "g-a-quo-cuncta", text: "a quo bona cuncta procedunt", cantusId: "g02549.Tp3" },
                { id: "g-magne-deus", text: "magnae potentiae", cantusId: "g02549.Tp4" },
                { id: "g-rex-genitor", text: "rex genitor", cantusId: "g02549.Tp5" },
            ],
        },
        {
            key: "hymn-veni-creator",
            label: "Hymn: Veni Creator Spiritus",
            baseCantusId: "830142",
            core: [
                { id: "c-vc-1", text: "Veni Creator Spiritus, mentes tuorum visita", cantusId: "830142" },
                { id: "c-vc-2", text: "Imple superna gratia quae tu creasti pectora", cantusId: "830142" },
                { id: "c-vc-3", text: "Qui Paraclitus diceris, donum Dei altissimi", cantusId: "830142" },
            ],
            general: [
                { id: "g-dox-deo-patri", text: "Deo Patri sit gloria, et Filio qui a mortuis surrexit, ac Paraclito", cantusId: "909030" },
                { id: "g-dox-sit-laus", text: "Sit laus Deo Patri, summo Christo decus, Spiritui Sancto honor unus", cantusId: "909031" },
                { id: "g-gloria-patri", text: "Gloria Patri et Filio et Spiritui Sancto", cantusId: "909000" },
                { id: "g-amen", text: "Amen", cantusId: "909999" },
            ],
        },
    ];

    const MIN_QUERY = 2; // characters before the typeahead offers suggestions
    const MAX_MATCHES = 8;

    let textarea, composer, select, hasGeneralCheckbox, hint;
    let currentCluster = null;

    // inline typeahead state
    let typeahead = null; // the floating <ul> (created once, appended to body)
    let taMatches = [];
    let taActiveIndex = 0;
    let taContext = null; // { node, offset, leadWs } — where a picked element gets inserted

    // ---- tokens ---------------------------------------------------------

    function makeToken(kind, element) {
        const token = document.createElement("span");
        token.className = "cluster-token cluster-token--" + kind;
        token.contentEditable = "false";
        token.dataset.kind = kind;
        token.dataset.elementId = element.id;
        token.dataset.text = element.text;
        token.dataset.cantusId = element.cantusId;

        const label = document.createElement("span");
        label.className = "token-label";
        label.textContent = element.text;

        const cid = document.createElement("span");
        cid.className = "token-cid";
        cid.textContent = element.cantusId;
        cid.title = "Cantus ID";
        token.append(label, cid);

        // core elements are part of the base chant and cannot be removed
        if (kind === "general") {
            const remove = document.createElement("span");
            remove.className = "token-remove";
            remove.textContent = "×";
            remove.title = "Remove element";
            remove.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                token.remove();
                syncToTextarea();
            });
            token.append(remove);
        }
        return token;
    }

    function isCoreToken(node) {
        return !!(node && node.classList && node.classList.contains("cluster-token--core"));
    }

    // Insert a token at a collapsed range, padding with spaces so words stay
    // separated and a caret can sit on either side. Returns the trailing space
    // node so callers can place the caret after the token.
    function insertTokenAtRange(range, token) {
        range.insertNode(token);
        const after = document.createTextNode(" ");
        token.after(after);
        token.before(document.createTextNode(" "));
        return after;
    }

    function placeCaretAfter(node) {
        const sel = window.getSelection();
        const caret = document.createRange();
        caret.setStart(node, node.length);
        caret.collapse(true);
        sel.removeAllRanges();
        sel.addRange(caret);
    }

    // ---- sync to the real form field ------------------------------------

    // Only element tokens are submitted; free text is a transient search query.
    function syncToTextarea() {
        const parts = [];
        composer.querySelectorAll(".cluster-token").forEach(function (token) {
            parts.push(token.dataset.text);
        });
        textarea.value = parts.join(" ").replace(/\s+/g, " ").trim();
    }

    // Drop any stray free text, keeping only the tokens separated by single
    // spaces, so the field shows exactly what will be saved.
    function normalizeComposer() {
        const tokens = Array.from(composer.querySelectorAll(".cluster-token"));
        composer.innerHTML = "";
        tokens.forEach(function (token, i) {
            if (i > 0) composer.appendChild(document.createTextNode(" "));
            composer.appendChild(token);
        });
        composer.appendChild(document.createTextNode(" "));
        syncToTextarea();
    }

    // ---- activate / deactivate ------------------------------------------

    function activateCluster(cluster) {
        currentCluster = cluster;
        composer.innerHTML = "";
        cluster.core.forEach(function (element, i) {
            if (i > 0) composer.appendChild(document.createTextNode(" "));
            composer.appendChild(makeToken("core", element));
        });
        composer.appendChild(document.createTextNode(" "));
        textarea.style.display = "none";
        composer.hidden = false;
        hint.hidden = !hasGeneralCheckbox.checked;
        syncToTextarea();
    }

    function deactivateCluster() {
        normalizeComposer(); // preserve composed elements back into the textarea
        closeTypeahead();
        composer.hidden = true;
        textarea.style.display = "";
        currentCluster = null;
        hint.hidden = true;
    }

    // ---- inline typeahead for general elements --------------------------

    // The free text typed since the previous token/line start, up to the caret.
    // Returns null when the caret isn't sitting in an editable text run.
    function currentQueryContext() {
        const sel = window.getSelection();
        if (!sel.rangeCount) return null;
        const range = sel.getRangeAt(0);
        if (!range.collapsed) return null;
        const node = range.startContainer;
        if (node.nodeType !== Node.TEXT_NODE || !composer.contains(node)) return null;
        const before = node.nodeValue.slice(0, range.startOffset);
        const leadWs = before.match(/^\s*/)[0];
        return { node: node, offset: range.startOffset, leadWs: leadWs, query: before.slice(leadWs.length) };
    }

    function findMatches(query) {
        const q = query.trim().toLowerCase();
        if (q.length < MIN_QUERY || !currentCluster) return [];
        return currentCluster.general
            .filter(function (e) {
                return e.text.toLowerCase().includes(q) || e.cantusId.toLowerCase().includes(q);
            })
            .slice(0, MAX_MATCHES);
    }

    function renderTypeahead() {
        typeahead.innerHTML = "";
        taMatches.forEach(function (element, i) {
            const li = document.createElement("li");
            li.className = "typeahead-item" + (i === taActiveIndex ? " active" : "");
            const label = document.createElement("span");
            label.className = "typeahead-label";
            label.textContent = element.text;
            const cid = document.createElement("span");
            cid.className = "typeahead-cid";
            cid.textContent = element.cantusId;
            li.append(label, cid);
            // mousedown (not click) so the composer keeps focus and the caret/context
            li.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectMatch(i);
            });
            typeahead.appendChild(li);
        });
    }

    function positionTypeahead() {
        const sel = window.getSelection();
        if (!sel.rangeCount) return;
        let rect = sel.getRangeAt(0).getBoundingClientRect();
        if (!rect.height && !rect.width && !rect.top) {
            rect = composer.getBoundingClientRect(); // fallback when a collapsed caret has no box
        }
        typeahead.style.left = rect.left + "px";
        typeahead.style.top = rect.bottom + "px";
    }

    function openTypeahead(matches, context) {
        taMatches = matches;
        taContext = context;
        taActiveIndex = 0;
        renderTypeahead();
        positionTypeahead();
        typeahead.hidden = false;
    }

    function closeTypeahead() {
        typeahead.hidden = true;
        taMatches = [];
        taContext = null;
    }

    function isTypeaheadOpen() {
        return !typeahead.hidden;
    }

    function moveActive(delta) {
        if (!taMatches.length) return;
        taActiveIndex = (taActiveIndex + delta + taMatches.length) % taMatches.length;
        renderTypeahead();
    }

    // Replace the typed query with the chosen general element as an inline token.
    function selectMatch(index) {
        const element = taMatches[index];
        if (!element || !taContext) return closeTypeahead();
        const ctx = taContext;
        // drop the typed query text, keeping any leading whitespace and the tail
        ctx.node.nodeValue = ctx.leadWs + ctx.node.nodeValue.slice(ctx.offset);
        const range = document.createRange();
        range.setStart(ctx.node, ctx.leadWs.length);
        range.collapse(true);
        const trailingSpace = insertTokenAtRange(range, makeToken("general", element));
        placeCaretAfter(trailingSpace);
        closeTypeahead();
        syncToTextarea();
    }

    function onComposerInput() {
        syncToTextarea();
        if (!(currentCluster && hasGeneralCheckbox.checked)) {
            closeTypeahead();
            return;
        }
        const context = currentQueryContext();
        const matches = context ? findMatches(context.query) : [];
        if (matches.length) {
            openTypeahead(matches, context);
        } else {
            closeTypeahead();
        }
    }

    // ---- protect core tokens from deletion ------------------------------

    function nodeBeforeCaret(range) {
        const c = range.startContainer;
        const o = range.startOffset;
        if (c.nodeType === Node.TEXT_NODE) return o === 0 ? c.previousSibling : null;
        return o > 0 ? c.childNodes[o - 1] : null;
    }

    function nodeAfterCaret(range) {
        const c = range.startContainer;
        const o = range.startOffset;
        if (c.nodeType === Node.TEXT_NODE) return o === c.length ? c.nextSibling : null;
        return c.childNodes[o] || null;
    }

    function rangeHitsCore(range) {
        const cores = composer.querySelectorAll(".cluster-token--core");
        for (let i = 0; i < cores.length; i++) {
            if (range.intersectsNode(cores[i])) return true;
        }
        return false;
    }

    function onBeforeInput(e) {
        const sel = window.getSelection();
        if (!sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        if (!range.collapsed) {
            // typing over / cutting / deleting a selection that includes a core token
            if (rangeHitsCore(range)) e.preventDefault();
            return;
        }
        const t = e.inputType || "";
        if (t === "deleteContentBackward" || t === "deleteWordBackward") {
            if (isCoreToken(nodeBeforeCaret(range))) e.preventDefault();
        } else if (t === "deleteContentForward" || t === "deleteWordForward") {
            if (isCoreToken(nodeAfterCaret(range))) e.preventDefault();
        }
    }

    // ---- wiring ---------------------------------------------------------

    function wire() {
        select.addEventListener("change", function () {
            const cluster = CLUSTER_DEMO_DATA.find((c) => c.key === select.value);
            if (cluster) {
                activateCluster(cluster);
            } else {
                deactivateCluster();
            }
        });

        hasGeneralCheckbox.addEventListener("change", function () {
            hint.hidden = !(hasGeneralCheckbox.checked && currentCluster);
            if (!hasGeneralCheckbox.checked) closeTypeahead();
        });

        composer.addEventListener("input", onComposerInput);
        composer.addEventListener("beforeinput", onBeforeInput);

        composer.addEventListener("keydown", function (e) {
            if (isTypeaheadOpen()) {
                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    moveActive(1);
                    return;
                }
                if (e.key === "ArrowUp") {
                    e.preventDefault();
                    moveActive(-1);
                    return;
                }
                if (e.key === "Enter") {
                    e.preventDefault();
                    selectMatch(taActiveIndex);
                    return;
                }
                if (e.key === "Escape") {
                    e.preventDefault();
                    closeTypeahead();
                    return;
                }
            }
            // keep the field a single flowing line; no stray newlines
            if (e.key === "Enter") e.preventDefault();
        });

        // dropping the typeahead / discarding unresolved free text when focus leaves
        composer.addEventListener("blur", function () {
            // defer so a mousedown on a typeahead item can fire first
            window.setTimeout(function () {
                closeTypeahead();
                if (currentCluster) normalizeComposer();
            }, 0);
        });

        window.addEventListener("scroll", function () {
            if (isTypeaheadOpen()) positionTypeahead();
        }, true);
        window.addEventListener("resize", function () {
            if (isTypeaheadOpen()) positionTypeahead();
        });

        // guarantee the submitted value is the composed elements, not stray text
        const form = composer.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                if (currentCluster) normalizeComposer();
            });
        }
    }

    function init() {
        textarea = document.getElementById("id_manuscript_full_text_std_spelling");
        composer = document.getElementById("cluster-composer");
        select = document.getElementById("cluster-select");
        hasGeneralCheckbox = document.getElementById("has-general-elements");
        hint = document.getElementById("general-elements-hint");
        const controls = document.getElementById("cluster-controls");
        if (!textarea || !composer || !select || !controls) return;

        typeahead = document.createElement("ul");
        typeahead.id = "element-typeahead";
        typeahead.className = "element-typeahead";
        typeahead.hidden = true;
        document.body.appendChild(typeahead);

        CLUSTER_DEMO_DATA.forEach(function (cluster) {
            const opt = document.createElement("option");
            opt.value = cluster.key;
            opt.textContent = cluster.label;
            select.appendChild(opt);
        });

        controls.hidden = false; // reveal now that JS is running (progressive enhancement)
        wire();
    }

    document.addEventListener("DOMContentLoaded", init);
})();
