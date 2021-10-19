import re
from latin_syllabification import syllabify_word
from itertools import zip_longest


def syllabize_text(text, pre_syllabized=False):
    # if there is vertical line in the text, make sure it is surrounded by spaces
    if "|" in text:
        substrs_around_barline = text.split("|")
        # this may introduce extra spaces. those will be removed in the next part
        text = " | ".join(substrs_around_barline)

    words_text = text.split(" ")
    # initialize this with a space, which aligns with the clef at the beginning of melody
    # syls_text is a list of lists (words). each word is a list of syllables
    syls_text = [[" "]]

    if pre_syllabized:
        for word in words_text:
            if word:
                syls = [syl + "-" for syl in word.split("-")]
                syls[-1] = syls[-1][:-1]
                syls_text.append(syls)
    else:
        for word in words_text:
            if word:
                syls = [syl + "-" for syl in syllabify_word(word)]
                syls[-1] = syls[-1][:-1]
                syls_text.append(syls)
    return syls_text


def syllabize_melody(volpiano):
    print(volpiano)
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
    syls_melody = []
    for word in words_melody[:-1]:
        if "******" in word:
            # change * back to 6------6
            word = word.replace("******", "6------6")
            syls_melody.append([word])
        else:
            syls = [syl + "--" for syl in word[:-3].split("--")]
            # this next line is equivalent to removing the trailing "--" and
            # then adding the "---" back to the end of each word
            syls[-1] = syls[-1] + "-"
            syls_melody.append(syls)

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
    print(syls_melody)
    return syls_melody


def find_next_barline(syls_text, tilda_idx):
    barline_idx = len(syls_text)
    for i, word in enumerate(syls_text[tilda_idx + 1 :]):
        if word == ["|"]:
            barline_idx = tilda_idx + 1 + i
            break
    return barline_idx


def postprocess(syls_text, syls_melody):
    barline_idx = []
    tilda_idx = []
    for i, word in enumerate(syls_text):
        if word == ["|"]:
            barline_idx.append(i)
        if word[0][0] == "~":
            tilda_idx.append(i)

    for idx in tilda_idx:
        syls_melody[idx] = ["".join(syls_melody[idx])]

        # print(syls_text)
        next_barline = find_next_barline(syls_text, idx)
        # print(idx)
        # print(next_barline)
        rebuilt_words = []
        for word in syls_text[idx:next_barline]:
            word = [syl.strip("-") for syl in word]
            rebuilt_word = "".join(word)
            rebuilt_words.append(rebuilt_word)
        syls_text[idx] = [" ".join(rebuilt_words)]
        for i in range(idx + 1, next_barline):
            syls_text[i] = ["*"]
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
