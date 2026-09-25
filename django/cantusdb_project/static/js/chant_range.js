// A chant carries either volpiano or a hand-entered range, never both: the
// range is derived from the melody on save (see BaseChant.save). The form
// rejects a submission that supplies both, but waiting for a validation error to
// say so is a poor way to learn the rule - so grey the range input out as soon
// as the melody box has content. See #2081 / #1176.
window.addEventListener("load", function () {
    const volpiano = document.getElementById("id_volpiano");
    const chantRange = document.getElementById("id_chant_range");
    if (!volpiano || !chantRange) {
        return;
    }
    const note = document.getElementById("chantRangeDerivedNote");

    function syncChantRange() {
        const hasVolpiano = volpiano.value.trim() !== "";
        // Only the input's disabled state changes; its value is left intact so
        // that clearing the volpiano again restores whatever was typed.
        chantRange.disabled = hasVolpiano;
        if (note) {
            note.hidden = !hasVolpiano;
        }
    }

    volpiano.addEventListener("input", syncChantRange);
    syncChantRange();
});
