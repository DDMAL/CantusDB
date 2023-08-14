window.addEventListener("load", function () {
    const copyTextButton = document.getElementById("copyFullTextBelow");
    if (copyTextButton) {
        copyTextButton.addEventListener("click", copyText);
    }
    function copyText() {
        const standardText = document.getElementById('id_manuscript_full_text_std_spelling').value;
        document.getElementById('id_manuscript_full_text').value = standardText;
    }
})