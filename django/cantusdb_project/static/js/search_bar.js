window.addEventListener("load", globalSearch);
function globalSearch() {
    // the global search bar at the top-right corner of almost every page
    const searchBar = document.getElementById("searchBar")
    // the area for displaying the suggested results
    const chantsDiv = document.getElementById("chantsDiv");
    // search upon input 
    searchBar.addEventListener("input", loadChants);
    // lastXhttp is a pointer to the last ajax request
    // if the user clicks on the canvas or deletes notes very fast, the older requests 
    // may not finish before the newer ones, causing the result table being updated multiple times, 
    // potentially with wrong results from the older requests
    // therefore we keep a pointer to the last request and abort it whenever sending a new request
    var lastXhttp = new XMLHttpRequest();

    function loadChants() {
        // whenever a new search begins, abort the previous one, so that it does not update the result table with wrong data
        lastXhttp.abort()
        const searchTerm = searchBar.value;
        // if the search bar is empty, clear the target area and don't proceed to search
        if (searchTerm == "") {
            chantsDiv.innerHTML = "";
            return;
        }

        const xhttp = new XMLHttpRequest();
        // construct the ajax url with the search term
        const url = new URL(`ajax/search-bar/${searchTerm}`, window.location.origin);

        xhttp.open("GET", url);
        xhttp.onload = function () {
            const data = JSON.parse(this.response);
            // the results are to be displayed in a list-group
            chantsDiv.innerHTML = `<div class="list-group" id="listBox" style="position:absolute; z-index:1"></div>`;
            const listBox = document.getElementById("listBox");
            // for every chant returned in the JSONResponse
            data.chants.map(chant => {
                // if a field is null, change it to empty str
                const incipit = chant.incipit ?? "";
                const genre = chant.genre__name ?? "";
                const feast = chant.feast__name ?? "";
                const cantus_id = chant.cantus_id ?? "";
                const mode = chant.mode ?? "";
                const siglum = chant.source__siglum ?? "";
                const folio = chant.folio ?? "";
                const sequence = chant.c_sequence ?? "";
                // add an entry to the list-group
                listBox.innerHTML += `<a href=${chant.chant_link} class="list-group-item list-group-item-action flex-column align-items-start" target="_blank">
                                        <div class="w-100 justify-content-between">
                                            <h5>${incipit}</h5>
                                            <small>
                                                <p align="right">
                                                    ${genre} | ${feast} | ${cantus_id} | Mode: ${mode}
                                                    <br>
                                                    ${siglum} | ${folio} | ${sequence}
                                                </p>
                                            </small>
                                        </div>
                                    </a>`;
            });
        }

        xhttp.onerror = function () {
            // handle errors
            chantsDiv.innerHTML = "ajax error";
        }

        xhttp.send();
        // update the pointer to the last xhttp request
        lastXhttp = xhttp;
        // display the "loading results" prompt after sending the ajax request
        // loadingPrompt.style.display = "inline";
        // hide the "load concordances" button after sending the ajax request
        // concordanceButton.style.display = "none";
    }
}