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
 *
 * For a troped chant the seed is not that chant's own text but the text of the BASE
 * CHANT Cantus Index names for it (#2189) — its own text has the base chant cut down
 * to cue words, so it is not something a split can repair. The endpoint decides this
 * and reports which Cantus ID the text came from, but the composer does not show it:
 * cataloguers work from the text in front of them and don't need the provenance.
 * Note the ID in the FIELD stays the troped one throughout: the
 * element bank probes it for components (g01349.tp14:01), which hang off the troped
 * chant and not the base, so rewriting the field to the base ID would empty the bank.
 */
(function () {
    "use strict";

    const MAX_UNDO = 50;
    const CI_MIN_QUERY = 3; // characters before we query Cantus Index (matches the Input Tool)
    const CI_DEBOUNCE_MS = 250; // wait for a typing pause before firing a request
    const BASE_TEXT_URL = "/ci-base-text/"; // + cantus_id → { base_text, cantus_id }
    // Cantus Index's public chant page, for the menu's "View on Cantus Index" link.
    // cantusindex.org (not the uwaterloo host) is what serves /id/ today.
    const CI_ID_URL = "https://cantusindex.org/id/";
    const CLUSTER_ELEMENTS_URL = "/ci-cluster-elements/"; // + cantus_id → { elements }
    // Dropdown sizing, in px. MAX matches the stylesheet's max-height (~10 results);
    // MIN is the smallest list worth showing rather than flipping to the other side.
    const TYPEAHEAD_MAX_HEIGHT = 448; // 28rem
    const TYPEAHEAD_MIN_HEIGHT = 120;

    let textarea, composer, cantusIdInput, hasComponentCheckbox, hint, status, undoButton, reloadButton, tray;
    // The Clean up menu (#2165): the automatic split, then the removal it enables.
    let cleanup, cleanupButton, autoSplitItem, removeSeparatorsItem;
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

    // The bank is a sidebar card, but the cards above it are short, so it floats up near the
    // Input Tool — far above the full text field it belongs to. We drop it down with a
    // margin so its top sits level with the field (#2188). Recomputed on any layout change
    // (via a ResizeObserver on the form) and coalesced into one rAF so a burst of changes
    // doesn't thrash layout.
    let alignScheduled = false;

    // "1 element" / "2 elements", for the confirm dialogs.
    function plural(count, singular, pluralForm) {
        return count + " " + (count === 1 ? singular : pluralForm);
    }

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

    // Splittable in principle AND actually divisible. A one-word element has no boundary to
    // split at, and enterSplitMode already declines it — which left the menu offering a Split
    // that quietly did nothing. Automatic splitting produces plenty of one-word elements
    // ("SANCTUS", "|"), so that dead item is now common enough to be worth withholding.
    function canSplit(node) {
        return (
            isSplittable(node) &&
            String(node.dataset.text).trim().split(/\s+/).filter(Boolean).length > 1
        );
    }

    function allTokens() {
        return Array.from(composer.querySelectorAll(".cluster-token"));
    }

    function componentTokens() {
        return Array.from(composer.querySelectorAll(".cluster-token--component"));
    }

    // Whether the cataloguer has composed anything worth protecting from a wipe. A single
    // core element is just the untouched seed, so it doesn't count: warning about that would
    // put a confirm in front of every stray tick of the checkbox. Anything else — a split, an
    // interleaved component, something sitting in the restore tray — is real work.
    function hasComposedWork() {
        return (
            allTokens().length > 1 || componentTokens().length > 0 || removedCores.length > 0
        );
    }

    // Re-label existing cores after the Cantus ID field changes. Cores display the parent's
    // ID but never store it as their own identity, so this is presentation only — without it
    // the boxes keep showing the ID of the chant they were seeded from, which is a display
    // that has quietly stopped being true.
    function relabelCores() {
        const parent = parentCantusId();
        allTokens()
            .filter(isCoreToken)
            .forEach(function (token) {
                token.dataset.cantusId = parent;
                const cid = token.querySelector(".token-cid");
                // Separator boxes hide their ID in CSS, but keep the data consistent anyway.
                if (cid) cid.textContent = parent;
            });
        syncToTextarea(); // cores carry the parent ID into elements_json
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
        // Every path that changes the elements ends here — normalizeComposer, the seed,
        // undo, deactivation — so this is the one place the Clean up menu's enabled states
        // need refreshing from. Hooking normalizeComposer instead would miss undo.
        updateCleanupMenu();
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
        // Same reason: the selected run and the anchor would be left pointing at nodes that
        // are no longer in the document.
        clearRangeSelection();
        mergeAnchor = null;
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
        scheduleAlign(); // now that it's shown, drop it down to the field
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
                        : "No elements found in Cantus Index for " + cid
                );
                renderBank();
            });
    }

    // Drop the bank down so its top sits level with the full text field. The sidebar card
    // and the field are in independently-floated columns, so nothing but measurement can
    // line them up. Only ever pushes down — the form is long, the sidebar short, so the
    // field is always the lower of the two.
    function alignBankToField() {
        if (!bank) return;
        bank.style.marginTop = ""; // reset before measuring; also the small-screen default
        // Below lg the sidebar stacks under the form, so there's no column beside the field
        // to line up with — leave the bank in normal flow.
        if (bank.hidden || !window.matchMedia("(min-width: 992px)").matches) return;
        const fieldRow = textarea.closest(".row");
        if (!fieldRow) return;
        // The card already carries a top margin (mt-3) for the no-JS / stacked layout. The
        // drop is added ON TOP of it — set the inline value from the shift alone and it
        // would replace that base margin, landing the bank a notch high.
        const base = parseFloat(getComputedStyle(bank).marginTop) || 0;
        const shift =
            fieldRow.getBoundingClientRect().top - bank.getBoundingClientRect().top;
        if (shift > 0) bank.style.marginTop = base + shift + "px";
    }

    // Coalesce a burst of layout changes (a field toggling, the composer growing, a resize)
    // into a single realign on the next frame.
    function scheduleAlign() {
        if (alignScheduled) return;
        alignScheduled = true;
        requestAnimationFrame(function () {
            alignScheduled = false;
            alignBankToField();
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
        if (cleanup) cleanup.hidden = false;
        updateReloadButton();
        updateCleanupMenu();
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
        clearRangeSelection();
        mergeAnchor = null;
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
            const text = cid ? (base.text || "").trim() : preTyped;
            if (text) {
                seedCore(text);
                // For a troped chant the text is the base chant's rather than this Cantus
                // ID's (#2189). The composer used to say so here; cataloguers don't need
                // to know which record the text came from, so it seeds silently.
                setStatus("");
            } else if (cid) {
                setStatus("No base text found in Cantus Index for Cantus ID " + cid + ".");
            } else {
                setStatus("Add a Cantus ID to load the base chant text from Cantus Index.");
            }
        };
        if (!cid) {
            done({ text: "", cantusId: "" });
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

    // GET the standard full text to seed the cores from (one blob; CI doesn't pre-split
    // it), as { text, cantusId }. For a troped chant the endpoint answers with the *base*
    // chant's text and reports which chant that was in `cantus_id`, so the ID need not be
    // the one we asked for. Nothing displays it today — the seed is silent — but it is
    // kept because it is the only signal that the text was redirected. Always resolves; a
    // failure is empty text, which the caller treats as "CI has nothing for this ID".
    function fetchBaseText(cantusId) {
        return fetch(BASE_TEXT_URL + encodeURIComponent(cantusId), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (r) {
                return r.ok ? r.json() : null;
            })
            .then(function (data) {
                return {
                    text: (data && data.base_text) || "",
                    cantusId: (data && data.cantus_id) || "",
                };
            })
            .catch(function () {
                return { text: "", cantusId: "" };
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
        clearRangeSelection();
        mergeAnchor = null;
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
        if (cleanup) cleanup.hidden = true;
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
        if (canSplit(token)) {
            tokenMenu.appendChild(
                menuButton("Split", "s", false, function () {
                    enterSplitMode(token);
                })
            );
        }
        // Merging is offered only towards a neighbour it is allowed with, so the menu never
        // shows an action that would refuse. Shift-click a second box for a longer run.
        if (mergeableNeighbour(token, -1)) {
            tokenMenu.appendChild(
                menuButton("Merge with previous", "p", false, function () {
                    mergeWithNeighbour(token, -1);
                })
            );
        }
        if (mergeableNeighbour(token, 1)) {
            tokenMenu.appendChild(
                menuButton("Merge with next", "m", false, function () {
                    mergeWithNeighbour(token, 1);
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
            key === "m" ||
            key === "M" ||
            key === "p" ||
            key === "P" ||
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

    // Several boxes at once — a shift-clicked run, or every separator a split found. Each
    // one leaves exactly as deleteToken would take it alone (cores to the restore tray,
    // components just gone), so a run is only a way of naming several deletions; what makes
    // this its own function is that they share one undo step.
    //
    // Deleting the trope text is the main use. Cantus Index catalogues the separate
    // <parent>:NN elements for very few chants, so that text is usually the only record of
    // the trope — hence the tray, and hence cores going into it even in bulk.
    function deleteTokens(tokens) {
        if (!tokens.length) return;
        exitSplitMode();
        closeMenu();
        pushUndo();
        // Indexes are read from the composer as it stands, before anything leaves it, so the
        // tray restores each element to the place it actually came from.
        const order = allTokens();
        let hadComponent = false;
        tokens.forEach(function (token) {
            if (isCoreToken(token)) {
                removedCores.push({
                    id: token.dataset.text,
                    text: token.dataset.text,
                    index: order.indexOf(token),
                });
            } else {
                hadComponent = true;
            }
            token.remove();
        });
        clearRangeSelection();
        normalizeComposer();
        renderTray();
        if (hadComponent) renderBank(); // a bank element it held is on offer again
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

    // ---- merge adjacent elements (#2165) --------------------------------
    //
    // The inverse of Split, for putting back together what a split — by hand or automatic —
    // divided too finely. Everything the automatic split produces is a core element, so a
    // merge is plain text concatenation with no type to reconcile.
    //
    // Two ways in, over one operation:
    //   - the box's own menu offers "Merge with previous/next", and stays open on the result,
    //     so m,m,m glues a run without re-clicking;
    //   - shift-clicking a second box selects the whole run between the two and offers
    //     "Merge N elements", for a split that came out too fine to fix a pair at a time.

    let mergeAnchor = null; // the box a plain click last landed on: shift-click's origin
    let selectedRange = []; // the run a shift-click has selected, in document order

    // A run is mergeable when it is at least two boxes, holds no separator, and is all of
    // one kind. Separators are punctuation to be removed, not text to be folded into an
    // element; and merging across kinds would turn core text into component text or the
    // reverse, which is not an operation this tool performs. An approved component owns its
    // Cantus ID for its whole text, so it is excluded for the same reason it can't be split.
    function isMergeable(tokens) {
        if (tokens.length < 2) return false;
        const kind = tokens[0].dataset.kind;
        const proposed = isProposedToken(tokens[0]);
        return tokens.every(function (token) {
            return (
                token.dataset.autoKind !== "separator" &&
                token.dataset.kind === kind &&
                isProposedToken(token) === proposed &&
                (isCoreToken(token) || proposed)
            );
        });
    }

    // Fuse a run into one element. Returns the new element, or null if the run can't merge.
    function mergeTokens(tokens) {
        if (!isMergeable(tokens)) return null;
        exitSplitMode();
        closeMenu(); // the boxes below are about to be replaced
        pushUndo();
        const text = tokens
            .map(function (token) {
                return token.dataset.text;
            })
            .join(" ")
            .replace(/\s+/g, " ")
            .trim();
        // Same kind in, same kind out — as performSplit does in the other direction.
        const merged = isCoreToken(tokens[0])
            ? makeCoreToken(text)
            : makeToken("component", text, "", true);
        // Deliberately no data-auto-kind: the result is the cataloguer's judgement, not the
        // rules', so it stops wearing the colour the automatic split gave it — and stops
        // being swept up by "Remove separators"/"Remove component elements".
        tokens[0].replaceWith(merged);
        tokens.slice(1).forEach(function (token) {
            token.remove();
        });
        clearRangeSelection();
        normalizeComposer();
        return merged;
    }

    // The neighbour on one side, if merging with it is allowed. direction: -1 before, +1 after.
    function mergeableNeighbour(token, direction) {
        const tokens = allTokens();
        const at = tokens.indexOf(token);
        if (at < 0) return null;
        const other = tokens[at + direction];
        if (!other) return null;
        const run = direction < 0 ? [other, token] : [token, other];
        return isMergeable(run) ? other : null;
    }

    function mergeWithNeighbour(token, direction) {
        const other = mergeableNeighbour(token, direction);
        if (!other) return;
        const merged = mergeTokens(direction < 0 ? [other, token] : [token, other]);
        // Leave the menu up on the result so the same key merges again straight away.
        if (merged) openMenu(merged);
    }

    function clearRangeSelection() {
        selectedRange.forEach(function (token) {
            delete token.dataset.selected;
        });
        selectedRange = [];
    }

    // Select the run between the anchor and the shift-clicked box, inclusive. Taking every
    // box in the index span makes the run contiguous by construction.
    function selectRangeTo(token) {
        const tokens = allTokens();
        const from = tokens.indexOf(mergeAnchor);
        const to = tokens.indexOf(token);
        if (from < 0 || to < 0 || from === to) return;
        clearRangeSelection();
        selectedRange = tokens.slice(Math.min(from, to), Math.max(from, to) + 1);
        selectedRange.forEach(function (selected) {
            selected.dataset.selected = "true";
        });
        openRangeMenu();
    }

    // The selected run's menu: fold it into one element, or delete the lot. Merge is shown
    // disabled rather than withheld when the run can't take it, so the reason is legible
    // where the cataloguer is looking instead of nothing appearing to happen. Delete has no
    // such condition — a run of anything can be deleted, and separators mixed in with trope
    // text is the ordinary case after a split.
    function openRangeMenu() {
        if (selectedRange.length < 2) return;
        closeMenu();
        closeTypeahead();
        // positionMenu anchors on menuToken; the first box in the run is where it should sit.
        menuToken = selectedRange[0];
        tokenMenu.innerHTML = "";
        const run = selectedRange.slice();
        const merge = menuButton("Merge " + run.length + " elements", "m", false, function () {
            mergeTokens(run);
        });
        merge.disabled = !isMergeable(run);
        tokenMenu.appendChild(merge);
        tokenMenu.appendChild(
            menuButton("Delete " + run.length + " elements", "x", true, function () {
                deleteTokens(run);
            })
        );
        tokenMenu.hidden = false;
        positionMenu();
    }

    // A document-level hotkey must not fire while the cataloguer is typing somewhere else:
    // "m" is the merge key only when the composer is what holds focus.
    function isTypingElsewhere(target) {
        if (!target || target === composer || composer.contains(target)) return false;
        if (tokenMenu && tokenMenu.contains(target)) return false;
        const tag = (target.tagName || "").toLowerCase();
        return (
            tag === "input" || tag === "textarea" || tag === "select" || !!target.isContentEditable
        );
    }

    // ---- automatic split of Cantus Index text (#2165) --------------------

    // The rules themselves live in chant_create_auto_split.js, loaded just before this file.
    // They are pure functions over a string — no DOM, no page state — and keeping them apart
    // is what lets tests/js/auto_split.test.js run them under Node with no browser. Read that
    // file's header comment for the conventions and the evidence behind them.
    //
    // If it somehow fails to load, the composer still works and the Clean up menu simply finds
    // nothing to do, which is the right way for a missing rule set to fail.
    function autoSplitText(text) {
        return window.ChantAutoSplit ? window.ChantAutoSplit.splitText(text) : [];
    }

    // ---- the Clean up menu's two actions --------------------------------

    function separatorTokens() {
        return allTokens().filter(function (token) {
            return isCoreToken(token) && token.dataset.autoKind === "separator";
        });
    }

    // "Split automatically". Splits every core element wherever the text says so with
    // certainty, and no further. A segment with no signal in it is left as one element
    // rather than guessed at, so a text like ah47196 — where the "|" boundaries are
    // unambiguous but nothing distinguishes the Gloria's own words from the trope's — still
    // gets its separators picked out, with everything between them left whole.
    //
    // Reports nothing: the composer itself is the feedback, and the outcome is visible in
    // it. Silence is safe here because the boundaries we are sure of are split in every
    // case, so a click that finds anything at all shows it.
    function autoSplitAll() {
        if (!currentCluster) return;
        const plans = [];
        allTokens()
            .filter(isCoreToken)
            .forEach(function (token) {
                const parts = autoSplitText(token.dataset.text);
                if (parts.length < 2) return; // nothing certain enough to divide
                plans.push({ token: token, parts: parts });
            });
        if (!plans.length) return;
        exitSplitMode();
        closeMenu();
        pushUndo();
        plans.forEach(function (plan) {
            const replacements = [];
            plan.parts.forEach(function (part, i) {
                // A space between the new elements, as performSplit leaves: normalizeComposer
                // drops it again, and the gap on screen is the token margin.
                if (i > 0) replacements.push(document.createTextNode(" "));
                const token = makeCoreToken(part.text);
                // Only the separators are marked. The rest are cores indistinguishable from
                // hand-made ones, which is the whole point — there is nothing to record.
                if (part.hint === "separator") token.dataset.autoKind = "separator";
                replacements.push(token);
            });
            plan.token.replaceWith.apply(plan.token, replacements);
        });
        normalizeComposer();
    }

    // "Remove separators". The "|"-type markers are core tokens like any other, so they
    // leave by the same path a hand-deleted core does — into the restore tray, recoverable —
    // as one undo step for the whole batch.
    //
    // The trope text has no action of its own: the rules no longer claim to know which
    // elements it is, so removing it is the cataloguer's own deletion — one box from its
    // menu, or a shift-clicked run at once.
    function removeSeparators() {
        if (!currentCluster) return;
        deleteTokens(separatorTokens()); // declines an empty run itself
    }

    // Neither action is offered when it would do nothing. Called from normalizeComposer, so
    // it tracks every structural change including undo.
    function updateCleanupMenu() {
        if (!cleanupButton) return;
        cleanupButton.disabled = !currentCluster;
        if (autoSplitItem) {
            // Greyed out when nothing in the composer holds a boundary the rules are sure of,
            // so a plain untroped chant like 007989 says so before the click rather than
            // after. This runs the rules over every core element on every structural change;
            // measured over all 4,325 Cantus Index texts that costs ~45 µs for a typical one
            // and under 2 ms for a composer holding 40 of them, with the worst case in the
            // whole corpus — a single 12,000-character un-split blob — at ~2.4 ms. Cheap
            // enough that caching it would only be a way of getting it wrong.
            autoSplitItem.disabled =
                !currentCluster ||
                !allTokens()
                    .filter(isCoreToken)
                    .some(function (token) {
                        return autoSplitText(token.dataset.text).length > 1;
                    });
        }
        if (removeSeparatorsItem) {
            removeSeparatorsItem.disabled = !currentCluster || separatorTokens().length === 0;
        }
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
            // Unticking flattens the cluster back to plain text, so the composed elements
            // stop being saved as elements. That's destructive once any exist — confirm, and
            // put the tick back if the cataloguer backs out. Counts every element, not just
            // the interleaved components: a split into cores is work too, and losing it
            // silently was the complaint.
            const composed = allTokens().length;
            if (
                hasComposedWork() &&
                !window.confirm(
                    "This will discard the " +
                        plural(composed, "element", "elements") +
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
                if (!currentCluster) return;
                loadBank();
                // The composer is holding the *previous* Cantus ID's base text, so leaving it
                // alone silently is the one outcome that can't be right: the field and the
                // elements would describe different chants, and unticking the checkbox later
                // would then reseed without warning and take the work with it. With nothing
                // composed yet there is nothing to lose, so just refetch; with work in
                // progress, ask before discarding it.
                if (!hasComposedWork()) {
                    reseed("");
                    return;
                }
                if (
                    window.confirm(
                        "The Cantus ID has changed. Reload the base text from Cantus Index for " +
                            parentCantusId() +
                            "? This discards the elements composed so far."
                    )
                ) {
                    reseed("");
                    return;
                }
                // Keeping the elements: they belong to the new parent now, so re-label them.
                relabelCores();
            });
        }
        if (reloadButton) {
            reloadButton.addEventListener("click", reloadBaseText);
        }

        // The Clean up menu's two actions, in the order they are meant to be used: split the
        // Cantus Index text, then drop the markers the split picked out of it. Deleting the
        // trope text is not one of them — that is the cataloguer's judgement, made in the
        // composer on the elements they choose.
        if (autoSplitItem) {
            autoSplitItem.addEventListener("click", autoSplitAll);
        }
        if (removeSeparatorsItem) {
            removeSeparatorsItem.addEventListener("click", removeSeparators);
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
                // Shift extends from the last plainly-clicked box to this one, taking the whole
                // run between them; a plain click drops any run and becomes the new anchor.
                if (e.shiftKey && mergeAnchor && mergeAnchor !== token) {
                    selectRangeTo(token);
                    return;
                }
                clearRangeSelection();
                mergeAnchor = token;
                openMenu(token);
            } else {
                clearRangeSelection();
                mergeAnchor = null;
                closeMenu();
                refreshTypeahead(); // clicked in free space → reveal components
            }
        });

        // Shift-click means a range of elements here, not a range of text. Without this the
        // browser also drags its own selection across the boxes, which then fights the caret
        // bookkeeping the composer depends on.
        composer.addEventListener("mousedown", function (e) {
            if (!e.shiftKey || !e.target.closest) return;
            if (e.target.closest(".cluster-token")) e.preventDefault();
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
            } else if (
                (isMenuOpen() || selectedRange.length) &&
                !isMenuHotkey(e.key) &&
                !isModifierKey(e.key)
            ) {
                // The cataloguer moved on (typing, arrows): drop the menu so a later
                // Backspace can't confirm a deletion they'd forgotten was pending — and drop
                // the selected run with it. The two have to die together: leaving a run picked
                // out after its menu had gone meant typing "am" into the field swallowed the
                // "m" and merged the run instead.
                closeMenu();
                clearRangeSelection();
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

        // Hotkeys for what is currently picked out: a selected run, or a box with its menu
        // open. 's' splits (core/proposed), 'm'/'p' merge, 'x' deletes — and so do
        // Backspace/Delete on a single box, where the menu on screen makes the intent
        // unambiguous, so the delete keys shouldn't be inert.
        document.addEventListener("keydown", function (e) {
            // Escape drops whatever is pending, from wherever the focus happens to be: a
            // stale selection is exactly what shouldn't survive a keystroke meant to clear it.
            if (e.key === "Escape") {
                if (splittingToken()) exitSplitMode();
                else {
                    clearRangeSelection();
                    closeMenu();
                }
                return;
            }
            // Two conditions on every key below, and both matter: something has to be picked
            // out for the key to act on, and the composer has to be what holds the focus. One
            // gate for all of them rather than a check per key — an "x" typed into the Feast
            // field must never be able to delete an element, whichever key it is.
            if (isTypingElsewhere(e.target)) return;
            // A selected run describes several boxes, so only its own actions apply: the
            // single-box hotkeys below would each act on the anchor alone. Backspace/Delete
            // are left out on purpose — beside the caret they already mean "the element I am
            // next to", and 'x' is the key the run's own menu shows.
            if (selectedRange.length > 1) {
                if (e.key === "m" || e.key === "M") {
                    e.preventDefault();
                    mergeTokens(selectedRange.slice());
                } else if (e.key === "x" || e.key === "X") {
                    e.preventDefault();
                    deleteTokens(selectedRange.slice());
                }
                return;
            }
            if (!isMenuOpen()) return;
            if ((e.key === "s" || e.key === "S") && canSplit(menuToken)) {
                e.preventDefault();
                enterSplitMode(menuToken);
                return;
            }
            if (e.key === "m" || e.key === "M") {
                e.preventDefault();
                mergeWithNeighbour(menuToken, 1);
                return;
            }
            if (e.key === "p" || e.key === "P") {
                e.preventDefault();
                mergeWithNeighbour(menuToken, -1);
                return;
            }
            if (e.key === "x" || e.key === "X" || e.key === "Backspace" || e.key === "Delete") {
                e.preventDefault();
                deleteToken(menuToken);
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
            scheduleAlign();
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
            // The field's position shifts whenever the form reflows — a project's extra
            // fields toggling, the composer growing as elements are added, the window
            // resizing. Re-drop the bank to match on any of it. Observing the form (not the
            // bank) can't feed back into itself, since the bank sits in the other column.
            if (window.ResizeObserver) {
                new ResizeObserver(scheduleAlign).observe(form);
            }
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
        cleanup = document.getElementById("cluster-cleanup");
        cleanupButton = document.getElementById("cluster-cleanup-toggle");
        autoSplitItem = document.getElementById("cluster-auto-split");
        removeSeparatorsItem = document.getElementById("cluster-remove-separators");
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
