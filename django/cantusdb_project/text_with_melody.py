from latin_syllabification import syllabify_word

# some useful info taken from the text entry guideline:
# the symbols are present only in the MS spelling, not std spelling
# vertical stroke | identifies sections within a chant, it's meant to help align text with melody
#   should be surrounded by spaces
# tilda ~ identifies "Psalm incipits" or any text that doesn't align with pitches
#   immediately before text, no spaces
# IPSUM (same), it looks like: | space ～Ipsum space [actual psalm text from the antiphon]
#   this doesn't affect alignment, just treat the part between ~ and next | as one syllable in one word

#                                   MISSING TEXT WITH READABLE PITCHES
# the number sign # identifies missing text, it could be missing complete word(s) or syllable(s)
#   complete words missing: space # space
#   partially visible word (syllables missing): - (one hyphen represents missing syllables) then space # space for missing section of text
#   volpiano for the section with missing text: -- between neumes, begin and end section with --- (always treat the section as a word?)

#                                   READABLE TEXT UNDER MISSING PITCHES
# for a complete word:
#   enclose affected text in {},
#   volpiano use 6------6 to represent missing pitches, --- before and after each 6

# for select syllables:
#   enclose affected syllable(s) in {},
#   volpiano use 6------6 to represent missing pitches, no --- before and after each 6???
# In either case, the 6*6 align with {*}

#                                   MISSING BOTH PITCHES AND TEXT
# no text, no pitches visible:
#   {#} indicates missing text,
#   if partial word readable, use - for the missing sylable(s) and then enter space {#} space for the remainder of missing text
#   volpiano use 6------6 as described above

# no pitches, partial text visible:
#   enclose affected text in {}, use - for the missing portions of words
#   use # within {} to indicate location of missing text
#   volpiano use 6------6 as described above


# there should never be a space in volpiano. hyphens do the separation and spacing.
def syllabize_melody(volpiano):
    # split volpiano into melody words
    words_melody = [word + "---" for word in volpiano.split("---")]
    # remove the trailing "---" (added in previous line) from the last word
    words_melody[-1] = words_melody[-1][:-3]

    # split melody words into syllables
    syls_melody = []
    for word in words_melody[:-1]:
        syls = [syl + "--" for syl in word.strip("---").split("--")]
        # this next line is equivalent to removing the trailing "--" and
        # then adding the "---" back to the end of each word
        syls[-1] = syls[-1] + "-"
        syls_melody.extend(syls)

    if "--" in words_melody[-1]:
        # if the last melody word is multi-syllable
        syls = [syl + "--" for syl in words_melody[-1].split("--")]
        # remove the trailing "--" (added in previous line) from the last syllable
        syls[-1] = syls[-1][:-2]
        syls_melody.extend(syls)
    elif words_melody[-1]:
        # if the last melody word is not empty string (it can be barline, syllable, or -)
        syls_melody.append(words_melody[-1])
    return syls_melody


def syllabize_text(text, pre_syllabized=False):
    if pre_syllabized:
        # deal with syllabized text saved in DB
        # example of syllabized full text in DB:
        # Spi-ri-tus san-ctus in te des-cen-det ma-ri-a ne ti-me-as ha-bens in u-te-ro fi-li-um de-i al-le-lu-ya "
        syllabized_text = text

        # if there is a vertical line in the syllabized text
        # it shouldn't be grouped into any adjacent word
        # so we must make sure it is surrounded by spaces
        if "|" in syllabized_text:
            substrs_around_barline = syllabized_text.split("|")
            print(substrs_around_barline)
            # this may introduce extra spaces. those will be removed in the next part
            syllabized_text = " | ".join(substrs_around_barline)
            print(syllabized_text)

        words_text = syllabized_text.split(" ")
        # initialize `tilda_found`, this is for locating the part between ~ and |, which shouldn't be syllabized
        tilda_found = False
        syls_text = []
        for i, word in enumerate(words_text):
            if word.startswith("~"):
                print("~ found")
                tilda_found = True
                tilda_idx = i
                # initialize the index for the | following ~,
                # it defaults to the end of list in case there's no | following ~,
                barline_idx = len(words_text)
                for i, word in enumerate(words_text[tilda_idx + 1 :]):
                    if word.startswith("|"):
                        print("| found")
                        # if there's a | following the ~, record the index of that word
                        barline_idx = tilda_idx + 1 + i
                        break
                break

        # if there is ~ in the text, the text between ~ and | needs to be merged into one syllable
        if tilda_found:

            # for words before ~, syllabize them normally
            for word in words_text[0:tilda_idx]:
                # this `if` is necessary because some chants use two spaces between syllabized words
                # splitting on space with leave empty strings in the output, causing bugs in alignment
                # also, in the previous step, there may be excessive spaces inserted around |
                # this `if` eliminates the extra spaces
                if word:
                    syls = [syl + "-" for syl in word.split("-")]
                    syls[-1] = syls[-1].strip("-")
                    syls_text.extend(syls)

            # for words between ~ and |, put them in one syllable without syllabification
            unsyllabized = " ".join(words_text[tilda_idx:barline_idx])
            syls_text.append(unsyllabized)

            # for words after |, syllabize them normally
            for word in words_text[barline_idx:]:
                if word:
                    syls = [syl + "-" for syl in word.split("-")]
                    syls[-1] = syls[-1].strip("-")
                    syls_text.extend(syls)
        # if there is no ~ in text, syllabize the whole text normally
        else:
            for word in words_text:
                if word:
                    syls = [syl + "-" for syl in word.split("-")]
                    syls[-1] = syls[-1].strip("-")
                    syls_text.extend(syls)
        # the first syllable in volpiano is always a clef,
        # add an empty syllable in text to aligh with it
        syls_text.insert(0, "")

    else:
        """this part should be very similar to the 'pre-stored syllabized text' part
        a lot of code in this part should be fixed according to what's in that part"""
        # if there is melody but no pre-syllabized text stored in DB,
        # we use our own script to syllabize the text

        words_text = text.split(" ")
        # initialize `tilda_found`, this is for locating the part between ~ and |, which shouldn't be syllabized
        tilda_found = False
        syls_text = []

        for i, word in enumerate(words_text):
            # the ~ starts a segment of text which do not go through syllabification
            # this segment ends at the next | or the end of text
            if word.startswith("~"):
                # print("~ found")
                tilda_found = True
                # if there is a ~, record the index of that word
                tilda_idx = i
                # check the words after ~ for |,
                # if not found, `barline_idx` set to the end of list (default)
                barline_idx = len(words_text)
                # if found, `barline_idx` will be changed in the following loop
                for i, word in enumerate(words_text[tilda_idx + 1 :]):
                    if word.startswith("|"):
                        # print("| found")
                        # if there's a | following the ~, record the index of that word
                        barline_idx = tilda_idx + 1 + i
                        break
                break

        # if there is ~ in text, the text between ~ and | needs to be merged into one syllable
        if tilda_found:
            # for words before ~, syllabify them normally
            for word in words_text[0:tilda_idx]:
                syls = syllabify_word(word)
                # add - to every syllable before the last syllable in a word
                syls = [syl + "-" for syl in syls[:-1]] + [syls[-1]]
                syls_text.extend(syls)
            # for words between ~ and |, put them in one syllable without syllabification
            unsyllabized = " ".join(words_text[tilda_idx:barline_idx])
            syls_text.append(unsyllabized)
            # for words after |, syllabize them normally
            for word in words_text[barline_idx:]:
                syls = syllabify_word(word)
                syls = [syl + "-" for syl in syls[:-1]] + [syls[-1]]
                syls_text.extend(syls)
        # if there is no ~ in text, syllabify the whole text normally
        else:
            for word in words_text:
                syls = syllabify_word(word)
                syls = [syl + "-" for syl in syls[:-1]] + [syls[-1]]
                syls_text.extend(syls)

        # the first syllable in volpiano is always a clef, align an empty text with it
        syls_text.insert(0, "")
        """is this really necessary?"""
        # for "|" in the melody, make sure it is aligned with a "|" or an empty syllable in the text
        # if "3---" in syls_melody:
        #     idx = syls_melody.index("3---")
        #     if syls_text[idx] != "|":
        #         syls_text.insert(idx, " ")
    return syls_text, tilda_found


# this function should be modified to deal with all symbols in text
# see instructions in "Text Entry and Editing Guide" starting page 5
def postprocess_symbols(syls_text, syls_melody, tilda_found):
    # no matter what text we're using, as long as there is ~ in text,
    # some text syllables (between ~ and |) are merged into one,
    # we need to merge the correponding melody into one syllable too
    if tilda_found:
        # melody (from the ~ to the next |) should NOT be syllabized
        # this loop locates the ~ in syllables
        for i, syl in enumerate(syls_text):
            if syl.startswith("~"):
                tilda_syl_idx = i
                # initialize barline_syl_idx, if no | found after ~, default to end of list
                barline_syl_idx = len(syls_text)
                break
        for i, syl in enumerate(syls_melody[tilda_syl_idx + 1 :]):
            # if | is present
            if "3" in syl:
                barline_syl_idx = tilda_syl_idx + 1 + i
                break
        joined_melody = "".join(syls_melody[tilda_syl_idx:barline_syl_idx])
        rectified_melody = (
            syls_melody[:tilda_syl_idx]
            + [joined_melody]
            + syls_melody[barline_syl_idx:]
        )
    else:
        rectified_melody = syls_melody
    return rectified_melody


def align_melody_with_text(syls_text, syls_melody):
    # if melody is longer than text, fill spaces to the end of the text
    if len(syls_melody) > len(syls_text):
        syls_text = syls_text + [" "] * (len(syls_melody) - len(syls_text))
    # if melody is shorter than text, discard the extra text (default behavior of zip)
    text_with_melody = zip(syls_melody, syls_text)
    return text_with_melody
