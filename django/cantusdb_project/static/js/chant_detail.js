function togglePrevious() {
    const x = document.getElementById("previousDiv");
    const toggle = document.getElementById(event.target.id);
    if (x.style.display === "none") {
        x.style.display = "block";
        toggle.innerHTML = "Hide previous chants ▴";
    } else {
        x.style.display = "none";
        toggle.innerHTML = "Display previous chants ▴";
    }
}

function toggleNext() {
    const x = document.getElementById("nextDiv");
    const toggle = document.getElementById(event.target.id);
    if (x.style.display === "none") {
        x.style.display = "block";
        toggle.innerHTML = "Hide next chants ▾";
    } else {
        x.style.display = "none";
        toggle.innerHTML = "Display next chants ▾";
    }
}

function jumpToFolio(sourceId) {
    const url = new URL("chants/", window.location.origin);
    const folio = document.getElementById("folioSelect").options[document.getElementById("folioSelect").selectedIndex].value;
    url.searchParams.set("source", sourceId);
    url.searchParams.set("folio", folio);
    window.location.assign(url);
}


// Values from our database and from Cantus Index are added to the page as
// text, never as HTML, and links only go to http(s) addresses (#2384).

/**
 * The address to link to, or "" if it isn't a web address. Our own links
 * are relative ("/chant/123"); links from Cantus Index must be absolute.
 */
function safeHref(value, allowRelative = false) {
    if (value === null || value === undefined || value === "") {
        return "";
    }
    try {
        const url = allowRelative
            ? new URL(String(value), window.location.origin)
            : new URL(String(value));
        return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
    } catch (e) {
        return "";
    }
}

function appendText(parent, text) {
    if (text !== null && text !== undefined && text !== "") {
        parent.appendChild(document.createTextNode(String(text)));
    }
}

function appendBold(parent, text) {
    const bold = document.createElement("b");
    appendText(bold, text);
    parent.appendChild(bold);
    return bold;
}

/** A link opening in a new tab, or plain text if the address isn't safe. */
function appendLink(parent, text, href, allowRelative = false) {
    const safe = safeHref(href, allowRelative);
    const element = document.createElement(safe ? "a" : "span");
    if (safe) {
        element.setAttribute("href", safe);
        element.setAttribute("target", "_blank");
        element.setAttribute("rel", "noopener");
    }
    appendText(element, text);
    parent.appendChild(element);
    return element;
}

/** One row of the melodies table, from our ajax melody list. */
function melodyRow(chant) {
    const row = document.createElement("tr");

    // the first cell contains chant information
    const chantCell = document.createElement("td");
    chantCell.classList.add("text-wrap");
    if (chant.siglum) {
        if (chant.source_link) {
            appendLink(chantCell, chant.siglum, chant.source_link, true);
        } else {
            appendText(chantCell, chant.siglum);
        }
    }
    chantCell.appendChild(document.createElement("br"));
    if (chant.folio) { appendText(chantCell, `${chant.folio} | `); }
    if (chant.service__name) { appendText(chantCell, `${chant.service__name} `); }
    if (chant.genre__name) { appendBold(chantCell, `${chant.genre__name} `); }
    if (chant.position) { appendText(chantCell, chant.position); }
    chantCell.appendChild(document.createElement("br"));
    if (chant.feast__name) { appendText(chantCell, chant.feast__name); }
    chantCell.appendChild(document.createElement("br"));
    appendText(chantCell, "Cantus ID: ");
    appendLink(chantCell, chant.cantus_id, chant.ci_link, true);
    row.appendChild(chantCell);

    // the second cell contains the volpiano and text
    const melodyCell = document.createElement("td");
    const volpiano = document.createElement("div");
    volpiano.setAttribute("class", "font-volpiano text-nowrap");
    appendText(volpiano, chant.volpiano);
    melodyCell.appendChild(volpiano);
    melodyCell.appendChild(document.createElement("br"));
    if (chant.mode) {
        appendText(melodyCell, "M:");
        appendBold(melodyCell, `${chant.mode} `);
    }
    if (chant.manuscript_full_text_std_spelling) {
        const textDiv = document.createElement("div");
        textDiv.classList.add("text-nowrap");
        appendLink(textDiv, chant.manuscript_full_text_std_spelling, chant.chant_link, true);
        melodyCell.appendChild(textDiv);
    }
    row.appendChild(melodyCell);
    return row;
}

function renderMelodies(melodyDiv, data) {
    melodyDiv.textContent = "";
    appendText(melodyDiv, "Displaying ");
    appendBold(melodyDiv, data.concordance_count);
    appendText(melodyDiv, " melodies from the following databases: ");

    const wrapper = document.createElement("div");
    wrapper.classList.add("table-responsive");
    const table = document.createElement("table");
    table.id = "melodyTable";
    table.setAttribute("class", "table table-bordered table-sm small w-100");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const [label, className] of [["Chant", "text-wrap w-25"], ["Melody", "text-wrap"]]) {
        const cell = document.createElement("th");
        cell.setAttribute("scope", "col");
        cell.setAttribute("class", className);
        appendText(cell, label);
        headRow.appendChild(cell);
    }
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    for (const chant of data.concordances) {
        body.appendChild(melodyRow(chant));
    }
    table.appendChild(body);
    wrapper.appendChild(table);
    melodyDiv.appendChild(wrapper);
}

/** One row of the concordance details table, from Cantus Index. */
function concordanceRow(concordance) {
    const row = document.createElement("tr");

    const sourceCell = document.createElement("td");
    appendLink(sourceCell, concordance.siglum, concordance.srclink);
    const folio = document.createElement("span");
    appendText(folio, ", ");
    appendBold(folio, concordance.folio);
    sourceCell.appendChild(folio);
    // Some concordance image links are invalid urls (e.g. "0")
    const image = safeHref(concordance.image);
    if (image) {
        sourceCell.appendChild(document.createElement("br"));
        const imageLink = document.createElement("a");
        imageLink.setAttribute("href", image);
        imageLink.setAttribute("target", "_blank");
        imageLink.setAttribute("rel", "noopener");
        imageLink.classList.add("bi-camera-fill");
        sourceCell.appendChild(imageLink);
    }
    row.appendChild(sourceCell);

    const incipitCell = document.createElement("td");
    appendLink(incipitCell, concordance.incipit, concordance.chantlink);
    row.appendChild(incipitCell);

    const details = [concordance.office, concordance.genre, concordance.position]
        .map(value => (value === null || value === undefined ? "" : value));
    for (const text of [details.join(" | "), concordance.feast, concordance.mode, concordance.db]) {
        const cell = document.createElement("td");
        appendText(cell, text);
        row.appendChild(cell);
    }
    return row;
}

function loadMelodies(cantusId) {
    const melodyDiv = document.getElementById('melodyDiv');
    const loadingPrompt = document.getElementById("melodyLoadingPrompt");
    const melodyButton = document.getElementById("melodyButton");

    const xhttp = new XMLHttpRequest();
    // construct the ajax url with the cantus id parameter
    const url = new URL(`ajax/melody/${cantusId}`, window.location.origin);

    xhttp.open("GET", url);
    xhttp.onload = function () {
        renderMelodies(melodyDiv, JSON.parse(this.response));
        // hide the "loading results" prompt after loading the data
        loadingPrompt.style.display = "none";
    }

    xhttp.onerror = function () {
        // handle errors
        melodyDiv.textContent = "ajax error";
    }

    xhttp.send();
    // display the "loading results" prompt after sending the ajax request
    loadingPrompt.style.display = "inline";
    // hide the "load concordances" button after sending the ajax request
    melodyButton.style.display = "none";
}

function concordanceDetailToggleText(event) {
    const collapseLink = event.target;
    if (collapseLink.innerText.includes("Hide")) {
        collapseLink.innerText = "▶ Show concordance details";
    } else {
        collapseLink.innerText = "▼ Hide concordance details";
    }
}

// Shown when Cantus Index doesn't answer (e.g. it is busy or rate-limiting),
// so readers don't take a failed load for "no concordances" (#2366).
function showConcordancesLoadError(cantusID) {
    const concordancesDiv = document.getElementById("concordancesDiv");
    const message = document.createElement("p");
    message.id = "concordancesLoadError";
    message.textContent = "Unable to load concordances from Cantus Index right now. ";
    const retry = document.createElement("a");
    retry.href = "#";
    retry.textContent = "Try again";
    retry.addEventListener("click", event => {
        event.preventDefault();
        // Removing the message removes the focused link, so keep keyboard
        // focus in this section by moving it to the Concordances heading.
        const heading = document.getElementById("concordances");
        heading.setAttribute("tabindex", "-1");
        heading.focus();
        message.remove();
        getConcordances(cantusID);
    });
    message.appendChild(retry);
    concordancesDiv.appendChild(message);
}

function getConcordances(cantusID) {
    // Remove the concordance button
    const concordanceButton = document.getElementById("concordanceButton");
    concordanceButton.classList.add("d-none");
    // Display the concordance loading status
    const concordancesLoadingStatus = document.getElementById("concordancesLoadingStatus");
    concordancesLoadingStatus.classList.remove("d-none");

    const concordancesDiv = document.getElementById("concordancesDiv");
    const concordancesUrl = new URL(`/cid-concordances/`, window.location.origin);
    concordancesUrl.searchParams.set("cantus_id", cantusID);
    const xhttp = new XMLHttpRequest();
    xhttp.open("GET", concordancesUrl);
    xhttp.onload = function () {
        // Remove the concordance loading status
        const concordancesLoadingStatus = document.getElementById("concordancesLoadingStatus");
        concordancesLoadingStatus.classList.add("d-none");
        if (this.status !== 200) {
            showConcordancesLoadError(cantusID);
            return;
        }
        const concordancesData = JSON.parse(this.response);
        if (Object.keys(concordancesData.databases).length === 0) {
            const noConcordances = document.createElement("p");
            appendText(noConcordances, "No concordances found for Cantus ID ");
            const idLink = appendLink(
                appendBold(noConcordances, ""),
                cantusID,
                `https://cantusindex.org/id/${encodeURIComponent(cantusID)}`,
            );
            idLink.setAttribute("title", `${cantusID} on Cantus Index`);
            appendText(noConcordances, ".");
            concordancesDiv.appendChild(noConcordances);
            return;
        }
        // Create the concordances summary table
        const concordancesSummaryDiv = document.getElementById("concordancesSummaryDiv");
        const concordancesSummaryTable = document.createElement("table");
        concordancesSummaryTable.id = "concordancesSummaryTable";
        concordancesSummaryTable.setAttribute("class", "table table-sm small border-bottom");
        const summaryTableHeader = concordancesSummaryTable.createTHead();
        const summaryHeaderRow = summaryTableHeader.insertRow();
        const summaryHeaderCell = summaryHeaderRow.insertCell();
        summaryHeaderCell.classList.add("border-top-0");
        summaryHeaderCell.innerHTML = "<b>Summary</b>";
        summaryHeaderCell.colSpan = 2;
        const summaryTableBody = concordancesSummaryTable.createTBody();
        for (const [initialism, dbSummary] of Object.entries(concordancesData.databases)) {
            // object returned by json-con API is ordered by the number
            // of concordances in descending order
            const newRow = summaryTableBody.insertRow();
            // The first cell of each row contains the database name
            // and initialism with a link to the database home page
            const dbNameCell = newRow.insertCell();
            const dbNameLink = document.createElement("a");
            dbNameLink.setAttribute("href", safeHref(dbSummary.url));
            dbNameLink.setAttribute("target", "_blank");
            const dbNameLinkText = document.createTextNode(`${dbSummary.name} (${initialism})`);
            dbNameLink.appendChild(dbNameLinkText);
            dbNameCell.appendChild(dbNameLink);
            // The second cell of each row contains the number of concordances
            // linked to the results url on the database
            const concordanceCountCell = newRow.insertCell();
            const concordanceCountLink = document.createElement("a");
            concordanceCountLink.setAttribute("href", safeHref(dbSummary.url_cid));
            concordanceCountLink.setAttribute("target", "_blank");
            if (dbSummary.count > 1) {
                concordanceCountLink.appendChild(document.createTextNode(`${dbSummary.count} concordances`));
            } else if (dbSummary.count === 1) {
                concordanceCountLink.appendChild(document.createTextNode(`${dbSummary.count} concordance`));
            } else {
                concordanceCountLink.appendChild(document.createTextNode(`See concordance(s)`));
            }
            concordanceCountCell.appendChild(concordanceCountLink);
        }
        concordancesSummaryDiv.appendChild(concordancesSummaryTable);
        if (Object.keys(concordancesData.chants).length === 0) {
            return;
        }
        // Create table collapse link
        const collapseLink = document.createElement("button");
        collapseLink.setAttribute("id", "concordanceDetailCollapseButton");
        collapseLink.setAttribute("data-bs-toggle", "collapse");
        collapseLink.setAttribute("data-bs-target", "#concordancesDetailTable");
        collapseLink.setAttribute("type", "button");
        collapseLink.setAttribute("aria-expanded", "true");
        collapseLink.setAttribute("aria-controls", "concordancesDetailTable");
        collapseLink.classList.add("btn", "p-0", "link-color", "link-hover-effect");
        collapseLink.innerHTML = "▼ Hide concordance details";
        collapseLink.addEventListener("click", concordanceDetailToggleText);
        // Create the concordances detail table
        const concordancesTable = document.createElement("table");
        concordancesTable.id = "concordancesDetailTable";
        concordancesTable.setAttribute("class", "mt-3 table table-sm table-bordered small collapse show");
        const headerArray = ["Source", "Incipit", "Office | Genre | Position", "Feast", "Mode", "Database"];
        const headerRow = concordancesTable.createTHead().insertRow();
        for (const header of headerArray) {
            const headerCell = headerRow.insertCell();
            headerCell.classList.add("text-center");
            headerCell.innerHTML = `<b>${header}</b>`;
        }
        var concordancesDetail = Object.values(concordancesData.chants);
        concordancesDetail.sort((a, b) => {
            return (a.siglum || "").localeCompare(b.siglum || "");
        });
        const concordancesTableBody = concordancesTable.createTBody();
        for (const concordance of concordancesDetail) {
            concordancesTableBody.appendChild(concordanceRow(concordance));
        }
        const concordancesTableDiv = document.getElementById("concordancesTableDiv");
        concordancesTableDiv.appendChild(collapseLink);
        concordancesTableDiv.appendChild(concordancesTable);
    }
    xhttp.onerror = function () {
        concordancesLoadingStatus.classList.add("d-none");
        showConcordancesLoadError(cantusID);
    }
    xhttp.send();
}