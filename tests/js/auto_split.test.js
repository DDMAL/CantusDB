/*
 * Tests for the automatic split of Cantus Index text (#2165).
 *
 * The rules under test live in
 * django/cantusdb_project/static/js/chant_create_auto_split.js and are pure functions over a
 * string, so they run here under Node with no browser and no DOM — Node's own test runner, with
 * no dependencies to install. See tests/js/README.md for the command.
 *
 * What these tests are for. The rules were derived from reading 4,325 Cantus Index texts, and
 * only three of Cantus Index's 355 trope parents catalogue their elements separately — so for
 * almost every chant there is nothing to check a split against but the conventions themselves.
 * Each test below therefore names the convention it pins, and the two ground-truth cases
 * (g04828, ah47439) assert their exact expected output, because those two are the only places
 * where Cantus Index tells us what the right answer is.
 *
 * Every test also guards one promise the whole feature rests on: the split does by machine
 * exactly what a cataloguer would have done by hand, so it must never lose text, never invent
 * text, and never produce anything but core elements and separators.
 */

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const RULES_PATH = path.join(
    __dirname,
    "..",
    "..",
    "django",
    "cantusdb_project",
    "static",
    "js",
    "chant_create_auto_split.js"
);
const FIXTURE_PATH = path.join(__dirname, "fixtures", "cantus_index_texts.json");

// The rules file is a browser script whose only contract with the page is the object it hangs
// on `window`. Evaluating the whole file against a stub window is exactly how the browser
// loads it, so the tests exercise the shipped file rather than a copy of it.
function loadRules() {
    const source = fs.readFileSync(RULES_PATH, "utf8");
    const window = {};
    new Function("window", source)(window);
    return window.ChantAutoSplit;
}

const { splitText, internals } = loadRules();
const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8")).texts;

function byId(cid) {
    const row = fixture.find((r) => r.cid === cid);
    assert.ok(row, `fixture is missing ${cid}`);
    return row.fulltext;
}

// Shorthand for the shape assertions: "SANCTUS | dominus" -> ["SANCTUS", "|", "dominus"].
const textsOf = (parts) => parts.map((p) => p.text);
const hintsOf = (parts) => parts.map((p) => p.hint);
const split = (text) => splitText(text);

// The rules mask editorial spans with U+0001 while they work — a character chant text never
// contains — and nothing masked may survive into a finished element.
const MASK_DELIMITER = "\u0001";

// Every synthetic string used anywhere below, so the invariants at the end run over the made-up
// cases as well as the real ones. Add to this when you add a case.
const SYNTHETIC = [
    "SANCTUS dominus deus",
    "sanctus DOMINUS DEUS",
    "SANCTUS DEUS PATER",
    "sanctus dominus pater",
    "AGNUS Domini miserere",
    "SANCTUS O deitas clemens",
    "O deitas clemens",
    "SANCTUS DEUS pater noster",
    "GLÓRIA IN EXCÉLSIS deo gratias",
    "SANCTUS a b c dominus",
    "GLORIA .. VOLUNTATIS",
    "AGNUS .. MUNDI qui tollis",
    "GLORIA .. voluntatis Rex immense",
    "GLORIA ... voluntatis Rex",
    "GLORIA … voluntatis Rex",
    "AGNUS * Qui sedes",
    "AGNUS DEI * qui tollis peccata",
    "SANCTUS | dominus",
    "SANCTUS || dominus",
    "| SANCTUS",
    "SANCTUS |",
    "a | | b",
    "SANCTUS dominus | DEUS pater",
    "Sanctus (A) Pater lumen (B) Genitus ex deo",
    "Sanctus (a) Pater (b) Genitus",
    "Sanctus (A1) Pater",
    "Sanctus (2) Pater",
    "Sanctus | (A) Pater lumen",
    "(MISIT DOMINUS ANGELUM SUUM) | Est quia cunctorum",
    "GLORIA (...) VOLUNTATIS",
    "GLORIA (..) VOLUNTATIS",
    "[ACCEND]E lumen sensibus",
    "SANCTUS [ACCEND]E dominus",
    "[2] Sanctus deus omnipotens",
    "VENI CREATOR [SPIRITUS] mentes tuorum",
    "(...)",
    "(A)",
    "2 Caelicolas mundo Laudamus te",
    "2 Caelicolas mundo | 4 Aula cui supera",
    "1234 Sanctus deus",
    "Sanctus 2 deus",
    "SANCTUS   \n\t dominus  deus  ",
    "  SANCTUS dominus  ",
    "|",
    "Sanctus",
];

describe("the rules file's contract with the page", () => {
    it("exposes splitText on window and nothing the page has to configure", () => {
        assert.equal(typeof splitText, "function");
        assert.equal(typeof internals, "object");
    });

    it("returns { hint, text } pieces, which is all the composer reads", () => {
        const parts = split("SANCTUS | dominus");
        for (const part of parts) {
            assert.deepEqual(Object.keys(part).sort(), ["hint", "text"]);
            assert.equal(typeof part.text, "string");
        }
    });
});

// ---------------------------------------------------------------------------------------------
// Ground truth. Cantus Index catalogues these two chants' elements separately as <parent>:NN,
// so unlike every other case below, the expected output here is not our reading of a convention
// — it is what Cantus Index itself says the elements are. If either of these fails, the rules
// have regressed against the only external check that exists.
// ---------------------------------------------------------------------------------------------

describe("ground truth: chants whose elements Cantus Index catalogues separately", () => {
    it("reproduces g04828 (case convention, no separators) as 9 elements", () => {
        assert.deepEqual(textsOf(split(byId("g04828"))), [
            "SANCTUS",
            "Perpetuo numine cuncta regens",
            "SANCTUS",
            "Regna patris disponens jure parili",
            "SANCTUS",
            "Consimilis qui bona cuncta nutris",
            "DOMINUS DEUS SABAOTH PLENI SUNT CAELI ET TERRA GLORIA TUA HOSANNA IN EXCELSIS",
            "O deitas clemens servorum suscipe laudes",
            "BENEDICTUS QUI VENIT IN NOMINE DOMINI HOSANNA IN EXCELSIS",
        ]);
    });

    it("makes every g04828 element core — the trope text included", () => {
        // The case convention does say which of these is the base chant and which is the trope,
        // and the tool deliberately throws that reading away: it only automates the cataloguer's
        // own splitting, and a hand split makes cores. Deleting the trope is their decision.
        assert.deepEqual(new Set(hintsOf(split(byId("g04828")))), new Set(["core"]));
    });

    it("reproduces g01349.tp14 (a troped proper chant) as 8 elements", () => {
        // The first *proper* chant — an Introit — we have ground truth for; the other two are
        // troped ordinary chants, which is a distinction that matters to musicologists more
        // than to the rules. Cantus Index catalogues four elements here, g01349.tp14:01…:04,
        // and they are the four lower-case pieces below, reproduced word for word.
        assert.deepEqual(textsOf(split(byId("g01349.tp14"))), [
            "Hac in laude patris cuncti dicamus ovanter",
            "OS JUSTI",
            "Qui nosmet hodie facit esse de se jucundos",
            "ET LINGUA",
            "Qui nobis hodie semet concessit habere",
            "LOQUETUR",
            "Unde dies sit hic toto venerabilis orbe",
            "LEX DEI",
        ]);
    });

    it("cannot recover g01349.tp14's base chant, because its text is not in there", () => {
        // The four capitalised pieces above are cues, not the base chant: g01349 reads "Os justi
        // meditabitur sapientiam et lingua ejus loquetur judicium lex dei ejus in corde ipsius",
        // and *meditabitur sapientiam*, *ejus*, *judicium* and *ejus in corde ipsius* appear
        // nowhere in the troped record. No split can put back words that were never there —
        // which is why the composer seeds from the base chant instead (#2189), and why this
        // test asserts a limit of the rules rather than a capability of them.
        const split_ = textsOf(split(byId("g01349.tp14"))).join(" ");
        for (const missing of ["meditabitur", "judicium", "in corde ipsius"]) {
            assert.ok(
                byId("g01349").includes(missing),
                `the base chant should contain ${missing}`
            );
            assert.ok(
                !split_.includes(missing),
                `${missing} is not in the troped record, so no split may produce it`
            );
        }
    });

    it("finds nothing to split in the base chant the composer seeds from (g01349)", () => {
        // Seeded from the base, the composer opens on clean text with no boundary in it, so
        // "Split automatically" greys itself out and the cataloguer divides it where the
        // components go instead. Nothing to do is the correct answer here, not a failure.
        assert.equal(split(byId("g01349")).length, 1);
    });

    it("reproduces ah47439 (case convention plus | separators) as 11 elements", () => {
        assert.deepEqual(textsOf(split(byId("ah47439"))), [
            "AGNUS DEI QUI TOLLIS PECCATA MUNDI",
            "Rex aeternae gloriae qui das locum veniae miserere miserere",
            "MISERERE NOBIS",
            "|",
            "AGNUS DEI QUI TOLLIS PECCATA MUNDI",
            "Qui natus de virgine sub humana specie miserere miserere",
            "MISERERE NOBIS",
            "|",
            "AGNUS DEI QUI TOLLIS PECCATA MUNDI",
            "Pater potentissime pacem nobis tribue dona nobis dona nobis",
            "DONA NOBIS PACEM",
        ]);
        assert.deepEqual(
            hintsOf(split(byId("ah47439"))).filter((h) => h === "separator"),
            ["separator", "separator"]
        );
    });
});

// ---------------------------------------------------------------------------------------------
// CASE: an ALL-CAPS run is the base chant's own text, a lower-case run is the trope. Carried by
// 51% of trope texts, and the only convention validated against ground truth — so the only one
// allowed to divide the inside of a segment. It is used as a boundary signal only.
// ---------------------------------------------------------------------------------------------

describe("the case convention", () => {
    it("cuts where upper case gives way to lower", () => {
        assert.deepEqual(textsOf(split("SANCTUS dominus deus")), ["SANCTUS", "dominus deus"]);
    });

    it("cuts where lower case gives way to upper", () => {
        assert.deepEqual(textsOf(split("sanctus DOMINUS DEUS")), ["sanctus", "DOMINUS DEUS"]);
    });

    it("cuts both ways in one segment", () => {
        assert.deepEqual(textsOf(split("SANCTUS DEUS pater noster")), [
            "SANCTUS DEUS",
            "pater noster",
        ]);
    });

    it("leaves an all-upper-case segment whole — there is no contrast to read", () => {
        assert.deepEqual(textsOf(split("SANCTUS DEUS PATER")), ["SANCTUS DEUS PATER"]);
    });

    it("leaves an all-lower-case segment whole for the same reason", () => {
        assert.deepEqual(textsOf(split("sanctus dominus pater")), ["sanctus dominus pater"]);
    });

    it("treats Title Case as lower-ish, because a trope can be title-cased", () => {
        // "Agnus ait Domini ... NOLITE GAUDERE" is a Title-cased trope against an upper-case
        // base text, so an initial capital must never open an upper-case run.
        assert.deepEqual(textsOf(split("AGNUS Domini miserere")), ["AGNUS", "Domini miserere"]);
    });

    it("joins a one-letter word to what FOLLOWS it", () => {
        // This single word is what separated an earlier version of the rules from g04828's
        // ground truth: "O deitas clemens" opens the trope, it does not close the base text.
        assert.deepEqual(textsOf(split("SANCTUS O deitas clemens")), [
            "SANCTUS",
            "O deitas clemens",
        ]);
        assert.deepEqual(textsOf(split("SANCTUS a b c dominus")), ["SANCTUS", "a b c dominus"]);
    });

    it("does not read a lone capital as upper-case evidence on its own", () => {
        // A segment holding nothing but "O" plus lower case would otherwise look like a
        // base-text/trope contrast and be split on nothing at all.
        assert.deepEqual(textsOf(split("O deitas clemens")), ["O deitas clemens"]);
    });

    it("reads accented Latin capitals as capitals", () => {
        // Case is decided by whether a character's upper and lower forms differ, not by a
        // hard-coded A-Z range, so the accents Cantus Index uses work without a character list.
        assert.deepEqual(textsOf(split("GLÓRIA IN EXCÉLSIS deo gratias")), [
            "GLÓRIA IN EXCÉLSIS",
            "deo gratias",
        ]);
    });

    it("collapses neighbouring words of like case into one element, not one per word", () => {
        const parts = split(byId("g04828"));
        assert.equal(parts.length, 9); // not 40-odd words
    });
});

// ---------------------------------------------------------------------------------------------
// "|" — in 42% of trope texts. A reliable BOUNDARY but useless as a type signal: it divides base
// text from trope in some chants, one repetition from the next in others, and in 204367.Tp3
// three tropes with no base text present at all.
// ---------------------------------------------------------------------------------------------

describe("| separators", () => {
    it("makes a single pipe its own piece, hinted separator", () => {
        const parts = split("SANCTUS | dominus");
        assert.deepEqual(textsOf(parts), ["SANCTUS", "|", "dominus"]);
        assert.deepEqual(hintsOf(parts), ["core", "separator", "core"]);
    });

    it("keeps a double pipe together as one separator", () => {
        assert.deepEqual(textsOf(split("SANCTUS || dominus")), ["SANCTUS", "||", "dominus"]);
    });

    it("cuts at a pipe even when the case convention also applies", () => {
        assert.deepEqual(textsOf(split("SANCTUS dominus | DEUS pater")), [
            "SANCTUS",
            "dominus",
            "|",
            "DEUS",
            "pater",
        ]);
    });

    it("handles a leading, trailing or doubled-up pipe without inventing empty elements", () => {
        assert.deepEqual(textsOf(split("| SANCTUS")), ["|", "SANCTUS"]);
        assert.deepEqual(textsOf(split("SANCTUS |")), ["SANCTUS", "|"]);
        assert.deepEqual(textsOf(split("a | | b")), ["a", "|", "|", "b"]);
    });

    it("leaves each segment whole when the pipes are the only signal (ah47196)", () => {
        // The Gloria's own words and the trope's are indistinguishable here, so the rules take
        // the boundaries they are sure of and stop. A chunk left too big is one more hand-split;
        // a wrong boundary has to be noticed first.
        const parts = split(byId("ah47196"));
        assert.equal(parts.length, 43);
        assert.equal(parts.filter((p) => p.hint === "separator").length, 21);
        assert.equal(parts.filter((p) => p.hint === "core").length, 22);
    });

    it("divides trope from trope where there is no base text at all (204367.Tp3)", () => {
        const parts = split(byId("204367.Tp3"));
        assert.equal(parts.length, 5);
        assert.deepEqual(hintsOf(parts), ["core", "separator", "core", "separator", "core"]);
    });
});

// ---------------------------------------------------------------------------------------------
// "(A)" / "(B)" / "(a)" / "(A1)" / "(2)" label a trope insertion. They are cut at, but the text
// after them is NOT typed on that basis: unlike the case convention, the label rule was only
// inferred from reading examples and never checked against a catalogued <parent>:NN element.
// ---------------------------------------------------------------------------------------------

describe("(A)-style insertion labels", () => {
    it("cuts at an upper-case label and keeps it as a separator", () => {
        const parts = split("Sanctus (A) Pater lumen (B) Genitus ex deo");
        assert.deepEqual(textsOf(parts), [
            "Sanctus",
            "(A)",
            "Pater lumen",
            "(B)",
            "Genitus ex deo",
        ]);
        assert.deepEqual(hintsOf(parts), ["core", "separator", "core", "separator", "core"]);
    });

    it("cuts at lower-case, letter-and-digit, and bare-digit labels too", () => {
        assert.deepEqual(textsOf(split("Sanctus (a) Pater (b) Genitus")), [
            "Sanctus",
            "(a)",
            "Pater",
            "(b)",
            "Genitus",
        ]);
        assert.deepEqual(textsOf(split("Sanctus (A1) Pater")), ["Sanctus", "(A1)", "Pater"]);
        assert.deepEqual(textsOf(split("Sanctus (2) Pater")), ["Sanctus", "(2)", "Pater"]);
    });

    it("does not call the text after a label a trope", () => {
        // The tempting reading — "(A) Pater lumen aeternum is a labelled trope insertion" — is
        // exactly what is refused. Typing on it would promote text on unvalidated evidence.
        const parts = split("Sanctus (A) Pater lumen (B) Genitus ex deo");
        assert.deepEqual(
            hintsOf(parts).filter((h) => h !== "separator"),
            ["core", "core", "core"]
        );
    });

    it("accepts a label right after a pipe, as 509504.Tp10 has it", () => {
        assert.deepEqual(textsOf(split("Sanctus | (A) Pater lumen")), [
            "Sanctus",
            "|",
            "(A)",
            "Pater lumen",
        ]);
        const real = split(byId("509504.Tp10"));
        assert.ok(real.some((p) => p.hint === "separator" && p.text === "(A)"));
    });

    it("reads a parenthesised UPPER-CASE phrase as the opposite of a label", () => {
        // "(MISIT DOMINUS ANGELUM SUUM)" wraps a base-text incipit rather than labelling an
        // insertion, so it is an element in its own right — a core, NOT a separator. The hints
        // are the whole point here: a greedy label rule would produce these same three texts and
        // then invite "Remove separators" to delete the chant's own words.
        assert.deepEqual(split("(MISIT DOMINUS ANGELUM SUUM) | Est quia cunctorum"), [
            { hint: "core", text: "(MISIT DOMINUS ANGELUM SUUM)" },
            { hint: "separator", text: "|" },
            { hint: "core", text: "Est quia cunctorum" },
        ]);
    });

    it("keeps a label that is the entire text", () => {
        assert.deepEqual(split("(A)"), [{ hint: "separator", text: "(A)" }]);
    });
});

// ---------------------------------------------------------------------------------------------
// ".." / "..." / "…" abbreviate a known base incipit — "GLORIA .. VOLUNTATIS" stands for the
// whole of "Gloria in excelsis ... bonae voluntatis". They GLUE: never a split point. "*"
// truncates an incipit and glues to its LEFT only, the trope following it.
// ---------------------------------------------------------------------------------------------

describe("elision and truncation glue", () => {
    it("never cuts inside an elision", () => {
        assert.deepEqual(textsOf(split("GLORIA .. VOLUNTATIS")), ["GLORIA .. VOLUNTATIS"]);
        assert.deepEqual(textsOf(split("GLORIA ... voluntatis Rex")), [
            "GLORIA ... voluntatis Rex",
        ]);
        assert.deepEqual(textsOf(split("GLORIA … voluntatis Rex")), ["GLORIA … voluntatis Rex"]);
    });

    it("lets an all-caps elision supply the upper-case side of a contrast by itself", () => {
        assert.deepEqual(textsOf(split("AGNUS .. MUNDI qui tollis")), [
            "AGNUS .. MUNDI",
            "qui tollis",
        ]);
    });

    it("reads a mixed-case elision as no case evidence at all, and so leaves the text whole", () => {
        // "GLORIA .. voluntatis" is one atomic span whose own letters are not all capitals, so
        // there is no capitalised unit anywhere to contrast with — which is why ah47196 comes
        // out as whole segments between its pipes rather than being cut on a guess.
        assert.deepEqual(textsOf(split("GLORIA .. voluntatis Rex immense")), [
            "GLORIA .. voluntatis Rex immense",
        ]);
    });

    it("glues '*' to its left only, so the trope after it separates", () => {
        assert.deepEqual(textsOf(split("AGNUS * Qui sedes")), ["AGNUS *", "Qui sedes"]);
        assert.deepEqual(textsOf(split("AGNUS DEI * qui tollis peccata")), [
            "AGNUS DEI *",
            "qui tollis peccata",
        ]);
    });

    it("never cuts an elision in half, in any text in the fixture", () => {
        // A cut inside "X .. Y" would leave one element ending on the marker and the next one
        // carrying the rest, so two neighbouring elements are what to look for. A marker at the
        // very end of a segment is a different thing — Cantus Index writes those, they abbreviate
        // nothing that follows, and they stay with their own text.
        for (const row of fixture) {
            const parts = split(row.fulltext);
            parts.forEach((part, i) => {
                const next = parts[i + 1];
                if (part.hint !== "core" || !next || next.hint !== "core") return;
                assert.doesNotMatch(
                    part.text,
                    /(\.{2,}|…)$/,
                    `${row.cid} (${row.category}) cut inside an elision: "${part.text}" then "${next.text}"`
                );
                assert.doesNotMatch(
                    next.text,
                    /^(\.{2,}|…)/,
                    `${row.cid} (${row.category}) cut inside an elision: "${part.text}" then "${next.text}"`
                );
            });
        }
    });
});

// ---------------------------------------------------------------------------------------------
// "(...)" / "(..)" mark omitted text and "[...]" an editorial supplement, which can sit inside a
// word ("[ACCEND]E"). Neither is an element, and neither is ever a split point. They are masked
// before anything else runs, so a "(..)" can't be read as a label and a "[...]" can't be split
// through.
// ---------------------------------------------------------------------------------------------

describe("editorial marks", () => {
    it("does not mistake omitted-text brackets for a label", () => {
        assert.deepEqual(textsOf(split("GLORIA (...) VOLUNTATIS")), ["GLORIA (...) VOLUNTATIS"]);
        assert.deepEqual(textsOf(split("GLORIA (..) VOLUNTATIS")), ["GLORIA (..) VOLUNTATIS"]);
    });

    it("treats a mark that is the whole of a piece as a separator, since it is not an element", () => {
        assert.deepEqual(split("(...)"), [{ hint: "separator", text: "(...)" }]);
    });

    it("never cuts through a supplement, not even one inside a word", () => {
        assert.deepEqual(textsOf(split("[ACCEND]E lumen sensibus")), ["[ACCEND]E lumen sensibus"]);
        assert.deepEqual(textsOf(split("SANCTUS [ACCEND]E dominus")), [
            "SANCTUS",
            "[ACCEND]E dominus",
        ]);
    });

    it("keeps a supplement with the words around it rather than making it evidence", () => {
        assert.deepEqual(textsOf(split("VENI CREATOR [SPIRITUS] mentes tuorum")), [
            "VENI CREATOR",
            "[SPIRITUS] mentes tuorum",
        ]);
    });

    it("cannot read a bracketed number as a strophe marker", () => {
        // The masking placeholder is delimited by U+0001, a character chant text never holds,
        // precisely so the index inside it can never be confused with a real number.
        assert.deepEqual(textsOf(split("[2] Sanctus deus omnipotens")), [
            "[2] Sanctus deus omnipotens",
        ]);
    });

    it("restores every masked span, leaking no placeholder into an element", () => {
        for (const row of [...fixture.map((r) => r.fulltext), ...SYNTHETIC]) {
            for (const part of split(row)) {
                assert.ok(
                    !part.text.includes(MASK_DELIMITER),
                    `a masking placeholder survived into: ${part.text}`
                );
            }
        }
    });
});

// ---------------------------------------------------------------------------------------------
// A bare leading number is a strophe marker.
// ---------------------------------------------------------------------------------------------

describe("strophe numbers", () => {
    it("takes a leading one- or two-digit number as a separator", () => {
        assert.deepEqual(textsOf(split("2 Caelicolas mundo Laudamus te")), [
            "2",
            "Caelicolas mundo Laudamus te",
        ]);
    });

    it("takes one at the head of each pipe-delimited stretch, as AH47206.3 has them", () => {
        assert.deepEqual(textsOf(split("2 Caelicolas mundo | 4 Aula cui supera")), [
            "2",
            "Caelicolas mundo",
            "|",
            "4",
            "Aula cui supera",
        ]);
        assert.ok(split(byId("AH47206.3")).some((p) => p.hint === "separator" && p.text === "2"));
    });

    it("leaves a number alone when it is not leading, or is too long to be a strophe", () => {
        assert.deepEqual(textsOf(split("Sanctus 2 deus")), ["Sanctus 2 deus"]);
        assert.deepEqual(textsOf(split("1234 Sanctus deus")), ["1234 Sanctus deus"]);
    });
});

// ---------------------------------------------------------------------------------------------
// Whitespace and degenerate input. The composer hands over whatever Cantus Index returned.
// ---------------------------------------------------------------------------------------------

describe("whitespace and degenerate input", () => {
    it("normalises runs of whitespace and trims every piece", () => {
        assert.deepEqual(textsOf(split("SANCTUS   \n\t dominus  deus  ")), [
            "SANCTUS",
            "dominus deus",
        ]);
        assert.deepEqual(textsOf(split("  SANCTUS dominus  ")), ["SANCTUS", "dominus"]);
    });

    it("returns nothing for empty or blank text", () => {
        assert.deepEqual(split(""), []);
        assert.deepEqual(split("   "), []);
        assert.deepEqual(split("\n\t "), []);
    });

    it("returns one piece for a single word, which is what greys the menu out", () => {
        assert.deepEqual(split("Sanctus"), [{ hint: "core", text: "Sanctus" }]);
    });

    it("survives a text that is only a separator", () => {
        assert.deepEqual(split("|"), [{ hint: "separator", text: "|" }]);
    });
});

// ---------------------------------------------------------------------------------------------
// The promises the feature rests on, checked over every real text in the fixture and every
// synthetic case used above. A failure here means the tool has started doing something a
// cataloguer's own hand-split would not: losing text, inventing elements, or making a judgement.
// ---------------------------------------------------------------------------------------------

describe("what the rules must never do, over every text in the fixture", () => {
    const ALL = [
        ...fixture.map((r) => ({ label: `${r.cid} (${r.category})`, text: r.fulltext })),
        ...SYNTHETIC.map((t) => ({ label: `synthetic ${JSON.stringify(t)}`, text: t })),
    ];
    const squash = (s) => s.replace(/\s+/g, "").toLowerCase();

    it("never alters the text: the pieces put back together are the input", () => {
        for (const { label, text } of ALL) {
            assert.equal(
                squash(textsOf(split(text)).join("")),
                squash(text),
                `${label} lost or gained text`
            );
        }
    });

    it("never produces an empty element", () => {
        for (const { label, text } of ALL) {
            for (const part of split(text)) {
                assert.ok(part.text.trim().length > 0, `${label} produced an empty element`);
            }
        }
    });

    it("never hints anything but core or separator", () => {
        for (const { label, text } of ALL) {
            for (const part of split(text)) {
                assert.ok(
                    part.hint === "core" || part.hint === "separator",
                    `${label} produced hint ${JSON.stringify(part.hint)}`
                );
            }
        }
    });

    it("only ever calls a marker a separator, never a stretch of chant text", () => {
        // "Remove separators" deletes every one of these in a click, so what may wear the hint has
        // to stay closed: a pipe, an (A)-style label, a strophe number, or an editorial mark. If
        // anything holding the chant's own words could be hinted separator, that button would
        // quietly delete text.
        const MARKER = /^(\|\|?|\([A-Za-z]\d?\)|\(\d{1,2}\)|\d{1,2}|\([.…\s]*\)|\[[^\]]*\])$/;
        for (const { label, text } of ALL) {
            for (const part of split(text)) {
                if (part.hint !== "separator") continue;
                assert.match(
                    part.text,
                    MARKER,
                    `${label} called this a separator: ${JSON.stringify(part.text)}`
                );
            }
        }
    });

    it("never hints 'component' — the rules find boundaries, they do not classify", () => {
        for (const { label, text } of ALL) {
            for (const part of split(text)) {
                assert.notEqual(part.hint, "component", `${label} classified an element`);
            }
        }
    });

    it("splits once and for all: re-splitting a piece returns that piece unchanged", () => {
        // Two things ride on this. "Split automatically" greys itself out after a run, which is
        // only honest if a second run really would find nothing; and the cataloguer must be able
        // to trust that clicking twice is not a way to lose their work.
        for (const { label, text } of ALL) {
            for (const part of split(text)) {
                const again = split(part.text);
                assert.equal(again.length, 1, `${label}: re-splitting "${part.text}" divided it`);
                assert.equal(again[0].text, part.text, `${label}: re-splitting changed the text`);
            }
        }
    });
});

// ---------------------------------------------------------------------------------------------
// The composer only asks one question of the rules — "is there more than one piece?" — to decide
// whether "Split automatically" is offered or greyed out.
// ---------------------------------------------------------------------------------------------

describe("the grey-out decision: is there more than one piece?", () => {
    it("finds nothing to split in a plain untroped chant (007989)", () => {
        assert.equal(split(byId("007989")).length, 1);
    });

    it("finds something to split in each ground-truth chant", () => {
        assert.ok(split(byId("g04828")).length > 1);
        assert.ok(split(byId("ah47439")).length > 1);
        assert.ok(split(byId("g01349.tp14")).length > 1);
    });

    it("finds nothing left to split in any piece of an already-split chant", () => {
        for (const cid of ["g04828", "ah47439", "g01349.tp14", "ah47196", "509504.Tp6"]) {
            for (const part of split(byId(cid))) {
                assert.equal(
                    split(part.text).length,
                    1,
                    `${cid} would still offer a split after being split`
                );
            }
        }
    });
});

// ---------------------------------------------------------------------------------------------
// The helpers, pinned where each decision is actually made. Testing only through splitText
// leaves these inferable but not stated, and they are where the conventions are encoded.
// ---------------------------------------------------------------------------------------------

describe("internals: how case is judged", () => {
    it("needs two capital letters to call a word capitalised", () => {
        assert.equal(internals.isCaps("SANCTUS"), true);
        assert.equal(internals.isCaps("Sanctus"), false);
        assert.equal(internals.isCaps("O"), false); // a lone capital is not evidence
        assert.equal(internals.isCaps("GLÓRIA"), true);
    });

    it("counts anything not wholly capitalised as lower-ish, including Title Case", () => {
        assert.equal(internals.isLowerish("sanctus"), true);
        assert.equal(internals.isLowerish("Sanctus"), true);
        assert.equal(internals.isLowerish("SANCTUS"), false);
        assert.equal(internals.isLowerish("O"), false); // too short to say either way
    });

    it("ignores characters that have no case", () => {
        assert.deepEqual(internals.letters("a1-b!"), ["a", "b"]);
        assert.deepEqual(internals.letters("2"), []);
    });
});

describe("internals: how a segment is broken up", () => {
    it("keeps an elision span as one atomic unit", () => {
        assert.deepEqual(internals.units("GLORIA .. VOLUNTATIS Rex"), [
            { text: "GLORIA .. VOLUNTATIS", atomic: true },
            { text: "Rex", atomic: false },
        ]);
    });

    it("marks structural pieces as segment or separator, in reading order", () => {
        assert.deepEqual(internals.structuralSplit("A | (B) c"), [
            { role: "seg", text: "A" },
            { role: "sep", text: "|" },
            { role: "sep", text: "(B)" },
            { role: "seg", text: "c" },
        ]);
    });

    it("never emits a blank structural piece, which is what the rest relies on", () => {
        // autoSplitText trusts this and does not re-check for emptiness, so it is pinned here.
        const awkward = ["", "   ", "|", " | ", "| |", "A |  | B", "  (A)  ", "\n\t|\t\n"];
        for (const text of [...awkward, ...SYNTHETIC, ...fixture.map((r) => r.fulltext)]) {
            for (const part of internals.structuralSplit(text)) {
                assert.ok(
                    part.text.trim().length > 0,
                    `structuralSplit(${JSON.stringify(text)}) emitted a blank piece`
                );
            }
        }
    });

    it("declines to divide a segment with no case contrast in it", () => {
        assert.equal(internals.caseRuns("sanctus dominus"), null);
        assert.equal(internals.caseRuns("SANCTUS DOMINUS"), null);
    });

    it("returns core runs — never a type — where there is a contrast", () => {
        assert.deepEqual(internals.caseRuns("SANCTUS dominus"), [
            { hint: "core", text: "SANCTUS" },
            { hint: "core", text: "dominus" },
        ]);
    });

    it("merges neighbouring runs that share a hint", () => {
        assert.deepEqual(
            internals.mergeRuns([
                { hint: "core", text: "SANCTUS" },
                { hint: "core", text: "DEUS" },
                { hint: "separator", text: "|" },
            ]),
            [
                { hint: "core", text: "SANCTUS DEUS" },
                { hint: "separator", text: "|" },
            ]
        );
    });

    it("tidies the whitespace of what it merges", () => {
        assert.deepEqual(
            internals.mergeRuns([
                { hint: "core", text: "  SANCTUS  " },
                { hint: "core", text: "DEUS\n\tPATER" },
            ]),
            [{ hint: "core", text: "SANCTUS DEUS PATER" }]
        );
    });
});

// ---------------------------------------------------------------------------------------------
// The fixture itself, so a bad edit to it fails loudly here rather than quietly weakening every
// test above.
// ---------------------------------------------------------------------------------------------

describe("the fixture", () => {
    it("holds a text for every convention the rules claim to know", () => {
        const categories = new Set(fixture.map((r) => r.category));
        for (const required of [
            "ground_truth_case_only",
            "ground_truth_case_and_pipe",
            "ground_truth_case_cued_base",
            "base_chant_nothing_to_split",
            "case_boundary_only",
            "pipe_separator",
            "double_pipe",
            "pipe_boundaries_no_case_signal",
            "pipe_between_tropes_no_core",
            "label_letter",
            "label_lowercase",
            "label_letter_digit",
            "label_digit",
            "labels_after_pipes",
            "strophe_number",
            "elision_two_dots",
            "elision_three_dots",
            "elision_ellipsis_char",
            "asterisk_truncation",
            "editorial_omitted",
            "editorial_brackets",
            "editorial_intraword",
            "paren_uppercase_incipit",
            "all_lower_no_split",
            "lone_capital_word",
            "plain_chant_nothing_to_split",
        ]) {
            assert.ok(categories.has(required), `fixture has no ${required} text`);
        }
    });

    it("gives every text a Cantus ID and a non-empty full text", () => {
        for (const row of fixture) {
            assert.ok(row.cid, "a fixture row has no cid");
            assert.ok(row.fulltext && row.fulltext.trim(), `${row.cid} has no text`);
            assert.ok(row.category, `${row.cid} has no category`);
        }
    });
});
