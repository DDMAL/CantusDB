/*
 * Chant cluster prototype (issues #2128 / #2129) — enhancement to the Create
 * Chant page.
 *
 * Turns the "Full text (standardized spelling)" field into an element composer.
 * A chant cluster's full text is an ordered sequence of typed elements; position
 * is just the order in the field:
 *
 *   - core elements      — chunks of the base chant's own text. They carry the
 *                          cluster's (parent) Cantus ID, e.g. g04828. Pre-filled
 *                          when a cluster is selected. Deletable, but deleting one
 *                          is a deliberate act (click the box → red Delete): the
 *                          removed core drops into a restore tray and Undo reverts
 *                          it. A core can also be SPLIT into two cores.
 *   - component elements — troped/added, reusable, found by TYPING in the field
 *                          (a filtered dropdown inserts one inline). Each carries
 *                          its OWN Cantus ID exactly as retrieved from Cantus Index
 *                          — e.g. g04828:01 (a sub-ID of the parent) or a wholly
 *                          separate ID like a shared doxology's 909030. IDs are
 *                          NEVER computed here. A component the user PROPOSES (not
 *                          yet in CI) shows no ID; the backend assigns one later
 *                          (for the g04828 cluster it would be g04828:XXXXXX).
 *
 * Only elements are saved: free text typed into the field is just a search query
 * for the dropdown. It is discarded when it isn't turned into an element (the
 * hidden textarea is built from tokens only).
 *
 * Data is hardcoded for now. Eventually clusters come from a table and the
 * typeahead can query Cantus Index live (its /json-text endpoint already backs
 * the sidebar "Input Tool"). Cantus IDs below are illustrative, except g04828,
 * which is copied from Cantus Index.
 */
(function () {
    "use strict";

    // Two of Anna's #2128 examples trope the same base chant (g02711); they share
    // a component pool but split the base text differently.
    // Cantus IDs here stand in for what Cantus Index would return; they are fixed
    // per component (not computed). Illustrative only — the real ones come from CI.
    const G02711_TROPES = [
        { id: "g-tp7", text: "Hodie regi archangelorum laudes promamus cum psalmista", cantusId: "g02711:07" },
        { id: "g-tp8", text: "Ipsum collaudantes in quem cernere cupitis semper", cantusId: "g02711:08" },
        { id: "g-tp9", text: "Vim habentes divinam per quam geritis mirabiles res", cantusId: "g02711:09" },
        { id: "g-tp10", text: "Adimplentes jussa jugiter domini", cantusId: "g02711:10" },
        { id: "g-36", text: "Humani superas jungentes vocibus odas", cantusId: "g02711:36" },
        { id: "g-37", text: "Et vos concentu pariter celebrate faventes", cantusId: "g02711:37" },
        { id: "g-38", text: "Nuntia dum geritis per quae bene corda paratis", cantusId: "g02711:38" },
    ];

    const CLUSTER_DEMO_DATA = [
        {
            // Copied from cantusindex.org/id/g04828 (troped Sanctus, genre TpSa):
            // its four tropes are numbered g04828:01–04. The user's "clean example".
            key: "g04828-sanctus",
            label: "g04828 Sanctus (troped) — cantusindex.org/id/g04828",
            parentCantusId: "g04828",
            core: [
                { id: "c-04828-1", text: "Sanctus" },
                { id: "c-04828-2", text: "Sanctus" },
                { id: "c-04828-3", text: "Sanctus" },
                { id: "c-04828-4", text: "Dominus Deus Sabaoth" },
                { id: "c-04828-5", text: "Pleni sunt caeli et terra gloria tua" },
                { id: "c-04828-6", text: "Hosanna in excelsis" },
                { id: "c-04828-7", text: "Benedictus qui venit in nomine Domini" },
                { id: "c-04828-8", text: "Hosanna in excelsis" },
            ],
            component: [
                { id: "g-04828-a", text: "Perpetuo numine cuncta regens", cantusId: "g04828:01" },
                { id: "g-04828-b", text: "Regna patris disponens jure parili", cantusId: "g04828:02" },
                { id: "g-04828-c", text: "Consimilis qui bona cuncta nutris", cantusId: "g04828:03" },
                { id: "g-04828-d", text: "O deitas clemens servorum suscipe laudes", cantusId: "g04828:04" },
            ],
        },
        {
            // Anna's first worked example: g02711 troped for St Michael, split 4 ways.
            key: "g02711-ex1",
            label: "g02711 Benedicite domino (troped, ex. 1)",
            parentCantusId: "g02711",
            core: [
                { id: "c-g02711a-1", text: "Benedicite domino omnes angeli ejus" },
                { id: "c-g02711a-2", text: "Potentes virtutes" },
                { id: "c-g02711a-3", text: "Qui facitis verbum ejus" },
                { id: "c-g02711a-4", text: "ad audiendam vocem sermonum ejus" },
            ],
            component: G02711_TROPES,
        },
        {
            // Anna's second example: same base chant, but it does not divide before
            // "qui facitis", so that word stays in the second core chunk. Three chunks.
            key: "g02711-ex2",
            label: "g02711 Benedicite domino (troped, ex. 2)",
            parentCantusId: "g02711",
            core: [
                { id: "c-g02711b-1", text: "Benedicite domino omnes angeli ejus" },
                { id: "c-g02711b-2", text: "Potentes virtutes qui facitis" },
                { id: "c-g02711b-3", text: "Ad audiendam vocem sermonum ejus" },
            ],
            component: G02711_TROPES,
        },
        {
            key: "kyrie-trope",
            label: "Kyrie eleison (troped)",
            parentCantusId: "g02549",
            core: [
                { id: "c-kyrie-1", text: "Kyrie" },
                { id: "c-eleison-1", text: "eleison" },
                { id: "c-christe", text: "Christe" },
                { id: "c-eleison-2", text: "eleison" },
                { id: "c-kyrie-2", text: "Kyrie" },
                { id: "c-eleison-3", text: "eleison" },
            ],
            component: [
                { id: "g-fons-bonitatis", text: "fons bonitatis", cantusId: "g02549:01" },
                { id: "g-pater-ingenite", text: "pater ingenite", cantusId: "g02549:02" },
                { id: "g-a-quo-cuncta", text: "a quo bona cuncta procedunt", cantusId: "g02549:03" },
                { id: "g-magne-deus", text: "magnae potentiae", cantusId: "g02549:04" },
                { id: "g-rex-genitor", text: "rex genitor", cantusId: "g02549:05" },
            ],
        },
        {
            key: "hymn-veni-creator",
            label: "Hymn: Veni Creator Spiritus",
            parentCantusId: "830142",
            core: [
                { id: "c-vc-1", text: "Veni Creator Spiritus, mentes tuorum visita" },
                { id: "c-vc-2", text: "Imple superna gratia quae tu creasti pectora" },
                { id: "c-vc-3", text: "Qui Paraclitus diceris, donum Dei altissimi" },
            ],
            // Doxologies are shared chants with their OWN Cantus IDs — not sub-IDs of
            // the hymn — showing that a component's ID need not match the parent.
            component: [
                { id: "g-dox-deo-patri", text: "Deo Patri sit gloria, et Filio qui a mortuis surrexit, ac Paraclito", cantusId: "909030" },
                { id: "g-dox-sit-laus", text: "Sit laus Deo Patri, summo Christo decus, Spiritui Sancto honor unus", cantusId: "909031" },
                { id: "g-gloria-patri", text: "Gloria Patri et Filio et Spiritui Sancto", cantusId: "909000" },
                { id: "g-amen", text: "Amen", cantusId: "909999" },
            ],
        },
    ];

    const MAX_MATCHES = 8;
    const MAX_UNDO = 50;
    const CI_MIN_QUERY = 3; // characters before we query Cantus Index (matches the Input Tool)
    const CI_DEBOUNCE_MS = 250; // wait for a typing pause before firing a request

    let textarea, composer, select, hasComponentCheckbox, hint, undoButton, tray;
    let currentCluster = null;

    // inline typeahead state
    let typeahead = null; // the floating <ul> (created once, appended to body)
    let taRows = []; // navigable rows: component matches + a "propose new" action
    let taActiveIndex = -1;
    let taContext = null; // where a picked element gets inserted (text node or element boundary)

    // live Cantus Index search state
    const ciCache = new Map(); // normalized query -> results array (session cache)
    let ciAbort = null; // AbortController for the in-flight request
    let ciDebounce = null; // pending debounce timer
    let ciSeq = 0; // monotonic guard so an old response can't clobber a newer one

    // token action menu ("click a box" → floating remove/split control)
    let tokenMenu = null;
    let menuToken = null;

    let removedCores = []; // { id, text, index } — the restore tray's contents
    let undoStack = []; // snapshots captured *before* each mutation

    // ---- tokens ---------------------------------------------------------

    // A token is an atomic, non-editable inline unit. It is draggable (reorder)
    // and clickable (its action menu). No per-token listeners: everything is
    // delegated on the composer, so rebuilding innerHTML (undo, normalize) is safe.
    // `proposed` marks a component the user is proposing to Cantus Index. It's a
    // backend-only flag (data-proposed) — in the UI a proposed component looks and
    // behaves exactly like any other component (same :NN, menu, drag, undo).
    function makeToken(kind, text, cantusId, proposed) {
        const token = document.createElement("span");
        token.className = "cluster-token cluster-token--" + kind;
        token.contentEditable = "false";
        token.draggable = true;
        token.dataset.kind = kind;
        token.dataset.text = text;
        token.dataset.cantusId = cantusId || "";
        if (proposed) token.dataset.proposed = "true";

        const label = document.createElement("span");
        label.className = "token-label";
        label.textContent = text;

        const cid = document.createElement("span");
        cid.className = "token-cid";
        cid.textContent = cantusId || "";
        cid.title = "Cantus ID";

        token.append(label, cid);
        return token;
    }

    function makeCoreToken(text) {
        return makeToken("core", text, currentCluster ? currentCluster.parentCantusId : "");
    }

    function isToken(node) {
        return !!(node && node.classList && node.classList.contains("cluster-token"));
    }

    function isCoreToken(node) {
        return !!(node && node.classList && node.classList.contains("cluster-token--core"));
    }

    function isProposedToken(node) {
        return !!(node && node.dataset && node.dataset.proposed === "true");
    }

    // Core chunks and not-yet-catalogued proposed components can be split into two
    // of the same kind. An approved component carries a real Cantus ID for its whole
    // text, so it is delete-only — splitting it would break that identity.
    function isSplittable(node) {
        return isCoreToken(node) || isProposedToken(node);
    }

    function allTokens() {
        return Array.from(composer.querySelectorAll(".cluster-token"));
    }

    // Insert a token at a collapsed range, padded with spaces so words stay
    // separated. Returns the trailing space node so callers can place the caret.
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

    // Drop any stray free text, keeping only tokens separated by single spaces,
    // so the field shows exactly what will be saved. (Loses the caret; only used
    // after structural edits, blur and submit — not mid-typing.)
    function normalizeComposer() {
        const tokens = allTokens();
        composer.innerHTML = "";
        tokens.forEach(function (token, i) {
            if (i > 0) composer.appendChild(document.createTextNode(" "));
            composer.appendChild(token);
        });
        composer.appendChild(document.createTextNode(" "));
        syncToTextarea();
    }

    // ---- undo -----------------------------------------------------------

    // Snapshot the composer + tray *before* a mutation; Undo restores the top.
    function pushUndo() {
        undoStack.push({ html: composer.innerHTML, cores: removedCores.slice() });
        if (undoStack.length > MAX_UNDO) undoStack.shift();
        updateUndoButton();
    }

    function undo() {
        const snapshot = undoStack.pop();
        if (!snapshot) return;
        closeMenu();
        composer.innerHTML = snapshot.html;
        removedCores = snapshot.cores;
        renderTray();
        syncToTextarea();
        updateUndoButton();
    }

    function updateUndoButton() {
        if (!undoButton) return;
        undoButton.disabled = undoStack.length === 0;
    }

    // ---- restore tray ---------------------------------------------------

    function renderTray() {
        if (!tray) return;
        tray.innerHTML = "";
        if (!removedCores.length) {
            tray.hidden = true;
            return;
        }
        const label = document.createElement("span");
        label.className = "tray-label";
        label.textContent = "Removed core elements (click to restore):";
        tray.appendChild(label);
        removedCores.forEach(function (core, i) {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "tray-chip";
            chip.textContent = core.text;
            chip.title = "Restore this core element";
            chip.dataset.trayIndex = String(i);
            tray.appendChild(chip);
        });
        tray.hidden = false;
    }

    function restoreCore(trayIndex) {
        const core = removedCores[trayIndex];
        if (!core) return;
        pushUndo();
        const token = makeCoreToken(core.text);
        const tokens = allTokens();
        const at = Math.min(core.index, tokens.length);
        if (at >= tokens.length) {
            composer.appendChild(token);
        } else {
            composer.insertBefore(token, tokens[at]);
        }
        removedCores.splice(trayIndex, 1);
        normalizeComposer();
        renderTray();
    }

    // ---- activate / deactivate ------------------------------------------

    function activateCluster(cluster) {
        currentCluster = cluster;
        removedCores = [];
        undoStack = [];
        composer.innerHTML = "";
        cluster.core.forEach(function (element, i) {
            if (i > 0) composer.appendChild(document.createTextNode(" "));
            composer.appendChild(makeCoreToken(element.text));
        });
        composer.appendChild(document.createTextNode(" "));
        textarea.style.display = "none";
        composer.hidden = false;
        hint.hidden = !hasComponentCheckbox.checked;
        if (undoButton) undoButton.hidden = false;
        renderTray();
        updateUndoButton();
        syncToTextarea();
    }

    function deactivateCluster() {
        exitSplitMode();
        closeMenu();
        normalizeComposer(); // preserve composed elements back into the textarea
        closeTypeahead();
        composer.hidden = true;
        textarea.style.display = "";
        currentCluster = null;
        removedCores = [];
        undoStack = [];
        hint.hidden = true;
        if (undoButton) undoButton.hidden = true;
        renderTray();
    }

    // ---- inline typeahead for component elements ------------------------

    // Where a picked component gets inserted, plus the free text typed there (the
    // search query). Handles the caret sitting inside a text run *or* at an element
    // boundary between tokens (e.g. right after clicking into the field), so the
    // dropdown can appear with nothing typed yet.
    function currentQueryContext() {
        const sel = window.getSelection();
        if (!sel.rangeCount) return null;
        const range = sel.getRangeAt(0);
        if (!range.collapsed) return null;
        const node = range.startContainer;
        if (node !== composer && !composer.contains(node)) return null;
        if (node.nodeType === Node.TEXT_NODE) {
            const before = node.nodeValue.slice(0, range.startOffset);
            const leadWs = before.match(/^\s*/)[0];
            return { textNode: node, offset: range.startOffset, leadWs: leadWs, query: before.slice(leadWs.length) };
        }
        // element-node caret (between tokens): no typed query, insert right here
        return { elementNode: node, offset: range.startOffset, leadWs: "", query: "" };
    }

    // Local, per-cluster component pool — the offline fallback used only when
    // Cantus Index can't be reached (see refreshTypeahead). Ranks by where the query
    // lands: text start first, then a word start, then anywhere. Stable within tiers.
    function findMatches(query) {
        const q = query.trim().toLowerCase();
        if (!currentCluster || !q) return [];
        const scored = [];
        currentCluster.component.forEach(function (e, i) {
            const text = e.text.toLowerCase();
            const idx = text.indexOf(q);
            if (idx < 0) return;
            const rank = idx === 0 ? 0 : /\s/.test(text.charAt(idx - 1)) ? 1 : 2;
            scored.push({ e: e, rank: rank, i: i });
        });
        scored.sort(function (a, b) {
            return a.rank - b.rank || a.i - b.i;
        });
        return scored.slice(0, MAX_MATCHES).map(function (s) {
            return s.e;
        });
    }

    // Float this cluster's own sub-elements (Cantus IDs like "<parent>:NN" or
    // "<parent>.Tp7") to the top, keeping CI's order within each group — search all
    // of Cantus Index, but surface the obvious in-cluster ones first.
    function rankResults(results) {
        if (!currentCluster) return results;
        const parent = currentCluster.parentCantusId;
        const own = [];
        const rest = [];
        results.forEach(function (r) {
            const cid = r.cid || "";
            if (cid.indexOf(parent + ":") === 0 || cid.indexOf(parent + ".") === 0) {
                own.push(r);
            } else {
                rest.push(r);
            }
        });
        return own.concat(rest);
    }

    // Live CI results (+ an always-present "propose new" row) → dropdown rows. CI's
    // fulltext carries trailing whitespace, so trim it before it becomes a token.
    function rowsFromResults(results, query) {
        const rows = rankResults(results)
            .slice(0, MAX_MATCHES)
            .map(function (r) {
                return {
                    kind: "match",
                    element: { text: (r.fulltext || "").trim(), cantusId: r.cid || "" },
                };
            });
        rows.push({ kind: "propose", text: query });
        return rows;
    }

    // Offline fallback: the cluster's own components, clearly flagged so they're not
    // mistaken for a live Cantus Index result.
    function localFallbackRows(query) {
        const rows = [{ kind: "notice", text: "Cantus Index unavailable — showing this cluster’s known components" }];
        findMatches(query).forEach(function (e) {
            rows.push({ kind: "match", element: e });
        });
        rows.push({ kind: "propose", text: query });
        return rows;
    }

    function isNavigable(row) {
        return !!row && (row.kind === "match" || row.kind === "propose");
    }

    // Text for a non-selectable status/prompt row.
    function messageRowText(kind) {
        if (kind === "loading") return "Searching Cantus Index…";
        return "Type to search or add component elements"; // "hint"
    }

    function renderTypeahead() {
        typeahead.innerHTML = "";
        taRows.forEach(function (row, i) {
            const li = document.createElement("li");
            if (!isNavigable(row)) {
                li.className = "typeahead-hint";
                if (row.kind === "notice") li.classList.add("typeahead-notice");
                li.textContent = row.kind === "notice" ? row.text : messageRowText(row.kind);
                typeahead.appendChild(li);
                return;
            }
            li.className = "typeahead-item" + (i === taActiveIndex ? " active" : "");
            if (row.kind === "propose") {
                li.classList.add("typeahead-propose");
                li.textContent = "＋ Propose “" + row.text + "” as a new component element in Cantus Index";
            } else {
                const label = document.createElement("span");
                label.className = "typeahead-label";
                label.textContent = row.element.text;
                li.appendChild(label);
                if (row.element.cantusId) {
                    const cid = document.createElement("span");
                    cid.className = "typeahead-cid";
                    cid.textContent = row.element.cantusId;
                    li.appendChild(cid);
                }
            }
            // mousedown (not click) so the composer keeps focus and the caret/context
            li.addEventListener("mousedown", function (e) {
                e.preventDefault();
                activateRow(i);
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

    function firstNavigable() {
        return taRows.findIndex(isNavigable);
    }

    function openTypeahead(rows, context) {
        taRows = rows;
        taContext = context;
        taActiveIndex = firstNavigable();
        renderTypeahead();
        positionTypeahead();
        typeahead.hidden = false;
    }

    function closeTypeahead() {
        typeahead.hidden = true;
        taRows = [];
        taContext = null;
        if (ciDebounce) {
            clearTimeout(ciDebounce);
            ciDebounce = null;
        }
        if (ciAbort) {
            ciAbort.abort();
            ciAbort = null;
        }
        ciSeq += 1; // invalidate any response still in flight
    }

    function isTypeaheadOpen() {
        return !typeahead.hidden;
    }

    function moveActive(delta) {
        const nav = taRows.reduce((acc, row, i) => (isNavigable(row) ? acc.concat(i) : acc), []);
        if (!nav.length) return;
        let pos = nav.indexOf(taActiveIndex);
        if (pos < 0) pos = 0;
        taActiveIndex = nav[(pos + delta + nav.length) % nav.length];
        renderTypeahead();
    }

    function activateRow(index) {
        const row = taRows[index];
        if (!isNavigable(row) || !taContext) return;
        if (row.kind === "propose") {
            insertComponent({ text: row.text }, true);
        } else {
            insertComponent(row.element, false);
        }
    }

    // Replace the typed query (if any) with a component token at the caret. When
    // `proposed`, the token carries the placeholder ID and a "pending" style until
    // Cantus Index assigns a real one.
    function insertComponent(element, proposed) {
        const ctx = taContext;
        if (!ctx) return closeTypeahead();
        pushUndo();
        const range = document.createRange();
        if (ctx.textNode) {
            // drop the typed query text, keeping any leading whitespace and the tail
            ctx.textNode.nodeValue = ctx.leadWs + ctx.textNode.nodeValue.slice(ctx.offset);
            range.setStart(ctx.textNode, ctx.leadWs.length);
        } else {
            range.setStart(ctx.elementNode, ctx.offset);
        }
        range.collapse(true);
        // approved components carry the Cantus ID from the pool; a proposed one has
        // none shown (its backend ID is assigned later) — only the data-proposed flag.
        const cantusId = proposed ? "" : element.cantusId || "";
        const token = makeToken("component", element.text, cantusId, proposed);
        const trailingSpace = insertTokenAtRange(range, token);
        placeCaretAfter(trailingSpace);
        closeTypeahead();
        syncToTextarea();
    }

    // Query the Django proxy (which wraps Cantus Index's /json-text) for a term,
    // caching per session and cancelling any earlier in-flight request so a slow
    // answer can't clobber a newer one. Resolves to {results} | {error} | {aborted}.
    function ciSearch(query) {
        const key = query.trim().toLowerCase();
        if (ciCache.has(key)) return Promise.resolve({ results: ciCache.get(key) });
        if (ciAbort) ciAbort.abort();
        ciAbort = new AbortController();
        return fetch("/ci-component-search/" + encodeURIComponent(query.trim()), { signal: ciAbort.signal })
            .then(function (response) {
                return response.ok ? response.json() : { error: true };
            })
            .then(function (data) {
                if (data.error) return { error: true };
                const results = data.results || [];
                ciCache.set(key, results);
                return { results: results };
            })
            .catch(function (error) {
                return error && error.name === "AbortError" ? { aborted: true } : { error: true };
            });
    }

    // Debounce the live query behind a typing pause; only the latest survives (the
    // seq guard + the "did the query change?" re-check drop stale/overtaken results).
    function scheduleCiSearch(query) {
        ciSeq += 1;
        const seq = ciSeq;
        if (ciDebounce) clearTimeout(ciDebounce);
        ciDebounce = window.setTimeout(function () {
            ciSearch(query).then(function (outcome) {
                if (seq !== ciSeq || outcome.aborted || !isTypeaheadOpen()) return;
                const ctx = currentQueryContext();
                if (!ctx || ctx.query.trim().toLowerCase() !== query.toLowerCase()) return;
                const rows = outcome.error ? localFallbackRows(query) : rowsFromResults(outcome.results, query);
                openTypeahead(rows, ctx);
            });
        }, CI_DEBOUNCE_MS);
    }

    // Offer the dropdown at the caret; shown on focus and input so it's discoverable.
    // Empty field → a search prompt; >= CI_MIN_QUERY chars → a live (debounced,
    // cached) Cantus Index query; below that you can still propose the typed text.
    function refreshTypeahead() {
        if (!(currentCluster && hasComponentCheckbox.checked)) {
            closeTypeahead();
            return;
        }
        const context = currentQueryContext();
        if (!context) {
            closeTypeahead();
            return;
        }
        const query = context.query.trim();
        if (!query) {
            openTypeahead([{ kind: "hint" }], context);
            return;
        }
        if (query.length < CI_MIN_QUERY) {
            openTypeahead([{ kind: "propose", text: query }], context);
            return;
        }
        const cached = ciCache.get(query.toLowerCase());
        if (cached) {
            openTypeahead(rowsFromResults(cached, query), context);
            return;
        }
        openTypeahead([{ kind: "loading" }, { kind: "propose", text: query }], context);
        scheduleCiSearch(query);
    }

    function onComposerInput() {
        syncToTextarea();
        refreshTypeahead();
    }

    // ---- token action menu (click a box) --------------------------------

    // A click on a token opens a small floating control above it: components get a
    // red "Remove"; cores get "Split" plus a red "Delete" (the deliberate approval
    // for removing base text — no separate modal). A drag never triggers this,
    // because a drag ends with "drop", not "click".
    // Build a menu button; `hotkey` (if given) renders as a small keycap so it
    // reads clearly as a shortcut rather than plain text.
    function menuButton(label, hotkey, danger, onAct) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "token-menu-btn" + (danger ? " token-menu-btn--danger" : "");
        btn.appendChild(document.createTextNode(label));
        if (hotkey) {
            const kbd = document.createElement("kbd"); // semantic keyboard-input element
            kbd.className = "token-menu-key";
            kbd.textContent = hotkey;
            btn.appendChild(kbd);
        }
        btn.addEventListener("mousedown", function (e) {
            e.preventDefault();
            onAct();
        });
        return btn;
    }

    function openMenu(token) {
        closeMenu();
        closeTypeahead(); // opening a box's menu dismisses the search prompt
        menuToken = token;
        tokenMenu.innerHTML = "";

        // Splittable elements (core, proposed) get Split; every element gets a
        // delete. Cores drop into the restore tray; components just go (undo only).
        if (isSplittable(token)) {
            tokenMenu.appendChild(
                menuButton("Split", "s", false, function () {
                    enterSplitMode(token);
                })
            );
        }
        const deleteLabel = isCoreToken(token) ? "Delete core element" : "Remove";
        tokenMenu.appendChild(
            menuButton(deleteLabel, "x", true, function () {
                deleteToken(token);
            })
        );

        tokenMenu.hidden = false;
        positionMenu();
    }

    // Sit centered above the box. For a token that wraps across lines, anchor on
    // its first line fragment so the menu lands where the box visually starts,
    // not over blank space. Kept on-screen horizontally.
    function positionMenu() {
        if (!menuToken) return;
        const rects = menuToken.getClientRects();
        const r = rects.length ? rects[0] : menuToken.getBoundingClientRect();
        const center = r.left + r.width / 2;
        let left = center - tokenMenu.offsetWidth / 2;
        left = Math.max(4, Math.min(left, window.innerWidth - tokenMenu.offsetWidth - 4));
        tokenMenu.style.left = left + "px";
        tokenMenu.style.top = r.top - tokenMenu.offsetHeight - 6 + "px";
    }

    function closeMenu() {
        if (!tokenMenu) return;
        tokenMenu.hidden = true;
        menuToken = null;
    }

    function isMenuOpen() {
        return tokenMenu && !tokenMenu.hidden;
    }

    // Menu/hotkey delete dispatch: a core is recoverable (goes to the restore
    // tray), a component is not (undo only).
    function deleteToken(token) {
        if (isCoreToken(token)) deleteCore(token);
        else removeComponent(token);
    }

    function removeComponent(token) {
        pushUndo();
        token.remove();
        closeMenu();
        normalizeComposer();
    }

    function deleteCore(token) {
        pushUndo();
        const index = allTokens().indexOf(token);
        removedCores.push({ id: token.dataset.text, text: token.dataset.text, index: index });
        token.remove();
        closeMenu();
        normalizeComposer();
        renderTray();
    }

    // ---- split a core into two cores ------------------------------------

    // Word-boundary split: the element's words are shown with clickable boundaries;
    // clicking one divides it there into two of the same kind. Esc cancels.
    function enterSplitMode(token) {
        if (!isSplittable(token)) return;
        exitSplitMode();
        closeMenu();
        const words = token.dataset.text.split(/\s+/).filter(Boolean);
        if (words.length < 2) return; // nothing to split
        token.classList.add("cluster-token--splitting");
        token.draggable = false;
        token.innerHTML = "";
        words.forEach(function (word, i) {
            if (i > 0) {
                const point = document.createElement("span");
                point.className = "split-point";
                point.dataset.splitIndex = String(i);
                point.title = "Split here";
                token.appendChild(point);
            }
            const w = document.createElement("span");
            w.className = "split-word";
            w.textContent = word;
            token.appendChild(w);
        });
    }

    function splittingToken() {
        return composer.querySelector(".cluster-token--splitting");
    }

    // Rebuild a splitting token's normal display from its stored text.
    function exitSplitMode() {
        const token = splittingToken();
        if (!token) return;
        token.classList.remove("cluster-token--splitting");
        token.draggable = true;
        token.innerHTML = "";
        const label = document.createElement("span");
        label.className = "token-label";
        label.textContent = token.dataset.text;
        const cid = document.createElement("span");
        cid.className = "token-cid";
        cid.textContent = token.dataset.cantusId || "";
        cid.title = "Cantus ID";
        token.append(label, cid);
    }

    function performSplit(token, wordIndex) {
        const words = token.dataset.text.split(/\s+/).filter(Boolean);
        const left = words.slice(0, wordIndex).join(" ");
        const right = words.slice(wordIndex).join(" ");
        if (!left || !right) return;
        pushUndo();
        // Two of the same kind: a core yields two cores; a proposed component
        // yields two proposed components (still uncatalogued, so no Cantus ID).
        const make = isCoreToken(token)
            ? makeCoreToken
            : function (t) {
                  return makeToken("component", t, "", true);
              };
        token.replaceWith(make(left), document.createTextNode(" "), make(right));
        normalizeComposer();
    }

    // ---- drag to reorder ------------------------------------------------

    let dragToken = null;

    function onDragStart(e) {
        const token = e.target.closest && e.target.closest(".cluster-token");
        if (!token) return;
        closeMenu();
        closeTypeahead();
        dragToken = token;
        token.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        // Firefox needs data set for a drag to start.
        e.dataTransfer.setData("text/plain", token.dataset.text);
    }

    function onDragEnd() {
        if (dragToken) dragToken.classList.remove("dragging");
        dragToken = null;
    }

    // The token before which the dragged token should land (null → append).
    function dragTargetToken(x, y) {
        const tokens = allTokens().filter(function (t) {
            return t !== dragToken;
        });
        let best = null;
        let bestDist = Infinity;
        tokens.forEach(function (t) {
            const box = t.getBoundingClientRect();
            const cx = box.left + box.width / 2;
            const cy = box.top + box.height / 2;
            // consider tokens that sit after the pointer in reading order
            const after = cy > y + box.height / 2 || (Math.abs(cy - y) <= box.height / 2 && cx > x);
            if (!after) return;
            const dist = Math.hypot(cx - x, cy - y);
            if (dist < bestDist) {
                bestDist = dist;
                best = t;
            }
        });
        return best;
    }

    function onDragOver(e) {
        if (!dragToken) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
    }

    function onDrop(e) {
        if (!dragToken) return;
        e.preventDefault();
        const target = dragTargetToken(e.clientX, e.clientY);
        if (target === dragToken) return;
        pushUndo();
        if (target) {
            composer.insertBefore(dragToken, target);
        } else {
            composer.appendChild(dragToken);
        }
        normalizeComposer();
    }

    // ---- protect tokens from keyboard deletion --------------------------

    // Tokens are atomic and only removed through their menu, so Backspace/Delete
    // and typing over a selection can't quietly destroy one. Free text (the search
    // query) edits normally.
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

    function rangeHitsToken(range) {
        const tokens = allTokens();
        for (let i = 0; i < tokens.length; i++) {
            if (range.intersectsNode(tokens[i])) return true;
        }
        return false;
    }

    function onBeforeInput(e) {
        const sel = window.getSelection();
        if (!sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        if (!range.collapsed) {
            if (rangeHitsToken(range)) e.preventDefault();
            return;
        }
        const t = e.inputType || "";
        if (t === "deleteContentBackward" || t === "deleteWordBackward") {
            if (isToken(nodeBeforeCaret(range))) e.preventDefault();
        } else if (t === "deleteContentForward" || t === "deleteWordForward") {
            if (isToken(nodeAfterCaret(range))) e.preventDefault();
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

        hasComponentCheckbox.addEventListener("change", function () {
            hint.hidden = !(hasComponentCheckbox.checked && currentCluster);
            if (!hasComponentCheckbox.checked) closeTypeahead();
        });

        composer.addEventListener("input", onComposerInput);
        composer.addEventListener("beforeinput", onBeforeInput);

        // click a box → its action menu (unless we're splitting or just dragged)
        composer.addEventListener("click", function (e) {
            const splitPoint = e.target.closest && e.target.closest(".split-point");
            if (splitPoint) {
                performSplit(splitPoint.closest(".cluster-token"), Number(splitPoint.dataset.splitIndex));
                return;
            }
            if (splittingToken()) {
                exitSplitMode();
                return;
            }
            const token = e.target.closest && e.target.closest(".cluster-token");
            if (token) {
                openMenu(token);
            } else {
                closeMenu();
                refreshTypeahead(); // clicked in free space → reveal components
            }
        });

        // reveal the component list as soon as the field is entered
        composer.addEventListener("focus", function () {
            window.setTimeout(refreshTypeahead, 0); // defer so the caret is placed first
        });

        composer.addEventListener("dragstart", onDragStart);
        composer.addEventListener("dragend", onDragEnd);
        composer.addEventListener("dragover", onDragOver);
        composer.addEventListener("drop", onDrop);

        composer.addEventListener("keydown", function (e) {
            // Ctrl/Cmd+Z drives our undo, not the browser's contenteditable undo
            if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === "z" || e.key === "Z")) {
                e.preventDefault();
                undo();
                return;
            }
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
                    activateRow(taActiveIndex);
                    return;
                }
                if (e.key === "Escape") {
                    e.preventDefault();
                    closeTypeahead();
                    return;
                }
            }
            if (e.key === "Escape") {
                if (splittingToken()) {
                    e.preventDefault();
                    exitSplitMode();
                    return;
                }
                if (isMenuOpen()) {
                    e.preventDefault();
                    closeMenu();
                    return;
                }
            }
            // keep the field a single flowing line; no stray newlines
            if (e.key === "Enter") e.preventDefault();
        });

        // hotkeys while a box's menu is open: 's' splits (core/proposed), 'x' deletes
        document.addEventListener("keydown", function (e) {
            if (isMenuOpen()) {
                if ((e.key === "s" || e.key === "S") && isSplittable(menuToken)) {
                    e.preventDefault();
                    enterSplitMode(menuToken);
                    return;
                }
                if (e.key === "x" || e.key === "X") {
                    e.preventDefault();
                    deleteToken(menuToken);
                    return;
                }
            }
            if (e.key === "Escape") {
                if (splittingToken()) exitSplitMode();
                else if (isMenuOpen()) closeMenu();
            }
        });

        // restore-tray chips
        if (tray) {
            tray.addEventListener("click", function (e) {
                const chip = e.target.closest(".tray-chip");
                if (chip) restoreCore(Number(chip.dataset.trayIndex));
            });
        }

        if (undoButton) {
            undoButton.addEventListener("click", function () {
                undo();
            });
        }

        // clicking outside the composer/menu closes the menu
        document.addEventListener("mousedown", function (e) {
            if (!isMenuOpen()) return;
            if (tokenMenu.contains(e.target) || (menuToken && menuToken.contains(e.target))) return;
            closeMenu();
        });

        // dropping the typeahead / discarding unresolved free text when focus leaves
        composer.addEventListener("blur", function () {
            // defer so a mousedown on a typeahead item can fire first
            window.setTimeout(function () {
                closeTypeahead();
                if (currentCluster && !splittingToken()) normalizeComposer();
            }, 0);
        });

        window.addEventListener(
            "scroll",
            function () {
                if (isTypeaheadOpen()) positionTypeahead();
                if (isMenuOpen()) positionMenu();
            },
            true
        );
        window.addEventListener("resize", function () {
            if (isTypeaheadOpen()) positionTypeahead();
            if (isMenuOpen()) positionMenu();
        });

        // guarantee the submitted value is the composed elements, not stray text
        const form = composer.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                if (currentCluster) {
                    exitSplitMode();
                    normalizeComposer();
                }
            });
        }
    }

    function init() {
        textarea = document.getElementById("id_manuscript_full_text_std_spelling");
        composer = document.getElementById("cluster-composer");
        select = document.getElementById("cluster-select");
        hasComponentCheckbox = document.getElementById("has-component-elements");
        hint = document.getElementById("component-elements-hint");
        undoButton = document.getElementById("cluster-undo");
        tray = document.getElementById("removed-cores-tray");
        const controls = document.getElementById("cluster-controls");
        if (!textarea || !composer || !select || !controls || !hasComponentCheckbox || !hint) return;

        typeahead = document.createElement("ul");
        typeahead.id = "element-typeahead";
        typeahead.className = "element-typeahead";
        typeahead.hidden = true;
        document.body.appendChild(typeahead);

        tokenMenu = document.createElement("div");
        tokenMenu.id = "token-menu";
        tokenMenu.className = "token-menu";
        tokenMenu.hidden = true;
        document.body.appendChild(tokenMenu);

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
