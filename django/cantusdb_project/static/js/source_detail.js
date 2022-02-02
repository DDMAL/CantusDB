// on selecting an option in the folio selector or feast selector, 
// jump to the browse chants page with pre-filled source and folio/feast info
function jumpToFolio(sourceId) {
    const folioSelect = document.getElementById("folioSelect");
    const url = new URL("chants/", window.location.origin);
    const folio = folioSelect.options[folioSelect.selectedIndex].value;
    url.searchParams.set("source", sourceId);
    url.searchParams.set("folio", folio);
    window.location.assign(url);
}

function jumpToFeast(sourceId) {
    const feastSelect = document.getElementById("feastSelect");
    const url = new URL("chants/", window.location.origin);
    const feast = feastSelect.options[feastSelect.selectedIndex].value;
    url.searchParams.set("source", sourceId);
    url.searchParams.set("feast", feast);
    window.location.assign(url);
}