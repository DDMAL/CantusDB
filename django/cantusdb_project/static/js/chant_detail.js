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


function loadMelodies(cantusId) {
    const melodyDiv = document.getElementById('melodyDiv');
    const loadingPrompt = document.getElementById("melodyLoadingPrompt");
    const melodyButton = document.getElementById("melodyButton");

    const xhttp = new XMLHttpRequest();
    // construct the ajax url with the cantus id parameter
    const url = new URL(`ajax/melody/${cantusId}`, window.location.origin);

    xhttp.open("GET", url);
    xhttp.onload = function () {
        const data = JSON.parse(this.response);
        melodyDiv.innerHTML = `Displaying <b>${data.concordance_count}</b> melodies from the following databases: `;
        melodyDiv.innerHTML += `<table id="melodyTable" class="table table-bordered table-sm small" style="table-layout: fixed; width: 100%;">
                                    <thead>
                                        <tr>
                                            <th scope="col" class="text-wrap" style="width:20%">Chant</th>
                                            <th scope="col" class="text-wrap">Melody</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                    </tbody>
                                </table>`;

        const table = document.getElementById("melodyTable").getElementsByTagName("tbody")[0];

        data.concordances.map(chant => {
            const newRow = table.insertRow(table.rows.length);
            if (chant.siglum) {
                // if the chant has a siglum, display it
                if (chant.source_link) {
                    // if the chant has a source, display the siglum as a hyperlink to the source page
                    newRow.innerHTML += `<td class="text-wrap"><a href="${chant.source_link}" target="_blank">${chant.siglum}</a></td>`;
                } else {
                    // if the chant does not have a source, display the siglum as plain text
                    newRow.innerHTML += `<td class="text-wrap">${chant.siglum}</td>`;
                }
            } else {
                newRow.innerHTML += '<td class="text-wrap"></td>';
            }

            // the first cell contains chant information
            const chantCell = newRow.getElementsByTagName("td")[0];
            chantCell.innerHTML += '<br>';
            if (chant.folio) { chantCell.innerHTML += `${chant.folio} | ` } else { chantCell.innerHTML += '' }
            if (chant.service__name) { chantCell.innerHTML += `${chant.service__name} ` } else { chantCell.innerHTML += '' }
            if (chant.genre__name) { chantCell.innerHTML += `<b>${chant.genre__name} </b>` } else { chantCell.innerHTML += '' }
            if (chant.position) { chantCell.innerHTML += `${chant.position}` } else { chantCell.innerHTML += '' }
            chantCell.innerHTML += '<br>';
            if (chant.feast__name) { chantCell.innerHTML += `${chant.feast__name}` } else { chantCell.innerHTML += '' }
            chantCell.innerHTML += '<br>';
            chantCell.innerHTML += `Cantus ID: <a href="${chant.ci_link}" target="_blank">${chant.cantus_id}</a>`

            // add the second cell to the row
            newRow.innerHTML += `<td>
                                    <div style="font-family: volpiano; font-size: 28px; white-space: nowrap; overflow: hidden; text-overflow: clip;">
                                        ${chant.volpiano}
                                    </div>
                                    <br>
                                </td>`;
            // the second cell contains the volpiano and text
            const melodyCell = newRow.getElementsByTagName("td")[1];
            if (chant.mode) {
                melodyCell.innerHTML += `M:<b>${chant.mode} </b>`;
            } else {
                melodyCell.innerHTML += "";
            }
            if (chant.manuscript_full_text_std_spelling) {
                melodyCell.innerHTML += `<div style="white-space: nowrap; overflow: hidden; text-overflow: clip;">
                                            <a href="${chant.chant_link}" target="_blank">
                                                ${chant.manuscript_full_text_std_spelling}
                                            </a>
                                        </div>`;
            } else {
                melodyCell.innerHTML += ""
            }
        });
        // hide the "loading results" prompt after loading the data
        loadingPrompt.style.display = "none";
    }

    xhttp.onerror = function () {
        // handle errors
        melodyDiv.innerHTML = "ajax error";
    }

    xhttp.send();
    // display the "loading results" prompt after sending the ajax request
    loadingPrompt.style.display = "inline";
    // hide the "load concordances" button after sending the ajax request
    melodyButton.style.display = "none";
}

function concordanceDetailToggleText(event) {
    const collapseLink = event.target;
    if (collapseLink.getAttribute("aria-expanded") === "true") {
        collapseLink.innerHTML = "▶ Show concordance details";
    } else {
        collapseLink.innerHTML = "▼ Hide concordance details";
    }
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
        const concordancesData = JSON.parse(this.response);
        if (Object.keys(concordancesData.databases).length === 0) {
            const noConcordances = document.createElement("p");
            noConcordances.innerHTML = `No concordances found for Cantus ID <b><a href="http://cantusindex.org/id/${cantusID}" target="_blank" title="${cantusID} on Cantus Index"> ${cantusID}</a></b>.`;
            concordancesDiv.appendChild(noConcordances);
            return;
        }
        // Create the concordances summary table
        const concordancesSummaryTable = document.createElement("table");
        concordancesSummaryTable.id = "concordancesSummaryTable";
        concordancesSummaryTable.setAttribute("class", "mx-3 table table-sm col-8 small border-bottom");
        const summaryTableHeader = concordancesSummaryTable.createTHead();
        const summaryHeaderRow = summaryTableHeader.insertRow();
        const summaryHeaderCell = summaryHeaderRow.insertCell();
        summaryHeaderCell.classList.add("border-top-0");
        summaryHeaderCell.innerHTML = "<b>Summary</b>";
        for (const [initialism, dbSummary] of Object.entries(concordancesData.databases)) {
            // object returned by json-con API is ordered by the number
            // of concordances in descending order
            const newRow = concordancesSummaryTable.insertRow();
            // The first cell of each row contains the database name
            // and initialism with a link to the database home page
            const dbNameCell = newRow.insertCell();
            const dbNameLink = document.createElement("a");
            dbNameLink.setAttribute("href", dbSummary.url);
            dbNameLink.setAttribute("target", "_blank");
            const dbNameLinkText = document.createTextNode(`${dbSummary.name} (${initialism})`);
            dbNameLink.appendChild(dbNameLinkText);
            dbNameCell.appendChild(dbNameLink);
            // The second cell of each row contains the number of concordances
            // linked to the results url on the database
            const concordanceCountCell = newRow.insertCell();
            const concordanceCountLink = document.createElement("a");
            concordanceCountLink.setAttribute("href", dbSummary.url_cid);
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
        const concordancesSummaryRow = document.createElement("div");
        concordancesSummaryRow.setAttribute("class", "row");
        concordancesSummaryRow.appendChild(concordancesSummaryTable);
        concordancesDiv.appendChild(concordancesSummaryRow);
        if (Object.keys(concordancesData.chants).length === 0) {
            return;
        }
        // Create table collapse link
        const collapseLink = document.createElement("a");
        collapseLink.classList.add("mx-3");
        collapseLink.setAttribute("id", "concordanceDetailCollapseLink");
        collapseLink.setAttribute("data-toggle", "collapse");
        collapseLink.setAttribute("href", "#concordancesDetailTable");
        collapseLink.setAttribute("role", "button");
        collapseLink.setAttribute("aria-expanded", "true");
        collapseLink.setAttribute("aria-controls", "concordancesDetailTable");
        collapseLink.innerHTML = "▼ Hide concordance details";
        collapseLink.addEventListener("click", concordanceDetailToggleText);
        // Create the concordances detail table
        const concordancesTable = document.createElement("table");
        concordancesTable.id = "concordancesDetailTable";
        concordancesTable.setAttribute("class", "mx-3 mt-3 table table-sm table-responsive table-bordered small collapse show");
        const headerArray = ["Source", "Incipit", "Office | Genre | Position", "Feast", "Mode", "Database"];
        const headerRow = concordancesTable.createTHead().insertRow();
        for (const header of headerArray) {
            const headerCell = headerRow.insertCell();
            headerCell.classList.add("text-center");
            headerCell.innerHTML = `<b>${header}</b>`;
        }
        var concordancesDetail = Object.values(concordancesData.chants);
        concordancesDetail.sort((a, b) => {
            return a.siglum.localeCompare(b.siglum);
        });
        for (const concordance of concordancesDetail) {
            const newRow = concordancesTable.insertRow();
            const sourceLink = document.createElement("a");
            sourceLink.setAttribute("href", concordance.srclink);
            sourceLink.setAttribute("target", "_blank");
            sourceLink.innerHTML = `${concordance.siglum}`;
            const folio = document.createElement("span");
            folio.innerHTML = `, <b>${concordance.folio}</b>`;
            // Some concordance image links are invalid urls (e.g. "0")
            // so we need to check both that the link is not empty and that it is
            // a valid url before creating the image link
            try {
                const url = new URL(concordance.image);
                var imageLink = document.createElement("a");
                imageLink.setAttribute("href", url.href);
                imageLink.setAttribute("target", "_blank");
                imageLink.classList.add("bi-camera-fill");
                newRow.insertCell().innerHTML = sourceLink.outerHTML + folio.outerHTML + "<br>" + imageLink.outerHTML;
            } catch (e) {
                newRow.insertCell().innerHTML = sourceLink.outerHTML + folio.outerHTML;
            }
            const chantLink = document.createElement("a");
            chantLink.setAttribute("href", concordance.chantlink);
            chantLink.setAttribute("target", "_blank");
            chantLink.innerHTML = concordance.incipit;
            newRow.insertCell().innerHTML = chantLink.outerHTML;
            newRow.insertCell().innerHTML = `${concordance.office} | ${concordance.genre} | ${concordance.position}`;
            newRow.insertCell().innerHTML = concordance.feast;
            newRow.insertCell().innerHTML = concordance.mode;
            newRow.insertCell().innerHTML = concordance.db;
        }
        const concordancesRow = document.createElement("div");
        concordancesRow.setAttribute("class", "row");
        concordancesRow.appendChild(collapseLink);
        concordancesRow.appendChild(concordancesTable);
        concordancesDiv.appendChild(concordancesRow);


    }
    xhttp.onerror = function () {
        concordancesLoadingStatus.innerHTML = "";
        const concordancesLoadError = document.createElement("p");
        concordancesLoadError.innerHTML = `Cantus Database encountered an error while loading concordances (Cantus ID <b><a href="http://cantusindex.org/id/${cantusID}" target="_blank" title="${cantusID} on Cantus Index"> ${cantusID} </a></b>).`;
        concordancesLoadingStatus.appendChild(concordancesLoadError);
    }
    xhttp.send();
}