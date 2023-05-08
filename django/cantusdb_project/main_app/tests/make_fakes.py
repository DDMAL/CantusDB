"""Functions to make fake objects to be used for testing"""
import random
from faker import Faker

from main_app.models import Century
from main_app.models import Chant
from main_app.models import Feast
from main_app.models import Genre
from main_app.models import Notation
from main_app.models import Office
from main_app.models import Provenance
from main_app.models import RismSiglum
from main_app.models import Segment
from main_app.models import Sequence
from main_app.models import Source
from django.contrib.auth import get_user_model

from typing import Optional, List

# Max positive integer accepted by Django's positive integer field
MAX_SEQUENCE_NUMBER = 2147483647

# The incipit will be up to 100 characters of the full text
INCIPIT_LENGTH = 100

# Create a Faker instance with locale set to Latin
faker = Faker("la")


def make_random_string(
    length: int, characters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
) -> str:
    """Return a random string of a specified length.

    Args:
        length (int): Length of the generated string.
        characters (str, optional): Pool of characters to draw from while generating the string.
            Defaults to string.ascii_uppercase.

    Returns:
        str: a string composed of random characters.
    """
    return "".join(characters[random.randrange(len(characters))] for _ in range(length))


def make_fake_volpiano(
    words: int = 5,
    syllables_per_word: int = 2,
    neumes_per_syllable: int = 2,
    notes_per_neume: int = 2,
) -> str:
    """Generates a random string of volpiano.

    Args:
        words (int, optional): The number of volpiano words (i.e. substrings separated by "---") to generate.
            Defaults to 5.
        syllables_per_word (int, optional): The number of volpiano syllables (i.e. substrings separated by "--") to generate in each word.
            Defaults to 2.
        neumes_per_syllable (int, optional): The number of volpiano neumes (i.e. substrings separated by "-") to generate in each syllable.
            Defaults to 2.
        notes_per_neume (int, optional): The number of volpiano notes to generate in each neume.
            Defaults to 2.

    Raises:
        ValueError if any argument is less than 1.

    Returns:
        str: A string of valid volpiano, with a treble clef at the beginning and a barline at the end.
    """
    NOTES = "abcdefghklmnABCDEFGHKLMN"
    BARLINES = ("3", "4")  # 3: single barline, 4: double barline
    if not words >= 1:
        raise ValueError("words must be >= 1")
    elif not syllables_per_word >= 1:
        raise ValueError("syllables_per_word must be >= 1")
    elif not neumes_per_syllable >= 1:
        raise ValueError("neumes_per_syllable must be >= 1")
    elif not notes_per_neume >= 1:
        raise ValueError("notes_per_neume must be >= 1")

    words_: List[List[List[str]]] = []
    for _ in range(words):
        syllables: List[List[str]] = []
        for __ in range(syllables_per_word):
            neumes: List[str] = []
            for ___ in range(neumes_per_syllable):
                notes = []
                for ____ in range(notes_per_neume):
                    note = random.choice(NOTES)
                    notes.append(note)
                neumes.append("".join(notes))
            syllables.append("-".join(neumes))
        words_.append("--".join(syllables))
    treble_clef = "1---"
    final_barline = f"---{random.choice(BARLINES)}"
    volpiano = treble_clef + "---".join(words_) + final_barline
    return volpiano


def make_fake_century() -> Century:
    """Generates a fake Century object."""
    century = Century.objects.create(name=faker.sentence(nb_words=3))
    return century


def make_fake_chant(
    source=None,
    marginalia=None,
    folio=None,
    office=None,
    genre=None,
    position=None,
    c_sequence=None,
    cantus_id=None,
    feast=None,
    manuscript_full_text_std_spelling=None,
    incipit=None,
    manuscript_full_text_std_proofread=None,
    manuscript_full_text=None,
    volpiano=None,
    manuscript_syllabized_full_text=None,
    next_chant=None,
    differentia=None,
) -> Chant:
    """Generates a fake Chant object."""
    if source is None:
        source = make_fake_source(segment_name="CANTUS Database")
    if marginalia is None:
        marginalia = make_random_string(1)
    if folio is None:
        # two digits and one letter
        folio = faker.bothify("##?")
    if office is None:
        office = make_fake_office()
    if genre is None:
        genre = make_fake_genre()
    if position is None:
        position = make_random_string(1)
    if c_sequence is None:
        c_sequence = random.randint(1, MAX_SEQUENCE_NUMBER)
    if cantus_id is None:
        cantus_id = make_random_string(6, "0123456789")
    if feast is None:
        feast = make_fake_feast()
    if manuscript_full_text_std_spelling is None:
        manuscript_full_text_std_spelling = faker.sentence()
    if incipit is None:
        incipit = manuscript_full_text_std_spelling[0:INCIPIT_LENGTH]
    if manuscript_full_text_std_proofread is None:
        manuscript_full_text_std_proofread = False
    if manuscript_full_text is None:
        manuscript_full_text = manuscript_full_text_std_spelling
    if volpiano is None:
        volpiano = make_fake_volpiano()
    if manuscript_syllabized_full_text is None:
        manuscript_syllabized_full_text = faker.sentence(20)
    if differentia is None:
        differentia = make_random_string(2)

    chant = Chant.objects.create(
        source=source,
        marginalia=marginalia,
        folio=folio,
        c_sequence=c_sequence,
        office=office,
        genre=genre,
        position=position,
        cantus_id=cantus_id,
        feast=feast,
        mode=make_random_string(1, "0123456789*?"),
        differentia=differentia,
        finalis=make_random_string(1, "abcdefg"),
        extra=make_random_string(3, "0123456789"),
        chant_range=make_fake_volpiano(
            words=1, syllables_per_word=1, neumes_per_syllable=1, notes_per_neume=1
        ).replace(
            "---", "-"
        ),  # chant_range is of the form "1-x-y-4", x, y are volpiano notes
        addendum=make_random_string(3, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        manuscript_full_text_std_spelling=manuscript_full_text_std_spelling,
        incipit=incipit,
        manuscript_full_text_std_proofread=manuscript_full_text_std_proofread,
        manuscript_full_text=manuscript_full_text,
        manuscript_full_text_proofread=faker.boolean(),
        volpiano=volpiano,
        volpiano_proofread=faker.boolean(),
        image_link=faker.image_url(),
        cao_concordances=make_random_string(12, "ABCDEFGHIJKLMNOPQRSTUVWXYZ  "),
        melody_id="m" + make_random_string(8, "0123456789."),
        manuscript_syllabized_full_text=manuscript_syllabized_full_text,
        indexing_notes=faker.sentence(),
        json_info=None,
        next_chant=next_chant,
    )
    return chant


def make_fake_feast() -> Feast:
    """Generates a fake Feast object."""
    feast = Feast.objects.create(
        name=faker.sentence(),
        description=faker.sentence(),
        feast_code=make_random_string(8, "0123456789"),
        notes=faker.sentence(),
        month=random.randint(1, 12),
        day=random.randint(1, 31),
    )
    return feast


def make_fake_genre(name=None) -> Genre:
    """Generates a fake Genre object."""
    if name is None:
        name = faker.lexify("???")
    genre = Genre.objects.create(
        name=name,
        description=faker.sentence(),
        mass_office=random.choice(["Mass", "Office", "Mass, Office", "Old Hispanic"]),
    )
    return genre


def make_fake_user(is_indexer=True) -> get_user_model():
    """Generates a fake User object."""
    user = get_user_model().objects.create(
        full_name=f"{faker.first_name()} {faker.last_name()}",
        institution=faker.company(),
        city=faker.city(),
        country=faker.country(),
        is_indexer=is_indexer,
        email=f"{faker.lexify('????????')}@fakeemail.com",
    )
    return user


def make_fake_notation() -> Notation:
    """Generates a fake Notation object."""
    notation = Notation.objects.create(name=faker.sentence(nb_words=3))
    return notation


def make_fake_office() -> Office:
    """Generates a fake Office object."""
    office = Office.objects.create(
        name=faker.lexify(text="??"),
        description=faker.sentence(),
    )
    return office


def make_fake_provenance() -> Provenance:
    """Generates a fake Provenance object."""
    provenance = Provenance.objects.create(name=faker.sentence(nb_words=3))
    return provenance


def make_fake_rism_siglum() -> RismSiglum:
    """Generates a fake RismSiglum object."""
    rism_siglum = RismSiglum.objects.create(
        name=faker.sentence(nb_words=3),
        description=faker.sentence(),
    )
    return rism_siglum


def make_fake_segment(name=None) -> Segment:
    """Generates a fake Segment object."""
    if not name:
        name = faker.sentence()
    segment = Segment.objects.create(name=name)
    return segment


def make_fake_sequence(
    source=None, title=None, incipit=None, cantus_id=None
) -> Sequence:
    """Generates a fake Sequence object."""
    if source is None:
        source = make_fake_source(segment_name="Bower Sequence Database")
    if title is None:
        title = faker.sentence()
    if incipit is None:
        incipit = title[:INCIPIT_LENGTH]
    if cantus_id is None:
        cantus_id = make_random_string(6, "0123456789")
    sequence = Sequence.objects.create(
        title=title,
        siglum=make_random_string(6),
        incipit=incipit,
        # folio in the form of two digits and one letter
        folio=faker.bothify("##?"),
        s_sequence=make_random_string(2, "0123456789"),
        genre=make_fake_genre(),
        rubrics=faker.sentence(),
        analecta_hymnica=make_random_string(6, "0123456789:"),
        indexing_notes=faker.sentence(),
        date=make_random_string(6, "1234567890abcdefghijklmnopqrstuvwxyz/-*"),
        ah_volume=str(random.randint(0, 60)),
        source=source,
        cantus_id=cantus_id,
        image_link=faker.image_url(),
    )
    return sequence


def make_fake_source(
    published: bool = True,
    title: Optional[str] = None,
    segment_name: Optional[str] = None,
    segment: Optional[Segment] = None,
    siglum: Optional[str] = None,
    rism_siglum: Optional[RismSiglum] = None,
    description: Optional[str] = None,
    summary: Optional[str] = None,
    provenance: Optional[Provenance] = None,
    century: Optional[Century] = None,
    full_source: bool = True,
    indexing_notes: Optional[str] = None,
) -> Source:
    """Generates a fake Source object."""
    # The cursus_choices and source_status_choices lists in Source are lists of
    # tuples and we only need the first element of each tuple

    # if published...
    #     published already defaults to True
    if title is None:
        title = faker.sentence()
    if segment_name is None:
        segment_name = faker.sentence(nb_words=2)
    if segment is None:
        segment = make_fake_segment(name=segment_name)
    if siglum is None:
        siglum = make_random_string(6)
    if rism_siglum is None:
        rism_siglum = make_fake_rism_siglum()
    if description is None:
        description = faker.sentence()
    if summary is None:
        summary = faker.sentence()
    if provenance is None:
        provenance = make_fake_provenance()
    if century is None:
        century = make_fake_century()
    # if full_source...
    #     full_source already defaults to True
    if indexing_notes is None:
        indexing_notes = faker.sentence()

    cursus_choices = [x[0] for x in Source.cursus_choices]
    source_status_choices = [x[0] for x in Source.source_status_choices]

    source = Source.objects.create(
        published=published,
        title=title,
        segment=segment,
        siglum=siglum,
        rism_siglum=rism_siglum,
        description=description,
        summary=summary,
        provenance=provenance,
        # century: ManyToManyField, must be set below
        full_source=full_source,
        indexing_notes=indexing_notes,
        provenance_notes=faker.sentence(),
        date=faker.sentence(nb_words=3),
        cursus=random.choice(cursus_choices),
        source_status=random.choice(source_status_choices),
        complete_inventory=faker.boolean(),
        liturgical_occasions=faker.sentence(),
        selected_bibliography=faker.sentence(),
        image_link=faker.image_url(),
        indexing_date=faker.sentence(),
        json_info=None,
    )
    source.century.set([century])
    source.notation.set([make_fake_notation()])
    source.inventoried_by.set([make_fake_user()])
    source.full_text_entered_by.set([make_fake_user()])
    source.melodies_entered_by.set([make_fake_user()])
    source.proofreaders.set([make_fake_user()])
    source.other_editors.set([make_fake_user()])

    return source
