/*
 * Automatic split of Cantus Index text (#2165) — the rules, and nothing else.
 *
 * Cantus Index stores a troped chant's text as one blob with core and component
 * elements intermingled, and no single convention for marking the boundary. The
 * rules below were derived from 4,325 CI texts (369 of them trope genres), and
 * check against the only ground truth CI offers — the few chants whose elements it
 * catalogues separately as <parent>:NN. Conventions actually in use:
 *
 *   - CASE. An ALL-CAPS run is the base chant's own text, a lower-case run is the
 *     trope. Carried by 51% of trope texts; reproduces g04828's and ah47439's
 *     boundaries exactly. Only the boundary is taken from it — see below.
 *   - "|", in 42% of trope texts. A reliable BOUNDARY but not a type signal: it
 *     divides core from component in some texts, one repetition from the next in
 *     others, and in 204367.Tp3 three components with no core present at all.
 *   - ".." / "..." abbreviating a known core incipit — "GLORIA .. VOLUNTATIS"
 *     stands for the whole of "Gloria in excelsis ... bonae voluntatis". It GLUES:
 *     never a split point, and a positive signal that the run is core.
 *   - "*" truncating an incipit ("AGNUS * Qui sedes"). Glues to its LEFT only.
 *   - "(A)" / "(B)" / "(a)" / "(A1)" labelling a component insertion.
 *   - "(SOME UPPERCASE PHRASE)" doing the exact opposite — wrapping a core incipit.
 *   - "(...)" / "(..)" for omitted text and "[...]" for an editorial supplement,
 *     which can sit inside a word ("[ACCEND]E"). Neither is an element, and neither
 *     is ever a split point.
 *   - a bare leading number as a strophe marker.
 *
 * THE RULES FIND BOUNDARIES AND NOTHING ELSE. Every element they produce is a CORE
 * element, exactly like a hand-made split — including the trope text, which is core
 * text as far as this tool is concerned even though the conventions above often say
 * otherwise. That is deliberate: the feature only automates the splitting and deleting
 * a cataloguer would otherwise do by hand, so the data saved either way has to be
 * identical, and a hand split makes cores. Deciding which of the pieces is really a
 * trope stays with the cataloguer, who deletes what they don't want to keep.
 *
 * The one thing recorded beyond the cut is a "separator" display hint (data-auto-kind)
 * on the "|"-type markers, so "Remove separators" can find them again. It is a hint on
 * a core token and is never submitted: ChantElement.Kind has no separator.
 *
 * The rules deliberately UNDER-split. A boundary we are certain of is always cut — "|"
 * and the (A)-style labels are unambiguous however little else about the text is clear,
 * and a change of case is just as plain to read. Where there is no signal at all,
 * though, the text is left alone rather than divided on a guess: ah47196 ("Gloria ..
 * voluntatis | Rex immense ... | Laudamus te | ...") has its separators picked out with
 * each whole segment between them left as one element, which is as far as the evidence
 * goes. A chunk left too big is one more hand-split; a wrong boundary has to be noticed
 * first.
 *
 * These are pure functions over a string: no DOM, no page state. That is why they live apart
 * from chant_create_clusters.js, which loads just after this file and does everything the
 * composer does with the result — it lets tests/js/auto_split.test.js run them under Node with
 * no browser at all. Keep them free of anything but text.
 */
(function () {
    "use strict";

    const AUTO_LABEL_RE = /\((?:[A-Za-z]\d?|\d{1,2})\)/g; // (A) (B) (a) (A1) (2)
    const AUTO_STROPHE_RE = /^\s*(\d{1,2})\s+(?=[A-Za-z])/;
    // Omitted "(...)"/"(..)" and supplied "[...]" text. Masked before anything else, so
    // a "(..)" can't be read as a label and a "[...]" can't be split through.
    const AUTO_EDITORIAL_RE = /\([.…\s]*\)|\[[^\]]*\]/g;
    // One atomic core span: "X .. Y" (elision, glues both sides) or "X *" (truncation of
    // an incipit, glues left only — the trope follows it, as in "AGNUS * Qui sedes").
    const AUTO_GLUE_SPAN_RE = /\S+\s*(?:\.{2,}|…)\s*\S+|\S+\s*\*/g;
    // Masked editorial spans are delimited by U+0001, a character chant text never
    // contains, so the index inside can never be confused with a strophe number that
    // is genuinely part of the text.
    const AUTO_MASK_RE = /\u0001(\d+)\u0001/g;

    // The cased characters of a word. Anything whose upper and lower forms differ counts,
    // so the accented Latin in CI text works without hard-coding a character range.
    function autoLetters(word) {
        return Array.prototype.filter.call(String(word), function (c) {
            return c.toLowerCase() !== c.toUpperCase();
        });
    }

    function autoIsUpper(c) {
        return c === c.toUpperCase();
    }

    // Two letters minimum: a lone capital ("O deitas clemens") is not evidence of a core
    // run, and is placed by its neighbours instead.
    function autoIsCaps(word) {
        const letters = autoLetters(word);
        return letters.length >= 2 && letters.every(autoIsUpper);
    }

    // Title case counts as lower-ish. It is genuinely ambiguous — "Agnus ait Domini
    // ... NOLITE GAUDERE" is a Title-cased trope against an upper-case base text — so an
    // initial capital never opens an upper-case run.
    function autoIsLowerish(word) {
        const letters = autoLetters(word);
        return letters.length >= 2 && !letters.every(autoIsUpper);
    }

    // Collapse neighbouring runs of the same hint, so "Sanctus" + "dominus" reads as the
    // one core element it is rather than two boxes the cataloguer has to rejoin.
    function autoMerge(runs) {
        const merged = [];
        runs.forEach(function (run) {
            const last = merged[merged.length - 1];
            if (last && last.hint === run.hint) last.text += " " + run.text;
            else merged.push({ hint: run.hint, text: run.text });
        });
        merged.forEach(function (run) {
            run.text = run.text.replace(/\s+/g, " ").trim();
        });
        return merged;
    }

    // Pass 1: cut the text at the boundaries that are unambiguous, emitting each marker
    // as its own part. Operates on text whose editorial spans are already masked.
    function autoStructuralSplit(masked) {
        const parts = [];
        masked.split(/(\|\|?)/).forEach(function (chunk) {
            if (!chunk.trim()) return;
            if (/^\|\|?$/.test(chunk.trim())) {
                parts.push({ role: "sep", text: chunk.trim() });
                return;
            }
            let rest = chunk;
            const strophe = rest.match(AUTO_STROPHE_RE);
            if (strophe) {
                parts.push({ role: "sep", text: strophe[1] });
                rest = rest.slice(strophe[0].length);
            }
            let pos = 0;
            Array.from(rest.matchAll(AUTO_LABEL_RE)).forEach(function (match) {
                const before = rest.slice(pos, match.index).trim();
                if (before) parts.push({ role: "seg", text: before });
                parts.push({ role: "sep", text: match[0] });
                pos = match.index + match[0].length;
            });
            const tail = rest.slice(pos).trim();
            // The label is emitted as a separator above, so the boundary is kept — but the
            // text after it is NOT typed as a component on that basis. By the convention,
            // "(A) Pater lumen aeternum" is a labelled trope insertion, and it is tempting to
            // read it that way; unlike the case convention, though, the label rule was only
            // inferred from reading examples and never checked against a catalogued
            // <parent>:NN element. Typing on it would promote core text to component text on
            // unvalidated evidence, so the split stops at the boundary and leaves the type
            // alone.
            if (tail) parts.push({ role: "seg", text: tail });
        });
        return parts;
    }

    // A segment's classifiable units: ordinary words, plus elision spans kept atomic so
    // no split can land inside "GLORIA .. VOLUNTATIS".
    function autoUnits(segment) {
        const units = [];
        let pos = 0;
        function pushWords(text) {
            text.split(/\s+/).forEach(function (word) {
                if (word) units.push({ text: word, atomic: false });
            });
        }
        Array.from(segment.matchAll(AUTO_GLUE_SPAN_RE)).forEach(function (match) {
            pushWords(segment.slice(pos, match.index));
            units.push({ text: match[0].trim(), atomic: true });
            pos = match.index + match[0].length;
        });
        pushWords(segment.slice(pos));
        return units;
    }

    // Pass 2: cut a segment where its case changes. Returns null when the segment carries no
    // case signal at all, and the caller then leaves it whole.
    //
    // The case convention is the only rule checked against Cantus Index's own catalogued
    // <parent>:NN elements, so it is the only one trusted to divide the inside of a segment.
    // BOTH cases have to be present: without the contrast there is nothing to read. An
    // elision span counts here like any other unit, so "AGNUS .. MUNDI" supplies the
    // upper-case side by itself.
    //
    // Upper and lower are what the convention calls core and trope, but that reading is used
    // ONLY to place the cut — every run comes back core. See the header comment.
    function autoCaseRuns(segment) {
        const units = autoUnits(segment);
        const texts = units.map(function (unit) {
            return unit.text;
        });
        if (!texts.some(autoIsCaps) || !texts.some(autoIsLowerish)) return null;
        const cases = units.map(function (unit) {
            if (unit.atomic) return "upper"; // an elision abbreviates a known base incipit
            if (autoIsCaps(unit.text)) return "upper";
            if (autoIsLowerish(unit.text)) return "lower";
            return null; // a lone capital, or bare punctuation: placed below
        });
        // A one-letter word joins what FOLLOWS it: "O deitas clemens" opens the lower-case
        // run rather than closing the upper-case one before it. That single word is what
        // separated an earlier pass from g04828's ground truth.
        for (let i = cases.length - 1; i >= 0; i -= 1) {
            if (cases[i] === null) cases[i] = i + 1 < cases.length ? cases[i + 1] : null;
        }
        for (let i = 0; i < cases.length; i += 1) {
            if (cases[i] === null) cases[i] = i > 0 ? cases[i - 1] : "upper";
        }
        // Merge on the case, so a run of one case is one element; then drop the case, so what
        // comes out is a row of plain cores divided where the case changed.
        return autoMerge(
            units.map(function (unit, i) {
                return { hint: cases[i], text: unit.text };
            })
        ).map(function (run) {
            return { hint: "core", text: run.text };
        });
    }

    // Run both passes over one element's text. -> [{ hint, text }]
    function autoSplitText(text) {
        const holes = [];
        const masked = String(text).replace(AUTO_EDITORIAL_RE, function (match) {
            holes.push(match);
            return "\u0001" + (holes.length - 1) + "\u0001";
        });
        const parts = autoStructuralSplit(masked);
        const pieces = [];
        parts.forEach(function (part) {
            // Never empty: autoStructuralSplit drops a blank chunk and trims what it emits, which
            // is where that guarantee belongs and where the tests pin it.
            const partText = part.text.replace(/\s+/g, " ").trim();
            if (part.role === "sep" || autoLetters(partText).length === 0) {
                // A part with no letters left is an editorial mark such as "(..)", not an
                // element: treated as a separator so it can be dropped with the rest.
                pieces.push({ hint: "separator", text: partText });
                return;
            }
            const runs = autoCaseRuns(partText);
            // No readable case contrast: the segment stays one element rather than being
            // divided on a guess.
            if (!runs) {
                pieces.push({ hint: "core", text: partText });
                return;
            }
            runs.forEach(function (run) {
                pieces.push(run);
            });
        });
        return pieces.map(function (part) {
            return {
                hint: part.hint,
                text: part.text
                    .replace(AUTO_MASK_RE, function (match, index) {
                        return holes[Number(index)];
                    })
                    .replace(/\s+/g, " ")
                    .trim(),
            };
        });
    }

    // The one function the composer needs, plus the internals the tests pin each convention
    // with. Nothing in the page reads `internals`.
    window.ChantAutoSplit = {
        splitText: autoSplitText,
        internals: {
            letters: autoLetters,
            isCaps: autoIsCaps,
            isLowerish: autoIsLowerish,
            mergeRuns: autoMerge,
            structuralSplit: autoStructuralSplit,
            units: autoUnits,
            caseRuns: autoCaseRuns,
        },
    };
})();
