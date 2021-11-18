from latin_syllabification import syllabify_word
from itertools import zip_longest


def syllabize_text(text, pre_syllabized=False):
    # vertical stroke | identifies sections within a chant, it's meant to help align text with melody
    # it should be surrounded by spaces
    if "|" in text:
        substrs_around_barline = text.split("|")
        # this may introduce extra spaces. those will be removed in the next part
        text = " | ".join(substrs_around_barline)

    # curly braces {} identifies text affected by missing pitches, insert spaces before { and after }
    # so that the text in braces are are treated as a separate word
    if "{" in text:
        substrs_around_brace_start = text.split("{")
        # this may introduce extra spaces. those will be removed in the next part
        text = " {".join(substrs_around_brace_start)
    if "}" in text:
        substrs_around_brace_end = text.split("}")
        # this may introduce extra spaces. those will be removed in the next part
        text = "} ".join(substrs_around_brace_end)

    words_text = text.split(" ")
    # initialize the first word with a space, which aligns with the clef at the beginning of melody
    # syls_text is a list of lists (words). each word is a list of syllables
    syls_text = [[" "]]

    if pre_syllabized:
        for word in words_text:
            # this `if` eliminates the extra spaces
            if word:
                syls = [syl + "-" for syl in word.split("-")]
                syls[-1] = syls[-1][:-1]
                syls_text.append(syls)
    else:
        for word in words_text:
            if word:
                # if "{" in word or "}" in word:
                #     # what we want here is to make the part between {} an independent word, so that they mey be combined correctly
                #     # see 219427 and 619450
                # else:
                syls = [syl + "-" for syl in syllabify_word(word)]
                syls[-1] = syls[-1][:-1]
                syls_text.append(syls)
    return syls_text


def syllabize_melody(volpiano):
    # the clef in volpiano should be 1--- with three dashes, if missing any dash, insert it
    if volpiano[1] != "-":
        volpiano = volpiano[:1] + "-" + volpiano[1:]
    if volpiano[2] != "-":
        volpiano = volpiano[:2] + "-" + volpiano[2:]
    if volpiano[3] != "-":
        volpiano = volpiano[:3] + "-" + volpiano[3:]

    # before splitting on "---", note that some volpianos use "6------6" to identify missing content
    # the "6------6" should not be split
    if "6------6" in volpiano:
        # temporarily replace 6-----6 by *
        volpiano = volpiano.replace("6------6", "******")
    # split volpiano into melody words
    words_melody = [word + "---" for word in volpiano.split("---")]
    # remove the trailing "---" (added in previous line) from the last word
    words_melody[-1] = words_melody[-1][:-3]

    # split melody words into syllables
    #  `syls_melody` would be a list of lists (words), each word is a list of syllables
    syls_melody = []
    for word in words_melody[:-1]:
        # to accommodate for text like `mar{tirum et}`, we appended space before all curly braces,
        # so that the text in curly braces can nicely align with the `---6------6---` in melody
        # (they're both treated as a single word)
        # however, there are cases like `an{#}` (originally no space before curly brace,
        # while the corresp `6------6` in melody has only two leading dashes because it corresponds to only a syllable)
        # in order to accommodate both cases, we change the syllable-level `6------6` into word-level
        # i.e., make it a single word on its own
        # example: see 219427 and 619450
        # this variable is for capturing the syllable-level `6------6` (below referred to as `gap`),
        syl_level_gap = None
        # `syls` contains the melody syllables in each melody word
        syls = []
        # the last 3 charactors (---) are discarded
        for i, syl in enumerate(word[:-3].split("--")):
            if "******" in syl:
                # if the syllable contains `6------6`
                # (it may not be exactly `6------6`, it could also be sth like `6------677`)
                if i == 0:
                    # if `6------6` is the first syllable in the word, it must be a word-level gap
                    # just put it directly into the list for the current word
                    syl = syl.replace("******", "6------6")
                    syls.append(syl + "--")
                else:
                    # if the gap is not the first syllable in the word,
                    # the word must be sth like `---k--6------677---` (syl-level gap)
                    # we save it and later add it directly to the `syls_melody` list
                    syl_level_gap = syl.replace("******", "6------6")
            else:
                # for normal syls, directly add them to the list for the current word
                syls.append(syl + "--")
        # this next line is equivalent to removing the trailing "--" and
        # then adding the "---" back to the end of each word
        syls[-1] = syls[-1] + "-"
        syls_melody.append(syls)
        if syl_level_gap:
            # if there is syl-level gap, add it to `syls_melody` like a word
            syls_melody.append([syl_level_gap])

    # for the last word in melody
    last_word = words_melody[-1]
    if "******" in last_word:
        # change * back to 6------6
        word = word.replace("******", "6------6")
        syls_melody.append([word])
    else:
        syls = [syl + "--" for syl in last_word.split("--")]
        # remove the trailing "--" (added in previous line) from the last syllable
        syls[-1] = syls[-1][:-2]
        syls_melody.append(syls)
    # print(syls_melody)
    return syls_melody


def find_next_barline(syls_text, tilda_idx):
    # set default to beyond the last word, in case the barline is missing, all words after ~ will be combined
    barline_idx = len(syls_text)
    # the barline is a word on its own, so start from the next word
    for i, word in enumerate(syls_text[tilda_idx + 1 :]):
        if word == ["|"]:
            barline_idx = tilda_idx + 1 + i
            break
    return barline_idx


def find_next_barline_mel(syls_melody, tilda_idx):
    # set default to beyond the last word, in case the barline is missing, all words after ~ will be combined
    barline_idx_mel = len(syls_melody)
    # the barline is a word on its own, so start from the next word
    for i, word in enumerate(syls_melody[tilda_idx + 1 :]):
        if word == ["3---"] or word == ["4---"] or word == ["3"] or word == ["4"]:
            barline_idx_mel = tilda_idx + 1 + i
            break
    return barline_idx_mel


def find_next_brace_end(syls_text, brace_start_idx):
    # set default to the last word, in case the brace end is missing, all words after { will be combined
    brace_end_idx = len(syls_text) - 1
    # there are cases where there's only one word in the braces, so start from the same word as the brace start
    for i, word in enumerate(syls_text[brace_start_idx:]):
        if word[-1][-1] == "}":
            brace_end_idx = brace_start_idx + i
            break
    return brace_end_idx


def postprocess(syls_text, syls_melody):
    # process the braces {} before processing ~ and |, because some chants have ~ inside {}, in this case,
    # processing {} will solve both
    brace_start_idx = []
    brace_end_idx = []
    for i, word in enumerate(syls_text):
        if word[0][0] == "{":
            brace_start_idx.append(i)
        if word[-1][-1] == "}":
            brace_end_idx.append(i)
    for idx in brace_start_idx:
        next_brace_end = find_next_brace_end(syls_text, idx)
        rebuilt_words = []
        for word in syls_text[idx : next_brace_end + 1]:
            word = [syl.strip("-") for syl in word]
            rebuilt_word = "".join(word)
            rebuilt_words.append(rebuilt_word)
        syls_text[idx] = [" ".join(rebuilt_words)]
        for i in range(idx + 1, next_brace_end + 1):
            syls_text[i] = ["*"]
    syls_text = [word for word in syls_text if word != ["*"]]

    # process the text between ~ and |
    barline_idx = []
    tilda_idx = []
    for i, word in enumerate(syls_text):
        if word == ["|"]:
            barline_idx.append(i)
        if word[0][0] == "~":
            tilda_idx.append(i)

    # when the text between ~ and | is combined into one word (since they aren't syllabized, they're actually one syllable),
    # the corresponding melody needs to be combined into one syllable, so that they align beautifully.
    # if multiple words are present between ~ and |, they are combined into one word.
    # this causes a change in the index of every word after them.
    # this becomes a problem when there are multiple ~ in the text (more than one region require combination).
    # `melody_offset` measures the change in indexing, so that we always index the correct words for combination
    melody_offset = 0
    for idx in tilda_idx:
        # combine melody words
        # based on the tilda index in text, find the index of melody words to combine
        # most of the time, only one melody word needs to be combined
        # but some situations require combination of multiple melody words, see 399083
        next_barline_mel = find_next_barline_mel(syls_melody, idx - melody_offset)
        melody_words_to_combine = syls_melody[idx - melody_offset : next_barline_mel]
        # combine the melody words into one word (a list of melody syls)
        melody_words_combined = [
            syl for word in melody_words_to_combine for syl in word
        ]
        try:
            # combine the melody syls into one syl
            syls_melody[idx - melody_offset] = ["".join(melody_words_combined)]
        except IndexError:
            # sometimes the melody is shorter than text, so the tilda in text doesn't have melody
            print("MELODY SHORTER THAN TEXT, DIDNT REACH TILDA")
            break
        # for the melody words that have been merged into some word before them,
        # mark them differently so that they still occupy the index and do not appear in the results
        for i in range(idx - melody_offset + 1, next_barline_mel):
            syls_melody[i] = ["*"]

        # combine text words
        rebuilt_words = []
        next_barline = find_next_barline(syls_text, idx)
        for word in syls_text[idx:next_barline]:
            word = [syl.strip("-") for syl in word]
            rebuilt_word = "".join(word)
            rebuilt_words.append(rebuilt_word)
        syls_text[idx] = [" ".join(rebuilt_words)]
        for i in range(idx + 1, next_barline):
            syls_text[i] = ["*"]

        # this is crucial for getting the index correct. melody offset updating depends on the number of melody words
        # and text words that have been merged, and also the current melody offset
        melody_offset = (
            next_barline - idx - 1 - (next_barline_mel - idx - 1 + melody_offset)
        )

    # remove the previously merged words (marked *) from the final results
    syls_melody = [word for word in syls_melody if word != ["*"]]
    syls_text = [word for word in syls_text if word != ["*"]]
    return syls_text, syls_melody


def align(syls_text, syls_melody):
    # if melody has more words than text, fill spaces to the end of the text
    # if melody has fewer words than text, discard the extra text (loop through melody length below)
    if len(syls_melody) > len(syls_text):
        syls_text = syls_text + [" "] * (len(syls_melody) - len(syls_text))

    list_of_zips = []
    for i in range(len(syls_melody)):
        # for every word, if melody has more syllables, add space to the text
        if len(syls_melody[i]) > len(syls_text[i]):
            word_zip = zip_longest(syls_melody[i], syls_text[i], fillvalue=" ")
        # if text has more syllables, add dash to melody
        else:
            word_zip = zip_longest(syls_melody[i], syls_text[i], fillvalue="-")
        list_of_zips.append(word_zip)

    return list_of_zips
