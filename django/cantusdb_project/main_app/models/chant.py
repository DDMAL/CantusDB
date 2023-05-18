from django.db.models.query import QuerySet
from main_app.models.base_chant import BaseChant
from align_text_mel import *


class Chant(BaseChant):
    """The model for chants

    Both Chant and Sequence must have the same fields, otherwise errors will be raised
    when a user searches for chants/sequences in the database. Thus, all fields,
    properties and attributes should be declared in BaseChant in order to keep the two
    models harmonized, even if only one of the two models uses a particular field.
    """

    def index_components(self) -> dict:
        """Constructs a dictionary of weighted lists of search terms.

        Returns:
            dict: A dictionary of lists of search terms, the keys are the
                  different weights
        """
        incipit = self.incipit if self.incipit else None
        full_text = self.manuscript_full_text if self.manuscript_full_text else None
        full_text_std_spelling = (
            self.manuscript_full_text_std_spelling
            if self.manuscript_full_text_std_spelling
            else None
        )
        source = self.source.title if self.source else None
        genre = self.genre.name if self.genre else None
        feast = self.feast.name if self.feast else None
        office = self.office.name if self.office else None
        return {
            "A": (
                " ".join(
                    filter(
                        None,
                        [incipit, full_text, full_text_std_spelling, source],
                    )
                )
            ),
            "B": (" ".join(filter(None, [genre, feast, office]))),
        }

    def related_chants_by_cantus_id(self) -> QuerySet:
        return Chant.objects.filter(cantus_id=self.cantus_id)

    def get_next_chant(self):
        """return the next chant in the same source
        Returns:
            chant_object/None: the next chant object, or None if there is no next chant
        """

        def get_next_folio(folio):
            """This is useful when the 'next chant' we need is on the next folio
            Args:
                folio (str): the folio number of a certain chant
            Returns:
                str: the folio number of the next folio
            """
            # For chants that end with ra, rb, va, vb - don't do anything about those. That formatting will not stay.

            if folio is None:
                # this shouldn't happen, but during testing, we may have some chants without folio
                next_folio = None
                return next_folio

            # some folios begin with an "a" - these should be treated like other folios, but preserving the leading "a"
            if folio[0] == "a":
                prefix, folio = folio[:1], folio[1:]
            else:
                prefix = ""

            stem, suffix = folio[:3], folio[3:]
            if stem.isdecimal():
                stem_int = int(stem)
            else:
                next_folio = None
                return next_folio

            if suffix == "r":
                # 001r -> 001v
                next_folio = prefix + stem + "v"
            elif suffix == "v":
                next_stem = str(stem_int + 1).zfill(3)
                next_folio = prefix + next_stem + "r"
            elif suffix == "":
                # 001 -> 002
                next_folio = prefix + str(stem_int + 1).zfill(3)

            # special cases: inserted pages
            elif suffix == "w":
                # 001w -> 001x
                next_folio = prefix + stem + "x"
            elif suffix == "y":
                # 001y -> 001z
                next_folio = prefix + stem + "z"
            elif suffix == "a":
                # 001a -> 001b
                next_folio = prefix + stem + "b"
            else:
                # unusual/uncommon suffix
                next_folio = None
            return next_folio

        try:
            next_chant = Chant.objects.get(
                source=self.source,
                folio=self.folio,
                c_sequence=self.c_sequence + 1,
            )
        except (
            Chant.DoesNotExist
        ):  # i.e. no chant with the subsequent c_sequence on same folio
            # check to see whether there are more chants on this folio after a gap in the numbering
            # e.g. situation with several sequential chants on a folio, followed by a lacuna with c_sequence 99
            subsequent_chants_this_folio = Chant.objects.filter(
                source=self.source,
                folio=self.folio,
                c_sequence__gt=self.c_sequence,
            ).order_by("c_sequence")
            if len(subsequent_chants_this_folio) >= 1:
                next_chant = subsequent_chants_this_folio[0]

            # no more chant on this folio, so get the first chant on the next folio
            else:
                chants_next_folio = Chant.objects.filter(
                    source=self.source,
                    folio=get_next_folio(self.folio),
                ).order_by("c_sequence")
                try:
                    next_chant = chants_next_folio[0]
                except AttributeError:  # i.e. next folio is None
                    return None
                except (
                    Chant.DoesNotExist
                ):  # i.e. next folio contains no chants (I think?)
                    return None
                except IndexError:  # i.e. next folio contains no chants (I think?)
                    return None
                except ValueError:  # i.e. next folio contains no chants
                    next_chant = None
        except (
            Chant.MultipleObjectsReturned
        ):  # i.e. multiple chants have the same source, folio and c_sequence
            # for example, the two chants on folio h001r c_sequence 1, in source with ID 123753
            next_chant = None
        except TypeError:  # c_sequence is None
            next_chant = None

        return next_chant

    def get_syllabized_text_and_melody(self, text_only=False):
        """Returns the syllabized text with the melody of a chant. Syllabized text splits the words from the
         full text into its syllable components based on the volpiano protocols
         (ex: Ocundare plebs fidelis cuius pater => I-O-cun-da-re plebs fi-de-lis cu-ius pa-ter)
         If volpiano is not established return None

                        Preview of melody and text:
         'manuscript_syllabized_full_text' exists =>
           preview constructed from 'manuscript_syllabized_full_text'
         no 'manuscript_syllabized_full_text', but 'manuscript_full_text' exists =>
           preview constructed from 'manuscript_full_text'
         no 'manuscript_syllabized_full_text' and no 'manuscript_full_text' =>
           preview constructed from 'manuscript_full_text_std_spelling'
        to this we add:
        no full text of any kind => preview constructed from `incipit`
        none of the above => show message explaining why melody preview has no text

        Returns:
            list/string: Returns a list of zip_longest objects containing syllabized melody and corresponding
            syllabized text elements. If text_only=True return a String with words separated by spaces and
            syllables separated by "-"
        """
        if self.manuscript_syllabized_full_text:
            syls_text = syllabize_text(
                self.manuscript_syllabized_full_text, pre_syllabized=True
            )
        elif self.manuscript_full_text:
            syls_text = syllabize_text(self.manuscript_full_text, pre_syllabized=False)
        elif self.manuscript_full_text_std_spelling:
            syls_text = syllabize_text(
                self.manuscript_full_text_std_spelling, pre_syllabized=False
            )
        elif self.incipit:
            syls_text = syllabize_text(self.incipit, pre_syllabized=False)
        else:
            syls_text = [[""]]

        if not text_only and self.volpiano:
            syls_melody = syllabize_melody(self.volpiano)
            syls_text, syls_melody = postprocess(syls_text, syls_melody)
            word_zip = align(syls_text, syls_melody)
            return word_zip
        elif text_only:
            human_readable_text = " ".join(["".join(word) for word in syls_text])
            return human_readable_text
