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
 *                          a deliberate act (click the box, or Backspace beside it,
 *                          then red Delete): the removed core drops into a restore
 *                          tray and Undo reverts it. A core can also be SPLIT in two.
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

    const MAX_UNDO = 50;
    const CI_MIN_QUERY = 3; // characters before we query Cantus Index (matches the Input Tool)
    const CI_DEBOUNCE_MS = 250; // wait for a typing pause before firing a request
    const BASE_TEXT_URL = "/ci-base-text/"; // + cantus_id → { base_text }
    // Cantus Index's public chant page, for the menu's "View on Cantus Index" link.
    // cantusindex.org (not the uwaterloo host) is what serves /id/ today.
    const CI_ID_URL = "https://cantusindex.org/id/";
    const CLUSTER_ELEMENTS_URL = "/ci-cluster-elements/"; // + cantus_id → { elements }
    // Dropdown sizing, in px. MAX matches the stylesheet's max-height (~10 results);
    // MIN is the smallest list worth showing rather than flipping to the other side.
    const TYPEAHEAD_MAX_HEIGHT = 448; // 28rem
    const TYPEAHEAD_MIN_HEIGHT = 120;

    let textarea, composer, cantusIdInput, hasComponentCheckbox, hint, status, undoButton, reloadButton, tray;
    let bank, bankItems, bankStatus, bankHeading; // the elements card in the sidebar
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

    // element bank state
    let bankElements = []; // { cantus_id, genre, fulltext } as returned by the proxy
    let bankSeq = 0; // guards a slow bank fetch against a newer Cantus ID
    // The element the caret last sat before, so a bank chip clicked in the sidebar lands
    // where the cataloguer was working. Clicking outside the composer clears the
    // selection, so the position has to be remembered while it still exists.
    // null = the caret was past the last element (append).
    let caretBeforeToken = null;

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

        // A zero-width break opportunity after the token. Adjacent tokens sit directly
        // against each other with no whitespace between them (the gap is margin, not a
        // character — see normalizeComposer), so the browser has no soft-wrap point at a
        // token boundary: a run of single-word tokens glues into one unbreakable unit that
        // overflows or forces the line to wrap at an odd earlier point (#2188). <wbr> is an
        // element, not a character, so it adds the break point without anything the caret
        // can land in or delete — the composer's child-offset model is unchanged.
        token.append(label, cid, document.createElement("wbr"));
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

    function componentTokens() {
        return Array.from(composer.querySelectorAll(".cluster-token--component"));
    }

    // Insert a token at a collapsed range. No padding spaces: elements sit directly
    // against one another and the gap between them is margin, not a character. Callers
    // follow up with normalizeComposer(token), which also places the caret.
    function insertTokenAtRange(range, token) {
        range.insertNode(token);
    }

    function placeCaretAfter(node) {
        placeCaretAt(node, node.length);
    }

    // Collapse the selection at container/offset. In a text node the offset is a
    // character index; in the composer itself it is a CHILD index, which is how the caret
    // addresses the boundary between two adjacent elements now that no space separates
    // them. Typing there inserts a text node in the gap, which is what the typeahead's
    // element-node query context is for.
    function placeCaretAt(container, offset) {
        const sel = window.getSelection();
        const caret = document.createRange();
        caret.setStart(container, offset);
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

    // Drop any stray free text, leaving nothing but the tokens, so the field shows exactly
    // what will be saved.
    //
    // Adjacent elements are left DIRECTLY against each other, with no separator character
    // between them (3 Aug 2026 feedback). A space used to sit in every gap, which was a
    // real character the cataloguer could put a caret inside and delete — it read as
    // punctuation they hadn't typed. Their whole visible separation is `.cluster-token`'s
    // horizontal margin now, so there is nothing there to select or delete, and the text
    // that gets saved is unaffected either way: syncToTextarea() joins the element texts
    // with single spaces of its own.
    //
    // Pass `caretAfter` to keep typing where an element was just inserted — the rebuild
    // otherwise drops the selection, which is why this used to be reserved for structural
    // edits, blur and submit.
    function normalizeComposer(caretAfter) {
        const tokens = allTokens();
        composer.innerHTML = "";
        tokens.forEach(function (token) {
            composer.appendChild(token);
        });
        // One trailing space, so there is still somewhere to type a query after the last
        // element. It is the only text node left in a normalized composer.
        const tail = document.createTextNode(" ");
        composer.appendChild(tail);
        if (caretAfter) {
            const at = tokens.indexOf(caretAfter);
            // Between two elements the caret is a child offset in the composer; after the
            // last one it goes in the tail space, where typing continues normally.
            if (at >= 0 && at < tokens.length - 1) placeCaretAt(composer, at + 1);
            else placeCaretAfter(tail);
        }
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
        closeMenu(); // the rebuild below replaces every element node
        composer.innerHTML = snapshot.html;
        removedCores = snapshot.cores;
        renderTray();
        renderBank(); // undoing may have put an element back in, or taken one out
        syncToTextarea();
        updateUndoButton();
    }

    function updateUndoButton() {
        if (!undoButton) return;
        undoButton.disabled = undoStack.length === 0;
    }

    // ---- restore tray ---------------------------------------------------

    // Deleted core elements, offered back. Lives at the foot of the element bank's card
    // rather than under the composer (3 Aug 2026 feedback) — one elements panel, not two.

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

    // ---- element bank ---------------------------------------------------

    // The trope elements Cantus Index already holds for this chant's Cantus ID, offered
    // in the sidebar so they can be dragged straight in rather than searched for one at a
    // time (28 Jul 2026 demo feedback). Shares its card with the restore tray above, so
    // the whole element inventory — available and removed — is in one place.

    function setBankStatus(msg) {
        if (bankStatus) bankStatus.textContent = msg || "";
    }

    // Name the chant being catalogued in the heading rather than saying "this Cantus ID"
    // (3 Aug 2026 feedback) — with the card over in the sidebar, away from the field, the
    // deixis had nothing nearby to point at.
    function setBankHeading(cantusId) {
        if (!bankHeading) return;
        bankHeading.textContent = cantusId
            ? "Component Elements for " + cantusId
            : "Component Elements";
    }

    // Which bank elements are already in the composer, by Cantus ID — those chips are
    // shown but disabled, so an element can't be interleaved twice by accident.
    function placedCantusIds() {
        const placed = new Set();
        composer.querySelectorAll(".cluster-token--component").forEach(function (token) {
            if (token.dataset.cantusId) placed.add(token.dataset.cantusId);
        });
        return placed;
    }

    function renderBank() {
        if (!bank || !bankItems) return;
        bankItems.innerHTML = "";
        const placed = placedCantusIds();
        bankElements.forEach(function (element, i) {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "cluster-bank-item";
            chip.dataset.bankIndex = String(i);
            const label = document.createElement("span");
            label.textContent = element.fulltext || "";
            const cid = document.createElement("span");
            cid.className = "cluster-bank-cid";
            cid.textContent = element.genre
                ? element.cantus_id + " · " + element.genre
                : element.cantus_id;
            chip.append(label, cid);
            if (placed.has(element.cantus_id)) {
                chip.disabled = true;
                chip.draggable = false;
                chip.title = "Already placed in the text";
            } else {
                chip.draggable = true;
                chip.title = "Drag into the text, or click to add it at the cursor";
            }
            bankItems.appendChild(chip);
        });
    }

    // Load the bank for the current Cantus ID. Guarded by a sequence number so a slow
    // response for an old Cantus ID can't land after the cataloguer has changed it.
    function loadBank() {
        if (!bank) return;
        bankSeq += 1;
        const seq = bankSeq;
        const cid = parentCantusId();
        bankElements = [];
        renderBank();
        setBankHeading(cid);
        if (!currentCluster) {
            bank.hidden = true;
            return;
        }
        bank.hidden = false;
        if (!cid) {
            setBankStatus("Add a Cantus ID to see its catalogued elements.");
            return;
        }
        setBankStatus("Loading elements from Cantus Index…");
        fetch(CLUSTER_ELEMENTS_URL + encodeURIComponent(cid), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (r) {
                return r.ok ? r.json() : null;
            })
            .catch(function () {
                return null;
            })
            .then(function (data) {
                if (seq !== bankSeq || !currentCluster) return; // superseded meanwhile
                bankElements = (data && data.elements) || [];
                setBankStatus(
                    bankElements.length
                        ? ""
                        : "Cantus Index lists no elements for " + cid + "."
                );
                renderBank();
            });
    }

    // The first element at or after the caret — i.e. the one an insertion here would sit
    // in front of. null means the caret is past every element.
    function tokenAfterCaret() {
        const selection = window.getSelection();
        if (!selection.rangeCount) return null;
        const range = selection.getRangeAt(0);
        if (!range.collapsed) return null;
        if (!composer.contains(range.startContainer) && range.startContainer !== composer) {
            return null;
        }
        const tokens = allTokens();
        for (let i = 0; i < tokens.length; i++) {
            // comparePoint > 0 puts the element's start after the caret; 0 means the
            // caret is exactly at its boundary, which also inserts in front of it.
            if (range.comparePoint(tokens[i], 0) >= 0) return tokens[i];
        }
        return null;
    }

    // Snapshot where the caret is while the composer still owns the selection.
    function rememberCaret() {
        if (!currentCluster) return;
        const selection = window.getSelection();
        if (!selection.rangeCount) return;
        const node = selection.getRangeAt(0).startContainer;
        if (node !== composer && !composer.contains(node)) return; // focus is elsewhere
        caretBeforeToken = tokenAfterCaret();
    }

    // Add a bank element to the composer as a component token. `before` is the token to
    // insert ahead of (null → append), matching the drop-point model.
    function insertBankElement(index, before) {
        const element = bankElements[index];
        if (!element) return;
        pushUndo();
        const token = makeToken(
            "component",
            element.fulltext || "",
            element.cantus_id || "",
            false
        );
        // `before` may be an element that a later edit already removed; falling back to
        // appending is better than throwing on a stale reference.
        if (before && before.parentNode === composer) {
            composer.insertBefore(token, before);
        } else {
            composer.appendChild(token);
        }
        // Leave the caret after the new element so the next click lands in sequence.
        normalizeComposer(token);
        caretBeforeToken = tokenAfterCaret();
        renderBank(); // the element is placed now, so grey its chip out
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
        caretBeforeToken = null;
        closeMenu(); // the wipe below replaces every element node
        composer.innerHTML = "";
        composer.appendChild(document.createTextNode(" "));
        composer.contentEditable = "true"; // reset (seedBaseText locks it while fetching)
        renderTray();
        updateUndoButton();
        syncToTextarea();
        loadBank(); // the bank follows the Cantus ID, so it reloads alongside the base text
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
        const cid = parentCantusId();
        if (!currentCluster || !cid) return;
        if (
            allTokens().length > 0 &&
            !window.confirm(
                "This will reload the base text for " +
                    cid +
                    " from Cantus Index and discard the current elements. Continue?"
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
        caretBeforeToken = null;
        hint.hidden = true;
        setStatus("");
        if (undoButton) undoButton.hidden = true;
        if (reloadButton) reloadButton.hidden = true;
        bankSeq += 1; // cancel any in-flight bank fetch
        bankElements = [];
        if (bank) bank.hidden = true;
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
    // `payload` is the proxy's {results, total}: results is the page to render, total the
    // number of matches before clipping, so the shortfall can be reported to the user.
    function rowsFromResults(payload, query) {
        const results = payload.results || [];
        const rows = rankResults(results).map(function (r) {
            return {
                kind: "match",
                element: { text: (r.fulltext || "").trim(), cantusId: r.cid || "" },
            };
        });
        // Say how much is out of view. Two different shortfalls, worded apart:
        //   - Cantus Index hit its own 100-result ceiling, so matches were lost upstream
        //     before the genre filter ran. The count names CI's matches, not the
        //     component elements listed here — often far fewer, sometimes none — so it
        //     says "Cantus Index matches" rather than implying 100+ usable ones.
        //   - Otherwise the filtered total is exact and simply larger than the page.
        const total = payload.total || results.length;
        if (payload.capped) {
            rows.push({
                kind: "more",
                text: "100+ Cantus Index matches — keep typing to narrow the search",
            });
        } else if (total > results.length) {
            rows.push({
                kind: "more",
                text: total + " matches — keep typing to narrow the search",
            });
        }
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
                // "notice" and "more" carry their own text; the rest are fixed prompts.
                if (row.kind === "notice") li.classList.add("typeahead-notice");
                if (row.kind === "more") li.classList.add("typeahead-more");
                li.textContent = row.text || messageRowText(row.kind);
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

    // Anchor the dropdown to the caret, sized to whatever room the viewport allows.
    // The list is tall enough for about ten results, which near the bottom of a long
    // form would otherwise run off-screen: prefer below the caret, flip above when
    // that side is roomier, and cap the height to the space actually available so the
    // list always ends on-screen and scrolls internally instead.
    function positionTypeahead() {
        const sel = window.getSelection();
        if (!sel.rangeCount) return;
        let rect = sel.getRangeAt(0).getBoundingClientRect();
        if (!rect.height && !rect.width && !rect.top) {
            rect = composer.getBoundingClientRect(); // fallback when a collapsed caret has no box
        }
        const GAP = 4; // breathing room from the caret and the viewport edge
        const below = window.innerHeight - rect.bottom - GAP;
        const above = rect.top - GAP;
        // Stay below the caret whenever the full list fits there; otherwise open on
        // whichever side has more room. Flipping only when the space below fell under the
        // bare minimum meant a caret partway down the form got a stub of a list — 3 rows
        // in 195px — while ~500px sat unused above it (3 Aug 2026 feedback: the dropdown
        // showing fewer results than the ten it is sized for).
        const flip = below < TYPEAHEAD_MAX_HEIGHT && above > below;
        const room = Math.max(TYPEAHEAD_MIN_HEIGHT, flip ? above : below);

        typeahead.style.maxHeight = Math.min(TYPEAHEAD_MAX_HEIGHT, room) + "px";
        // Page coordinates, not viewport ones: the list is positioned absolutely so the
        // browser scrolls it along with the text it belongs to. It used to be fixed and
        // re-positioned from a scroll handler, which runs after the page has already
        // painted at the new offset — so it lagged a frame behind every scroll and
        // visibly bounced (3 Aug 2026 feedback). Nothing re-positions it on scroll now.
        // Clamped horizontally as well as vertically: the caret can sit far enough right in
        // the full-width composer that a wide list would otherwise run off the edge.
        const maxLeft = Math.max(GAP, window.innerWidth - typeahead.offsetWidth - GAP);
        typeahead.style.left = Math.min(rect.left, maxLeft) + window.scrollX + "px";
        // Measuring the height needs it laid out, which it is: callers unhide first.
        // The flip clamp is viewport-relative, so translate after clamping.
        typeahead.style.top =
            (flip
                ? Math.max(GAP, rect.top - typeahead.offsetHeight - GAP)
                : rect.bottom) +
            window.scrollY +
            "px";
    }

    function firstNavigable() {
        return taRows.findIndex(isNavigable);
    }

    function openTypeahead(rows, context) {
        taRows = rows;
        taContext = context;
        taActiveIndex = firstNavigable();
        renderTypeahead();
        // Unhide first: positionTypeahead() measures offsetHeight to decide whether the
        // list fits below the caret, and a hidden element measures zero.
        typeahead.hidden = false;
        positionTypeahead();
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
        insertTokenAtRange(range, token);
        closeTypeahead();
        // Collapse the padding spaces this insertion just added, keeping the caret after
        // the new element so typing continues; without it the leftover spaces render
        // (pre-wrap) and indent the element whenever it starts a wrapped line.
        normalizeComposer(token);
        renderBank(); // a searched component may be one the bank also offers
    }

    // Query the Django proxy (which wraps Cantus Index's /json-text) for a term,
    // caching per session and cancelling any earlier in-flight request so a slow
    // answer can't clobber a newer one. Resolves to {results} | {error} | {aborted}.
    function ciSearch(query) {
        const key = query.trim().toLowerCase();
        if (ciCache.has(key)) return Promise.resolve({ payload: ciCache.get(key) });
        if (ciAbort) ciAbort.abort();
        ciAbort = new AbortController();
        return fetch("/ci-component-search/" + encodeURIComponent(query.trim()), { signal: ciAbort.signal })
            .then(function (response) {
                return response.ok ? response.json() : { error: true };
            })
            .then(function (data) {
                if (data.error) return { error: true };
                const results = data.results || [];
                // Cache the clipped page together with the unclipped total, so a repeat
                // query reports the same "N more matches" as the first one did.
                const payload = {
                    results: results,
                    total: data.total || results.length,
                    capped: !!data.capped,
                };
                ciCache.set(key, payload);
                return { payload: payload };
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
                const rows = outcome.error ? ciErrorRows(query) : rowsFromResults(outcome.payload, query);
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

    // The element's Cantus ID for display/linking. A core has no ID of its own — it is
    // the parent chant's, read live from the field — while a component carries its own.
    function tokenCantusId(token) {
        return isCoreToken(token) ? parentCantusId() : token.dataset.cantusId || "";
    }

    // "View on Cantus Index" — a real anchor rather than a scripted window.open, so
    // middle-click and ctrl-click open a background tab the way they do anywhere else.
    function menuLink(label, url) {
        const link = document.createElement("a");
        link.className = "token-menu-btn token-menu-btn--link";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        // Dismiss the menu on the way out; the navigation itself proceeds as normal.
        link.addEventListener("click", function () {
            closeMenu();
        });
        return link;
    }

    function openMenu(token) {
        closeMenu();
        closeTypeahead(); // opening a box's menu dismisses the search prompt
        menuToken = token;
        tokenMenu.innerHTML = "";

        // Look the element up externally (28 Jul 2026 demo feedback). Only offered when
        // there is an ID to look up: a proposed component isn't in Cantus Index yet, and
        // a core has nothing to link to until the chant's Cantus ID is filled in.
        const cantusId = tokenCantusId(token);
        if (cantusId) {
            tokenMenu.appendChild(
                menuLink("View on Cantus Index", CI_ID_URL + encodeURIComponent(cantusId))
            );
        }

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
        // Page coordinates for the same reason as the typeahead: absolutely positioned so
        // it scrolls with its element instead of being chased by a scroll handler.
        tokenMenu.style.left = left + window.scrollX + "px";
        tokenMenu.style.top = r.top - tokenMenu.offsetHeight - 6 + window.scrollY + "px";
    }

    function closeMenu() {
        if (!tokenMenu) return;
        tokenMenu.hidden = true;
        menuToken = null;
    }

    function isMenuOpen() {
        return tokenMenu && !tokenMenu.hidden;
    }

    // ---- two-step keyboard deletion -------------------------------------

    // Keys an open menu acts on itself. Anything else typed in the composer means the
    // cataloguer has moved on, so the menu closes rather than lingering somewhere a much
    // later Backspace could confirm a deletion they had forgotten was pending.
    function isMenuHotkey(key) {
        return (
            key === "s" ||
            key === "S" ||
            key === "x" ||
            key === "X" ||
            key === "Backspace" ||
            key === "Delete" ||
            key === "Escape"
        );
    }

    function isModifierKey(key) {
        return key === "Shift" || key === "Control" || key === "Meta" || key === "Alt";
    }

    // Backspace/Delete beside an element picks it out; a second press removes it.
    // Elements are atomic and expensive to rebuild, so a stray keystroke should never
    // destroy one — but the intermediate step is the ordinary menu the cataloguer
    // already knows from clicking a box (View on Cantus Index, Split, Remove) rather
    // than a selection idiom of its own (3 Aug 2026 feedback). That also means the
    // keyboard reaches every element action, not just deletion.
    //
    // Returns true when the keystroke was consumed. Only fires on a collapsed caret
    // sitting directly against an element, so editing a half-typed search query is
    // untouched — that text is ordinary content and deletes character by character.
    function handleDeleteKey(key) {
        const selection = window.getSelection();
        if (!selection.rangeCount) return false;
        const range = selection.getRangeAt(0);
        if (!range.collapsed) return false;
        const neighbour =
            key === "Backspace" ? nodeBeforeCaret(range) : nodeAfterCaret(range);
        if (!isToken(neighbour)) return false;
        // Already showing this element's menu, so the press is the confirmation. A menu
        // open on some *other* element just retargets — the caret is what decides.
        if (isMenuOpen() && menuToken === neighbour) deleteToken(neighbour);
        else openMenu(neighbour);
        return true;
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
        renderBank(); // it's available again if it came from the bank
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
        token.append(label, cid, document.createElement("wbr")); // trailing break opportunity, see makeToken
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

    let dragToken = null; // reordering a token already in the composer
    let bankDragIndex = -1; // dragging a new element in from the bank (index into bankElements)
    let dropIndicator = null; // blue insertion bar shown while dragging (created in init)

    // Both drag sources share the drop machinery: the only difference is whether the drop
    // moves the dragged token or creates a new one from the bank.
    function isDragging() {
        return !!dragToken || bankDragIndex >= 0;
    }

    function firstClientRect(el) {
        const rects = el.getClientRects();
        return rects.length ? rects[0] : el.getBoundingClientRect();
    }

    function lastClientRect(el) {
        const rects = el.getClientRects();
        return rects.length ? rects[rects.length - 1] : el.getBoundingClientRect();
    }

    function styleWidth(el, property) {
        return parseFloat(getComputedStyle(el)[property]) || 0;
    }

    // Every gap a drop can land in, in document order, as {token, x, top, height}: the bar
    // is drawn at x/top/height and the dragged token lands before `token` (null → append).
    //
    // Each point is anchored to a single LINE FRAGMENT — a token's first rect for the gap
    // before it, the last token's last rect for the gap at the end — never to the union
    // bounding box getBoundingClientRect() returns. That box is what made one gap
    // undroppable (28 Jul 2026 demo feedback): for a token wrapping across two lines the
    // union spans both, so its centre sits in the blank space between them and its left
    // edge is the container's, not the token's. Hit-testing against that centre meant a
    // wrapped token never registered as "after" a pointer to the right of it on its own
    // first line, leaving the gap in front of it unreachable — and only when the text
    // happened to wrap, which is why it did not reproduce on a shorter chant.
    //
    // The bar sits at the true midpoint of the gap when a token ends on the same line just
    // before this one. At a wrapped line start or the very beginning there is no such
    // neighbour, so it falls back to the token's own edge, inset by whatever horizontal
    // margin the token carries. Elements carry none today — the separator space alone
    // spaces them — so the bar sits flush to the edge; the term is kept so it stays
    // evenly placed rather than hugging the token if a margin is ever reintroduced.
    function insertionPoints() {
        const tokens = allTokens().filter(function (t) {
            return t !== dragToken;
        });
        const points = [];
        tokens.forEach(function (token, i) {
            const rect = firstClientRect(token);
            const prev = i > 0 ? lastClientRect(tokens[i - 1]) : null;
            const afterPrevOnThisLine =
                prev && Math.abs(prev.top - rect.top) < 1 && prev.right <= rect.left;
            points.push({
                token: token,
                x: afterPrevOnThisLine
                    ? (prev.right + rect.left) / 2
                    : rect.left - styleWidth(token, "marginLeft"),
                top: rect.top,
                height: rect.height,
            });
        });
        if (tokens.length) {
            const last = tokens[tokens.length - 1];
            const rect = lastClientRect(last);
            points.push({
                token: null, // append
                x: rect.right + styleWidth(last, "marginRight"),
                top: rect.top,
                height: rect.height,
            });
        }
        return points;
    }

    // The gap nearest the pointer. Vertical distance dominates, so a drop never jumps to
    // another line just because a gap there is closer in raw pixels; within a line it's
    // the nearest gap horizontally. Every pointer position resolves to some gap, so the
    // bar can't blink out over a spot that is in fact droppable.
    function nearestInsertionPoint(x, y) {
        let best = null;
        let bestScore = Infinity;
        insertionPoints().forEach(function (point) {
            // 0 while the pointer is level with this line, else the distance off it
            const dy = Math.max(0, point.top - y, y - (point.top + point.height));
            const score = dy * 10000 + Math.abs(point.x - x);
            if (score < bestScore) {
                bestScore = score;
                best = point;
            }
        });
        return best;
    }

    function showDropIndicator(point) {
        if (!dropIndicator) return;
        if (!point) return hideDropIndicator();
        dropIndicator.style.left = point.x - 1 + "px"; // centre the 2px bar on x
        dropIndicator.style.top = point.top + "px";
        dropIndicator.style.height = point.height + "px";
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

    // Dragging a catalogued element out of the bank. It isn't a token yet — one is
    // created only if it lands in the composer.
    function onBankDragStart(e) {
        const chip = e.target.closest && e.target.closest(".cluster-bank-item");
        if (!chip || chip.disabled) return;
        closeMenu();
        closeTypeahead();
        bankDragIndex = Number(chip.dataset.bankIndex);
        chip.classList.add("dragging");
        e.dataTransfer.effectAllowed = "copy";
        // Firefox needs data set for a drag to start.
        e.dataTransfer.setData("text/plain", (bankElements[bankDragIndex] || {}).fulltext || "");
    }

    function onBankDragEnd(e) {
        const chip = e.target.closest && e.target.closest(".cluster-bank-item");
        if (chip) chip.classList.remove("dragging");
        bankDragIndex = -1;
        hideDropIndicator();
    }

    function onDragOver(e) {
        if (!isDragging()) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = dragToken ? "move" : "copy";
        showDropIndicator(nearestInsertionPoint(e.clientX, e.clientY));
    }

    // Drop where the bar was showing: the same nearestInsertionPoint() call decides both,
    // so the token can't land somewhere other than the gap the cataloguer was shown.
    function onDrop(e) {
        if (!isDragging()) return;
        e.preventDefault();
        hideDropIndicator();
        const point = nearestInsertionPoint(e.clientX, e.clientY);
        if (bankDragIndex >= 0) {
            // No insertion point means an empty composer — the element becomes its first.
            insertBankElement(bankDragIndex, point ? point.token : null);
            bankDragIndex = -1;
            return;
        }
        if (!point) return; // the only token: nowhere else for it to go
        pushUndo();
        if (point.token) {
            composer.insertBefore(dragToken, point.token);
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
                return;
            }
            // Unticking flattens the cluster back to plain text, so the interleaved
            // components stop being saved as elements. That's destructive once any exist
            // — confirm, and put the tick back if the cataloguer backs out.
            const components = componentTokens().length;
            if (
                components > 0 &&
                !window.confirm(
                    "This will discard the " +
                        components +
                        (components === 1 ? " component element" : " component elements") +
                        " you have composed, keeping only the flattened text. Continue?"
                )
            ) {
                hasComponentCheckbox.checked = true;
                return;
            }
            deactivateCluster();
        });

        // Reloading is an explicit button, not a silent blur (which was undiscoverable);
        // keep it enabled only while there's a Cantus ID to fetch by.
        if (cantusIdInput) {
            cantusIdInput.addEventListener("input", updateReloadButton);
            // The bank is keyed on the Cantus ID, so refresh it once the field settles.
            // On "change" rather than "input": the bank costs upstream requests, and
            // every keystroke of a Cantus ID would fire one against a partial ID.
            cantusIdInput.addEventListener("change", function () {
                if (currentCluster) loadBank();
            });
        }
        if (reloadButton) {
            reloadButton.addEventListener("click", reloadBaseText);
        }

        composer.addEventListener("input", onComposerInput);
        composer.addEventListener("beforeinput", onBeforeInput);

        // Track the caret while the composer holds the selection, so clicking a bank chip
        // over in the sidebar — which blurs the composer — still knows where to insert.
        document.addEventListener("selectionchange", rememberCaret);

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
            // Backspace/Delete against an element: open its menu, then remove on the
            // repeat. Checked before the typeahead block so a stray dropdown doesn't
            // swallow it; handleDeleteKey declines whenever the caret isn't touching an
            // element, and the keystroke falls through to ordinary text editing.
            if (e.key === "Backspace" || e.key === "Delete") {
                if (handleDeleteKey(e.key)) {
                    e.preventDefault();
                    // Without this the document-level menu hotkeys below would see the
                    // menu this very keystroke just opened and delete on the same press.
                    e.stopPropagation();
                    return;
                }
            } else if (isMenuOpen() && !isMenuHotkey(e.key) && !isModifierKey(e.key)) {
                // The cataloguer moved on (typing, arrows): drop the menu so a later
                // Backspace can't confirm a deletion they'd forgotten was pending.
                closeMenu();
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

        // hotkeys while a box's menu is open: 's' splits (core/proposed); 'x' deletes,
        // and so do Backspace/Delete — with the box already picked out and its menu on
        // screen the intent is unambiguous, so the delete keys shouldn't be inert here.
        document.addEventListener("keydown", function (e) {
            if (isMenuOpen()) {
                if ((e.key === "s" || e.key === "S") && isSplittable(menuToken)) {
                    e.preventDefault();
                    enterSplitMode(menuToken);
                    return;
                }
                if (
                    e.key === "x" ||
                    e.key === "X" ||
                    e.key === "Backspace" ||
                    e.key === "Delete"
                ) {
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

        // element bank: drag a chip into the composer, or click to add it at the cursor
        // (the chips are buttons, so the keyboard path works without a drag).
        if (bankItems) {
            bankItems.addEventListener("dragstart", onBankDragStart);
            bankItems.addEventListener("dragend", onBankDragEnd);
            bankItems.addEventListener("click", function (e) {
                const chip = e.target.closest(".cluster-bank-item");
                // Drop it where the cataloguer left the caret rather than at the end.
                if (chip && !chip.disabled) {
                    insertBankElement(Number(chip.dataset.bankIndex), caretBeforeToken);
                }
            });
        }

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

        // No scroll handler: both overlays are absolutely positioned in page coordinates,
        // so the browser moves them with the document. A resize genuinely changes how much
        // room the dropdown has, so that one still re-measures.
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
        bank = document.getElementById("cluster-bank");
        bankItems = document.getElementById("cluster-bank-items");
        bankStatus = document.getElementById("cluster-bank-status");
        bankHeading = document.getElementById("cluster-bank-heading");
        const controls = document.getElementById("cluster-controls");
        if (!textarea || !composer || !controls || !hasComponentCheckbox || !hint) return;

        // The instructions are a hover/focus tooltip on the help icon now. Bootstrap's
        // tooltips are opt-in, so upgrade the icon's title into one; without Bootstrap the
        // plain title attribute still shows the same text as a native tooltip.
        if (window.bootstrap && window.bootstrap.Tooltip) {
            new window.bootstrap.Tooltip(hint);
        }

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
