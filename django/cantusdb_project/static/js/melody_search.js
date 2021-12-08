window.onload = melodySearch;
function melodySearch() {
    var index = 1;
    const drawArea = document.getElementById("drawArea");
    const deleteOne = document.getElementById("deleteOne");
    const deleteAll = document.getElementById("deleteAll");
    deleteOne.addEventListener("click", deleteOneNote);
    deleteAll.addEventListener("click", deleteAllNotes);
    drawArea.addEventListener("mousemove", () => { trackMouse(index); });
    drawArea.addEventListener("click", changePic);

    function changePic() {
        drawArea.removeEventListener("mousemove", () => { trackMouse(index); })
        if (index <= 14) {
            index = index + 1;
            drawArea.addEventListener("mousemove", () => { trackMouse(index); });
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

    function deleteOneNote() {
        document.getElementById(index - 1).src = "/static/melody search tool/-.jpg";
        index = index - 1;
    }

    function deleteAllNotes() {
        for (let i = 1; i < index; i++) {
            document.getElementById(i).src = "/static/melody search tool/-.jpg";
        }
        index = 1;
    }

    function showCoords() {
        var x = event.pageX;
        var y = event.pageY;
        var coords = "X coords: " + x + ", Y coords: " + y;
        console.log(coords);
    }
}
