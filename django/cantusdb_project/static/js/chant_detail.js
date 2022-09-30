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

function loadConcordances(cantusId) {
    const concordanceDiv = document.getElementById('concordanceDiv');
    const loadingPrompt = document.getElementById("concordanceLoadingPrompt");
    const concordanceButton = document.getElementById("concordanceButton");

    const xhttp = new XMLHttpRequest();
    // construct the ajax url with the cantus id parameter
    const url = new URL(`ajax/concordance/${cantusId}`, window.location.origin);

    xhttp.open("GET", url);
    xhttp.onload = function () {
        const data = JSON.parse(this.response);
        concordanceDiv.innerHTML = `Displaying <b>${data.concordance_count}</b> concordances from the following databases (Cantus ID <b><a href="http://cantusindex.org/id/${cantusId}" target="_blank">${cantusId}</a></b>)`;
        concordanceDiv.innerHTML += `<table id="concordanceTable" class="table table-bordered table-sm small" style="table-layout: fixed; width: 100%;">
                                    <thead>
                                        <tr>
                                            <th scope="col" class="text-wrap" style="width:15%">Siglum</th>
                                            <th scope="col" class="text-wrap" style="width:5%">Folio</th>
                                            <th scope="col" class="text-wrap" style="width:20%">Incipit</th>
                                            <th scope="col" class="text-wrap" style="width:5%"></th>
                                            <th scope="col" class="text-wrap" style="width:5%"></th>
                                            <th scope="col" class="text-wrap" style="width:5%"></th>
                                            <th scope="col" class="text-wrap" style="width:20%">Feast</th>
                                            <th scope="col" class="text-wrap" style="width:10%">Mode</th>
                                            <th scope="col" class="text-wrap" style="width:10%">Image</th>
                                            <th scope="col" class="text-wrap" style="width:5%">DB</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                    </tbody>
                                </table>`;
        const table = document.getElementById("concordanceTable").getElementsByTagName("tbody")[0];

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
            if (chant.folio) { newRow.innerHTML += `<td class="text-wrap">${chant.folio}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.incipit) { newRow.innerHTML += `<td class="text-wrap"><a href="${chant.chant_link}" target="_blank">${chant.incipit}</a></td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.office__name) { newRow.innerHTML += `<td class="text-wrap">${chant.office__name}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.genre__name) { newRow.innerHTML += `<td class="text-wrap">${chant.genre__name}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.position) { newRow.innerHTML += `<td class="text-wrap">${chant.position}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.feast__name) { newRow.innerHTML += `<td class="text-wrap">${chant.feast__name}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.mode) { newRow.innerHTML += `<td class="text-wrap">${chant.mode}</td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            if (chant.image_link) { newRow.innerHTML += `<td class="text-wrap"><a href="${chant.image_link}" target="_blank">Image</a></td>` } else { newRow.innerHTML += '<td class="text-wrap"></td>' }
            newRow.innerHTML += `<td class="text-wrap">${chant.db}</td>`
        });
        concordanceDiv.innerHTML += `<a href='//cantusindex.org/ci/${cantusId}?c=1&refresh=1' target='_blank'>Refresh results</a>`;
        // hide the "loading results" prompt after loading the data
        loadingPrompt.style.display = "none";
    }

    xhttp.onerror = function () {
        // handle errors
        concordanceDiv.innerHTML = "ajax error";
    }

    xhttp.send();
    // display the "loading results" prompt after sending the ajax request
    loadingPrompt.style.display = "inline";
    // hide the "load concordances" button after sending the ajax request
    concordanceButton.style.display = "none";
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
            if (chant.office__name) { chantCell.innerHTML += `${chant.office__name} ` } else { chantCell.innerHTML += '' }
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

