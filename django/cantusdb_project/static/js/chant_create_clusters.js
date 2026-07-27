/*
 * Chant cluster composer (issues #2128 / #2129) — enhancement to the Create
 * Chant page.
 *
 * Turns the "Full text (standardized spelling)" field into an element composer.
 * A chant cluster's full text is an ordered sequence of typed elements; position
 * is just the order in the field:
 *
 *   - core elements      — chunks of the base chant's own text. They display the
 *                          parent Cantus ID (read live from the Cantus ID field),
 *                          but never store it — the server resolves a core's ID
 *                          through the parent chant. Deletable, but deleting one is
 *                          a deliberate act (click the box → red Delete): the
 *                          removed core drops into a restore tray and Undo reverts
 *                          it. A core can also be SPLIT into two cores.
 *   - component elements — troped/added, reusable, found by TYPING in the field
 *                          (a filtered dropdown inserts one inline). Each carries
 *                          its OWN Cantus ID exactly as retrieved from Cantus Index
 *                          — e.g. g04828:01 (a sub-ID of the parent) or a wholly
 *                          separate ID like a shared doxology's 909030. IDs are
 *                          NEVER computed here. A component the user PROPOSES (not
 *                          yet in CI) shows no ID and is captured locally only —
 *                          there is no CI write API, so nothing is submitted upstream.
 *
 * Only elements are saved: free text typed into the field is just a search query
 * for the dropdown. It is discarded when it isn't turned into an element (the
 * hidden textarea is built from tokens only).
 *
 * The composer activates when the cataloguer ticks "Has interleaved component
 * elements". On activation it seeds a single core from the base chant's standard
 * text, fetched from Cantus Index by the Cantus ID (the ci-base-text endpoint);
 * the cataloguer splits that into cores and interleaves components. Components come
 * from a live, debounced Cantus Index text search (the ci-component-search
 * endpoint). CI does not pre-split text, so the base text arrives as one blob.
 */
(function () {
    "use strict";

    const MAX_MATCHES = 8;
    const MAX_UNDO = 50;
    const CI_MIN_QUERY = 3; // characters before we query Cantus Index (matches the Input Tool)
    const CI_DEBOUNCE_MS = 250; // wait for a typing pause before firing a request
    const BASE_TEXT_URL = "/ci-base-text/"; // + cantus_id → { base_text }

    let textarea, composer, cantusIdInput, hasComponentCheckbox, hint, status, undoButton, reloadButton, tray;
    let elementsField; // hidden input carrying the composed elements as JSON to the server
    // Truthy while the composer is active (cluster mode on); null when off. No preset
    // payload any more — the base text is fetched and the parent ID is read live.
    let currentCluster = null;
    let activateSeq = 0; // guards the async base-text seed against a fast off-toggle

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
    // `proposed` marks a component not yet in Cantus Index (data-proposed). It behaves
    // like any other component (menu, drag, undo) but carries no ID and shows a
    // "proposed" badge in place of one — captured locally only, never submitted to CI.
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

    // The parent Cantus ID, read live from the Cantus ID field. Cores display it but
    // never store it (the server resolves a core's ID through the parent chant), so a
    // later correction to the field just re-labels existing cores — no data at stake.
    function parentCantusId() {
        return cantusIdInput ? cantusIdInput.value.trim() : "";
    }

    function makeCoreToken(text) {
        return makeToken("core", text, parentCantusId());
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
        syncToElementsField();
    }

    // Serialise the composer's tokens (DOM order = element order) into the hidden
    // field the server persists as ChantElement rows. Kept in lockstep with the
    // textarea. Empty when cluster mode is off, so un-ticking the box saves no
    // elements — the flattened text alone remains.
    function syncToElementsField() {
        if (!elementsField) return;
        if (!currentCluster) {
            elementsField.value = "";
            return;
        }
        const elements = [];
        composer.querySelectorAll(".cluster-token").forEach(function (token) {
            elements.push({
                kind: token.dataset.kind,
                text: token.dataset.text,
                cantus_id: token.dataset.cantusId || "",
                proposed: token.dataset.proposed === "true",
            });
        });
        elementsField.value = JSON.stringify(elements);
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

    function setStatus(msg) {
        if (!status) return;
        status.textContent = msg || "";
        status.hidden = !msg;
    }

    // Turn the composer on. The base text isn't known synchronously — it's fetched
    // from Cantus Index by the Cantus ID — so we reveal the composer immediately and
    // seed the core once the fetch resolves (seedBaseText).
    function activateFromCantusId() {
        currentCluster = {}; // active sentinel; parent ID + components are read live
        textarea.style.display = "none";
        composer.hidden = false;
        hint.hidden = !hasComponentCheckbox.checked;
        if (undoButton) undoButton.hidden = false;
        if (reloadButton) reloadButton.hidden = false;
        updateReloadButton();
        // manual base text is the fallback only when there's no Cantus ID to fetch by
        reseed(textarea.value.trim());
    }

    // Reset the composer and (re)seed the base text. Runs on activation and on an
    // explicit reload (a Cantus ID change) — it clears any composed work first.
    function reseed(preTyped) {
        activateSeq += 1;
        removedCores = [];
        undoStack = [];
        composer.innerHTML = "";
        composer.appendChild(document.createTextNode(" "));
        composer.contentEditable = "true"; // reset (seedBaseText locks it while fetching)
        renderTray();
        updateUndoButton();
        syncToTextarea();
        seedBaseText(activateSeq, preTyped);
    }

    // Fetch the base chant's standard text from CI and seed it as one core. With a
    // Cantus ID, CI is authoritative; with none, seeds from any text the cataloguer
    // typed. Empty either way → a prompt. Guarded so a quick off-toggle can't seed late.
    function seedBaseText(seq, preTyped) {
        const cid = parentCantusId();
        setStatus(cid ? "Fetching base text from Cantus Index…" : "");
        // Lock the composer while the fetch is in flight so anything typed in that
        // window isn't wiped when the seeded core replaces the contents.
        if (cid) composer.contentEditable = "false";
        const done = function (base) {
            if (seq !== activateSeq || !currentCluster) return; // toggled off meanwhile
            composer.contentEditable = "true";
            // With a Cantus ID, Cantus Index is the sole source of the base text — never
            // fall back to text already in the field, or arbitrary typed text would be
            // relabelled as a core of this ID. Typing the base text in is only the path
            // when there's no ID to fetch by.
            const text = cid ? (base || "").trim() : preTyped;
            if (text) {
                seedCore(text);
                setStatus("");
            } else if (cid) {
                setStatus("No base text found in Cantus Index for Cantus ID " + cid + ".");
            } else {
                setStatus("Add a Cantus ID to load the base chant text from Cantus Index.");
            }
        };
        if (!cid) {
            done("");
            return;
        }
        fetchBaseText(cid).then(done);
    }

    function seedCore(text) {
        composer.innerHTML = "";
        composer.appendChild(makeCoreToken(text));
        composer.appendChild(document.createTextNode(" "));
        syncToTextarea();
    }

    // GET the base chant's standard full text (one blob; CI doesn't pre-split it).
    function fetchBaseText(cantusId) {
        return fetch(BASE_TEXT_URL + encodeURIComponent(cantusId), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (r) {
                return r.ok ? r.json() : null;
            })
            .then(function (data) {
                return data ? data.base_text : "";
            })
            .catch(function () {
                return "";
            });
    }

    // Reload the base text from Cantus Index for the current Cantus ID. Driven by an
    // explicit button — a silent reload on the field's blur was undiscoverable. Reloading
    // replaces the base chant, so confirm first whenever any elements are composed,
    // including a freshly-seeded core the cataloguer hasn't touched yet.
    function reloadBaseText() {
        if (!currentCluster || !parentCantusId()) return;
        if (
            allTokens().length > 0 &&
            !window.confirm(
                "This will reload the base text from Cantus Index and discard the current elements. Continue?"
            )
        ) {
            return;
        }
        reseed("");
    }

    // The reload button can only fetch when there's a Cantus ID, so keep it visible but
    // disabled until one is entered.
    function updateReloadButton() {
        if (!reloadButton) return;
        reloadButton.disabled = !parentCantusId();
    }

    function deactivateCluster() {
        activateSeq += 1; // cancel any in-flight base-text seed
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
        setStatus("");
        if (undoButton) undoButton.hidden = true;
        if (reloadButton) reloadButton.hidden = true;
        renderTray();
        syncToElementsField(); // cluster mode off → submit no elements, just the flattened text
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

    // Float this cluster's own sub-elements (Cantus IDs like "<parent>:NN" or
    // "<parent>.Tp7") to the top, keeping CI's order within each group — search all
    // of Cantus Index, but surface the obvious in-cluster ones first. The parent is
    // read live from the Cantus ID field; with no ID yet, leave CI's order untouched.
    function rankResults(results) {
        const parent = parentCantusId();
        if (!currentCluster || !parent) return results;
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

    // CI unreachable: no local pool to fall back on, so flag the outage and still let
    // the cataloguer propose the typed text as a new component.
    function ciErrorRows(query) {
        return [
            { kind: "notice", text: "Cantus Index unavailable — try again in a moment" },
            { kind: "propose", text: query },
        ];
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
                const rows = outcome.error ? ciErrorRows(query) : rowsFromResults(outcome.results, query);
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
        // Restore the token's normal display before snapshotting, so undoing the split
        // returns to the intact element — not the split-mode markup it was showing.
        exitSplitMode();
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
    let dropIndicator = null; // blue insertion bar shown while dragging (created in init)

    // Show the insertion bar at the boundary a drop would land on: the left edge of the
    // target token, or the right edge of the last token when appending past the end.
    function showDropIndicator(target) {
        if (!dropIndicator) return;
        let rect, left;
        if (target) {
            const rects = target.getClientRects();
            rect = rects.length ? rects[0] : target.getBoundingClientRect();
            left = rect.left;
        } else {
            const others = allTokens().filter(function (t) {
                return t !== dragToken;
            });
            if (!others.length) return hideDropIndicator();
            const last = others[others.length - 1];
            const rects = last.getClientRects();
            rect = rects.length ? rects[rects.length - 1] : last.getBoundingClientRect();
            left = rect.right;
        }
        dropIndicator.style.left = left - 1 + "px"; // centre the 2px bar on the boundary
        dropIndicator.style.top = rect.top + "px";
        dropIndicator.style.height = rect.height + "px";
        dropIndicator.hidden = false;
    }

    function hideDropIndicator() {
        if (dropIndicator) dropIndicator.hidden = true;
    }

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
        hideDropIndicator();
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
        showDropIndicator(dragTargetToken(e.clientX, e.clientY));
    }

    function onDrop(e) {
        if (!dragToken) return;
        e.preventDefault();
        hideDropIndicator();
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
        // The checkbox is the sole activation control (the demo cluster <select> is
        // gone): ticking it seeds the composer from the base chant, unticking it
        // flattens the composed elements back to the plain text field.
        hasComponentCheckbox.addEventListener("change", function () {
            if (hasComponentCheckbox.checked) {
                activateFromCantusId();
            } else {
                deactivateCluster();
            }
        });

        // Reloading is an explicit button, not a silent blur (which was undiscoverable);
        // keep it enabled only while there's a Cantus ID to fetch by.
        if (cantusIdInput) {
            cantusIdInput.addEventListener("input", updateReloadButton);
        }
        if (reloadButton) {
            reloadButton.addEventListener("click", reloadBaseText);
        }

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

        // clicking outside the composer/menu closes the menu; clicking anywhere
        // outside the composer while splitting cancels split mode (Esc also does)
        document.addEventListener("mousedown", function (e) {
            // ...but not the token menu, whose own "Split" button enters split mode (its
            // mousedown bubbles here right after) — that click must not cancel it.
            if (
                splittingToken() &&
                !composer.contains(e.target) &&
                !tokenMenu.contains(e.target)
            ) {
                exitSplitMode();
            }
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
        cantusIdInput = document.getElementById("id_cantus_id");
        hasComponentCheckbox = document.getElementById("has-component-elements");
        hint = document.getElementById("component-elements-hint");
        status = document.getElementById("cluster-status");
        elementsField = document.getElementById("id_elements_json");
        undoButton = document.getElementById("cluster-undo");
        reloadButton = document.getElementById("cluster-reload");
        tray = document.getElementById("removed-cores-tray");
        const controls = document.getElementById("cluster-controls");
        if (!textarea || !composer || !controls || !hasComponentCheckbox || !hint) return;

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

        dropIndicator = document.createElement("div");
        dropIndicator.className = "cluster-drop-indicator";
        dropIndicator.hidden = true;
        document.body.appendChild(dropIndicator);

        controls.hidden = false; // reveal now that JS is running (progressive enhancement)
        wire();
    }

    document.addEventListener("DOMContentLoaded", init);
})();
