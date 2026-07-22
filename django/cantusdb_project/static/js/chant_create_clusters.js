/*
 * Chant cluster prototype (issue #2128) — enhancement to the Create Chant page.
 *
 * Turns the "Full text (standardized spelling)" field into an element composer:
 * core elements are pre-filled as inline tokens, general elements can be dragged
 * in from the sidebar bank, and free text is typed in between. The real textarea
 * is hidden while a cluster is active and kept in sync so the form still submits.
 *
 * Data is hardcoded for now; eventually it will come from a table that records
 * which chants have general elements (see #2128).
 */
(function () {
    "use strict";

    const CLUSTER_DEMO_DATA = [
        {
            key: "kyrie-trope",
            label: "Kyrie (troped)",
            core: [
                { id: "core-kyrie-1", text: "Kyrie" },
                { id: "core-eleison-1", text: "eleison" },
                { id: "core-christe", text: "Christe" },
                { id: "core-eleison-2", text: "eleison" },
                { id: "core-kyrie-2", text: "Kyrie" },
                { id: "core-eleison-3", text: "eleison" },
            ],
            general: [
                { id: "gen-fons-bonitatis", text: "fons bonitatis" },
                { id: "gen-pater-ingenite", text: "pater ingenite" },
                { id: "gen-a-quo-cuncta", text: "a quo bona cuncta procedunt" },
                { id: "gen-magne-deus", text: "magnae potentiae" },
                { id: "gen-rex-genitor", text: "rex genitor" },
            ],
        },
        {
            key: "hymn-veni-creator",
            label: "Hymn — Veni Creator Spiritus",
            core: [
                { id: "core-vc-1", text: "Veni Creator Spiritus, mentes tuorum visita" },
                { id: "core-vc-2", text: "Imple superna gratia quae tu creasti pectora" },
                { id: "core-vc-3", text: "Qui Paraclitus diceris, donum Dei altissimi" },
            ],
            general: [
                { id: "gen-dox-deo-patri", text: "Deo Patri sit gloria, et Filio qui a mortuis surrexit, ac Paraclito" },
                { id: "gen-dox-sit-laus", text: "Sit laus Deo Patri, summo Christo decus, Spiritui Sancto honor unus" },
                { id: "gen-gloria-patri", text: "Gloria Patri et Filio et Spiritui Sancto" },
                { id: "gen-amen", text: "Amen" },
            ],
        },
    ];

    let textarea, composer, select, hasGeneralCheckbox, bank, card;
    let currentCluster = null;
    let dragEl = null; // general element currently being dragged from the bank
    let savedRange = null; // last caret position inside the composer (for click-insert)

    // ---- tokens ---------------------------------------------------------

    function makeToken(kind, element) {
        const token = document.createElement("span");
        token.className = "cluster-token cluster-token--" + kind;
        token.contentEditable = "false";
        token.dataset.kind = kind;
        token.dataset.elementId = element.id;
        token.dataset.text = element.text;

        const label = document.createElement("span");
        label.className = "token-label";
        label.textContent = element.text;

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

        token.append(label, remove);
        return token;
    }

    function appendToken(token) {
        composer.append(document.createTextNode(" "), token, document.createTextNode(" "));
        syncToTextarea();
    }

    function insertTokenAtRange(range, token) {
        if (!composer.contains(range.startContainer)) {
            appendToken(token);
            return;
        }
        range.insertNode(token);
        // pad with spaces so words stay separated and a caret can sit either side
        token.after(document.createTextNode(" "));
        token.before(document.createTextNode(" "));
        syncToTextarea();
    }

    // ---- caret helpers --------------------------------------------------

    function caretRangeFromPoint(x, y) {
        if (document.caretRangeFromPoint) {
            return document.caretRangeFromPoint(x, y); // Chrome/Safari
        }
        if (document.caretPositionFromPoint) {
            const pos = document.caretPositionFromPoint(x, y); // Firefox
            if (!pos) return null;
            const range = document.createRange();
            range.setStart(pos.offsetNode, pos.offset);
            range.collapse(true);
            return range;
        }
        return null;
    }

    // ---- sync to the real form field ------------------------------------

    function syncToTextarea() {
        const parts = [];
        composer.childNodes.forEach(function (node) {
            if (node.nodeType === Node.TEXT_NODE) {
                parts.push(node.nodeValue);
            } else if (node.classList && node.classList.contains("cluster-token")) {
                parts.push(node.dataset.text);
            } else if (node.nodeName === "BR") {
                parts.push(" ");
            } else {
                parts.push(node.textContent);
            }
        });
        textarea.value = parts.join("").replace(/\s+/g, " ").trim();
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
        populateBank(cluster);
        card.hidden = !hasGeneralCheckbox.checked;
        syncToTextarea();
    }

    function deactivateCluster() {
        syncToTextarea(); // preserve whatever was composed back into the textarea
        composer.hidden = true;
        textarea.style.display = "";
        currentCluster = null;
        bank.innerHTML = "";
        card.hidden = true;
    }

    // ---- sidebar bank ---------------------------------------------------

    function populateBank(cluster) {
        bank.innerHTML = "";
        cluster.general.forEach(function (element) {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "bank-item";
            item.textContent = element.text;
            item.draggable = true;
            item.title = "Drag into the full text, or click to insert at the cursor";
            item.addEventListener("dragstart", function (e) {
                dragEl = element;
                e.dataTransfer.effectAllowed = "copy";
                e.dataTransfer.setData("text/plain", element.text);
            });
            item.addEventListener("dragend", function () {
                dragEl = null;
            });
            item.addEventListener("click", function () {
                const token = makeToken("general", element);
                if (savedRange && composer.contains(savedRange.startContainer)) {
                    insertTokenAtRange(savedRange, token);
                } else {
                    appendToken(token);
                }
            });
            bank.appendChild(item);
        });
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
            card.hidden = !(hasGeneralCheckbox.checked && currentCluster);
        });

        composer.addEventListener("input", syncToTextarea);

        composer.addEventListener("dragover", function (e) {
            if (!dragEl) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            const range = caretRangeFromPoint(e.clientX, e.clientY);
            if (range) {
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }
        });
        composer.addEventListener("drop", function (e) {
            if (!dragEl) return;
            e.preventDefault();
            const range = caretRangeFromPoint(e.clientX, e.clientY);
            const token = makeToken("general", dragEl);
            if (range) {
                insertTokenAtRange(range, token);
            } else {
                appendToken(token);
            }
            dragEl = null;
        });

        // remember the caret inside the composer so bank clicks insert there
        document.addEventListener("selectionchange", function () {
            const sel = window.getSelection();
            if (sel.rangeCount && composer.contains(sel.anchorNode)) {
                savedRange = sel.getRangeAt(0).cloneRange();
            }
        });
    }

    function init() {
        textarea = document.getElementById("id_manuscript_full_text_std_spelling");
        composer = document.getElementById("cluster-composer");
        select = document.getElementById("cluster-select");
        hasGeneralCheckbox = document.getElementById("has-general-elements");
        bank = document.getElementById("general-elements-bank");
        card = document.getElementById("general-elements-card");
        const controls = document.getElementById("cluster-controls");
        if (!textarea || !composer || !select || !controls) return;

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
