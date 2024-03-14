window.addEventListener("load", function () {
    const searchText = document.getElementById("search");
    const sourceFilter = document.getElementById("sourceFilter");
    const feastFilter = document.getElementById("feastFilter");
    const feastSelect = document.getElementById("feastSelect");
    const genreFilter = document.getElementById("genreFilter");
    const folioFilter = document.getElementById("folioFilter");

    // Make sure the select components keep their values across multiple GET requests
    // so the user can "drill down" on what they want
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("source")) {
        sourceFilter.value = urlParams.get("source");
    }
    if (urlParams.has("feast")) {
        feastFilter.value = urlParams.get("feast");
        feastSelect.value = urlParams.get("feast");
    }
    if (urlParams.has("genre")) {
        genreFilter.value = urlParams.get("genre");
    }
    if (urlParams.has("folio")) {
        folioFilter.value = urlParams.get("folio");
    }

    searchText.addEventListener("change", setSearch);
    sourceFilter.addEventListener("change", setSource);
    feastFilter.addEventListener("change", setFeastLeft);
    feastSelect.addEventListener("change", setFeastRight);
    genreFilter.addEventListener("change", setGenre);
    folioFilter.addEventListener("change", setFolio);

    // functions for the auto-jump of various selectors and input fields on the page
    // the folio selector and folio-feast selector on the right half do source-wide filtering
    // the feast selector, genre selector, and text search on the left half do folio-wide filtering
    var url = new URL(window.location.href);

    function setSearch() {
        const searchTerm = searchText.value;
        url.searchParams.set('search_text', searchTerm);
        window.location.assign(url);
    }

    // if the source is reset, redirect to source/<int:source_id>/chants/
    function setSource() {
        const source = sourceFilter.options[sourceFilter.selectedIndex].value;
        url.pathname = "/source/" + source + "/chants/";
        url.searchParams.delete('source');
        url.searchParams.delete('feast');
        url.searchParams.delete('search_text');
        url.searchParams.delete('genre');
        url.searchParams.delete('folio');
        window.location.assign(url);
    }

    // if the feast on the right is reset, reset every selector but keep the source unchanged
    function setFeastRight() {
        url.searchParams.set('folio', '');
        url.searchParams.set('search_text', '');
        url.searchParams.set('genre', '');
        const feast = feastSelect.options[feastSelect.selectedIndex].value;
        url.searchParams.set('feast', feast);
        window.location.assign(url);
    }

    // if the feast on the left is reset, keep everything else unchanged
    function setFeastLeft() {
        const feast = feastFilter.options[feastFilter.selectedIndex].value;
        url.searchParams.set('feast', feast);
        window.location.assign(url);
    }

    // if the genre is reset, keep everything else unchanged
    function setGenre() {
        const genre = genreFilter.options[genreFilter.selectedIndex].value;
        url.searchParams.set('genre', genre);
        window.location.assign(url);
    }

    // if the folio is reset, reset every selector but keep the source unchanged
    function setFolio() {
        url.searchParams.set('feast', '');
        url.searchParams.set('search_text', '');
        url.searchParams.set('genre', '');
        const folio = folioFilter.options[folioFilter.selectedIndex].value;
        url.searchParams.set('folio', folio);
        window.location.assign(url);
    }
});
