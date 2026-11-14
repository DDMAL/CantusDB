// Match generate_chant_range in main_app/chant_range.py: a range needs at
// least one recognized pitch and no clef change. Other melodies allow manual
// range entry, just like an empty melody. See #2081 / #1176.
window.addEventListener("load", function () {
    const volpiano = document.getElementById("id_volpiano");
    const chantRange = document.getElementById("id_chant_range");
    if (!volpiano || !chantRange) {
        return;
    }
    const note = document.getElementById("chantRangeDerivedNote");

    function syncChantRange() {
        const melody = volpiano.value.toLowerCase().replaceAll(")", "9");
        const canDerive = /[9a-hj-s]/.test(melody)
            && !(melody.includes("1") && melody.includes("2"));
        // Only the input's disabled state changes; its value is left intact so
        // that clearing the volpiano again restores whatever was typed.
        chantRange.disabled = canDerive;
        if (note) {
            note.hidden = !canDerive;
        }
    }

    volpiano.addEventListener("input", syncChantRange);
    syncChantRange();
});
