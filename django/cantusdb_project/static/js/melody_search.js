window.onload = melodySearch;
function melodySearch() {
    // `index` is the index of the currently active note slot, it starts from one
    var index = 1;
    // `notes` is a string consisting of all notes put on the canvas
    // it should be updated with every call to `trackClick` or `deleteNotes`
    var notes = "";
    const drawArea = document.getElementById("drawArea");
    const deleteOne = document.getElementById("deleteOne");
    const deleteAll = document.getElementById("deleteAll");
    deleteOne.addEventListener("click", deleteOneNote);
    deleteAll.addEventListener("click", deleteAllNotes);
    drawArea.addEventListener("mousemove", () => { trackMouse(index); });
    drawArea.addEventListener("click", trackClick);

    function trackClick() {
        const y = event.pageY;
        // if click on the area without any notes, do nothing
        if (y < 256 || y >= 382) {
            return;
        }
        // otherwise, stop changing notes on the current slot
        drawArea.removeEventListener("mousemove", () => { trackMouse(index); })
        // add the note to the search term, according to the y position of the click
        if (index <= 14) {
            if (y < 264) {
                notes += "q";
            } else if (y < 272) {
                notes += "p";
            } else if (y < 279) {
                notes += "o";
            } else if (y < 287) {
                notes += "n";
            } else if (y < 294) {
                notes += "m";
            } else if (y < 302) {
                notes += "l";
            } else if (y < 309) {
                notes += "k";
            } else if (y < 317) {
                notes += "j";
            } else if (y < 324) {
                notes += "h";
            } else if (y < 332) {
                notes += "g";
            } else if (y < 339) {
                notes += "f";
            } else if (y < 347) {
                notes += "e";
            } else if (y < 354) {
                notes += "d";
            } else if (y < 362) {
                notes += "c";
            } else if (y < 369) {
                notes += "b";
            } else if (y < 377) {
                notes += "a";
            } else if (y < 382) {
                notes += "9";
            }
            // move on to the next slot
            index = index + 1;
            drawArea.addEventListener("mousemove", () => { trackMouse(index); });
            // here we should do the search
            search()
            console.log(notes)
        }
    }

    function trackMouse(noteIndex) {
        // console.log(event.type);
        // get the y coordinate of the mouse position, x doesn't matter
        // x = event.pageX;
        y = event.pageY;
        // console.log("X coords: " + x + ", Y coords: " + y);
        // compare it with the y coordinate of every staff line (hardcoded), 17 positions in total
        // staff line coordinates: [264, 279, 294, 309, 324, 339, 354, 369]
        if (document.getElementById(noteIndex)) {
            const currentPic = document.getElementById(noteIndex);
            // change the current image to the corresp. note image based on the y position
            if (y < 256) {
                currentPic.src = "/static/melody search tool/-.jpg";
            } else if (y < 264) {
                currentPic.src = "/static/melody search tool/b2.jpg";
            } else if (y < 272) {
                currentPic.src = "/static/melody search tool/a2.jpg";
            } else if (y < 279) {
                currentPic.src = "/static/melody search tool/g1.jpg";
            } else if (y < 287) {
                currentPic.src = "/static/melody search tool/f1.jpg";
            } else if (y < 294) {
                currentPic.src = "/static/melody search tool/e1.jpg";
            } else if (y < 302) {
                currentPic.src = "/static/melody search tool/d1.jpg";
            } else if (y < 309) {
                currentPic.src = "/static/melody search tool/c1.jpg";
            } else if (y < 317) {
                currentPic.src = "/static/melody search tool/b1.jpg";
            } else if (y < 324) {
                currentPic.src = "/static/melody search tool/a1.jpg";
            } else if (y < 332) {
                currentPic.src = "/static/melody search tool/g.jpg";
            } else if (y < 339) {
                currentPic.src = "/static/melody search tool/f.jpg";
            } else if (y < 347) {
                currentPic.src = "/static/melody search tool/e.jpg";
            } else if (y < 354) {
                currentPic.src = "/static/melody search tool/d.jpg";
            } else if (y < 362) {
                currentPic.src = "/static/melody search tool/c.jpg";
            } else if (y < 369) {
                currentPic.src = "/static/melody search tool/b.jpg";
            } else if (y < 377) {
                currentPic.src = "/static/melody search tool/a.jpg";
            } else if (y < 382) {
                currentPic.src = "/static/melody search tool/9.jpg";
            } else {
                currentPic.src = "/static/melody search tool/-.jpg";
            }
        }
    }

    // make an ajax call to the Django backend: do the search and return results
    function search() {
        const resultsDiv = document.getElementById("resultsDiv");
        const xhttp = new XMLHttpRequest();
        const url = "/ajax/melody-search/" + notes;
        console.log(url);
        xhttp.open("GET", url);
        xhttp.onload = function () {
            const data = JSON.parse(this.response)
            resultsDiv.innerHTML = `Search results <b>(${data.result_count} melodies)</b>`;
            resultsDiv.innerHTML += `<table id="resultsTable" class="table table-responsive table-sm small"><tbody></tbody></table>`;
            const table = document.getElementById("resultsTable").getElementsByTagName("tbody")[0];
            data.results.map(chant => {
                const newRow = table.insertRow(table.rows.length);
                newRow.innerHTML += `<td style="width:30%">
                                            <b>${chant.siglum}</b>
                                            <br>
                                            fol. <b>${chant.folio}</b>
                                            <br>
                                            <b>${chant.genre__name}</b> | Mode: <b>${chant.mode}</b>
                                    </td>`;
                newRow.innerHTML += `<td style="width:70%">
                                            <a href="${chant.chant_link}" target="_blank"><b>${chant.incipit}</b></a>
                                            <br>
                                            <div style="font-family: volpiano; font-size: 20px;">${chant.volpiano}</div>
                                            <br>
                                            ${chant.feast__name}
                                    </td>`
            });
        }
        xhttp.onerror = function () {
            // handle errors
            document.getElementById("resultsDiv").innerHTML = "ajax error"
        }
        xhttp.send();
    }

    function deleteOneNote() {
        document.getElementById(index - 1).src = "/static/melody search tool/-.jpg";
        // set the focused slot back one unit
        index = index - 1;
        // remove the last character from the search term
        notes = notes.slice(0, -1);
    }

    function deleteAllNotes() {
        for (let i = 1; i < index; i++) {
            document.getElementById(i).src = "/static/melody search tool/-.jpg";
        }
        // set the focused slot to the beginning
        index = 1;
        // set the search term to empty
        notes = "";
    }

    function showCoords() {
        var x = event.pageX;
        var y = event.pageY;
        var coords = "X coords: " + x + ", Y coords: " + y;
        console.log(coords);
    }
}
