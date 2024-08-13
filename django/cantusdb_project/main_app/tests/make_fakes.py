"""Functions to make fake objects to be used for testing"""

import random
from faker import Faker

from main_app.models.century import Century
from main_app.models.chant import Chant
from main_app.models.feast import Feast
from main_app.models.genre import Genre
from main_app.models.institution import Institution
from main_app.models.notation import Notation
from main_app.models.service import Service
from main_app.models.project import Project
from main_app.models.provenance import Provenance
from main_app.models.segment import Segment
from main_app.models.sequence import Sequence
from main_app.models.source import Source
from django.contrib.auth import get_user_model

from typing import Optional, List

User = get_user_model()

# Max positive integer accepted by Django's positive integer field
MAX_SEQUENCE_NUMBER = 2147483647

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


def add_accents_to_string(s: str) -> str:
    """Replace some letters in a string
    with their accented versions.

    Args:
        s (str): A string

    Returns:
        str: The same string, but with vowels, c's and n's
            replaced with accented versions of the same letter
    """
    accented_string = (
        s.replace("a", "à")
        .replace("e", "é")
        .replace("i", "ï")
        .replace("o", "ô")
        .replace("u", "ū")
        .replace("c", "ç")
        .replace("n", "ñ")
        .replace("A", "À")
        .replace("E", "É")
        .replace("I", "Ï")
        .replace("O", "Ô")
        .replace("U", "Ū")
        .replace("C", "Ç")
        .replace("N", "Ñ")
    )
    return accented_string


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
    service=None,
    genre=None,
    position=None,
    c_sequence=None,
    cantus_id=None,
    image_link=None,
    feast=None,
    mode=None,
    manuscript_full_text_std_spelling=None,
    manuscript_full_text_std_proofread=None,
    manuscript_full_text=None,
    volpiano=None,
    manuscript_syllabized_full_text=None,
    next_chant=None,
    differentia=None,
    project=None,
    indexing_notes=None,
) -> Chant:
    """Generates a fake Chant object."""
    if source is None:
        source = make_fake_source(segment_name="CANTUS Database")
    if marginalia is None:
        marginalia = make_random_string(1)
    if folio is None:
        # two digits and one letter
        folio = faker.bothify("##?")
    if service is None:
        service = make_fake_service()
    if genre is None:
        genre = make_fake_genre()
    if position is None:
        position = make_random_string(1)
    if c_sequence is None:
        c_sequence = random.randint(1, MAX_SEQUENCE_NUMBER)
    if cantus_id is None:
        cantus_id = make_random_string(6, "0123456789")
    if image_link is None:
        image_link = faker.image_url()
    if feast is None:
        feast = make_fake_feast()
    if mode is None:
        mode = make_random_string(1, "0123456789*?")
    if manuscript_full_text_std_spelling is None:
        manuscript_full_text_std_spelling = faker.sentence()
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
    if project is None:
        project = make_fake_project()
    if indexing_notes is None:
        indexing_notes = faker.sentence()

    chant = Chant.objects.create(
        source=source,
        marginalia=marginalia,
        folio=folio,
        c_sequence=c_sequence,
        service=service,
        genre=genre,
        position=position,
        cantus_id=cantus_id,
        feast=feast,
        mode=mode,
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
        manuscript_full_text_std_proofread=manuscript_full_text_std_proofread,
        manuscript_full_text=manuscript_full_text,
        manuscript_full_text_proofread=faker.boolean(),
        volpiano=volpiano,
        volpiano_proofread=faker.boolean(),
        image_link=image_link,
        cao_concordances=make_random_string(12, "ABCDEFGHIJKLMNOPQRSTUVWXYZ  "),
        melody_id="m" + make_random_string(8, "0123456789."),
        manuscript_syllabized_full_text=manuscript_syllabized_full_text,
        indexing_notes=indexing_notes,
        json_info=None,
        next_chant=next_chant,
        project=project,
    )
    chant.refresh_from_db()  # several fields (e.g., incipit) are calculated automatically
    # upon chant save. By refreshing from db before returning, we ensure all the chant's fields
    # are up-to-date. For more information, refer to main_app/signals.py
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


def make_fake_user(is_indexer=True) -> User:
    """Generates a fake User object."""
    user = User.objects.create(
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


def make_fake_service() -> Service:
    """Generates a fake Service object."""
    service = Service.objects.create(
        name=faker.lexify(text="??"),
        description=faker.sentence(),
    )
    return service


def make_fake_provenance() -> Provenance:
    """Generates a fake Provenance object."""
    provenance = Provenance.objects.create(name=faker.sentence(nb_words=3))
    return provenance


def make_fake_segment(name: str = None, id: int = None) -> Segment:
    """Generates a fake Segment object."""
    if name is None:
        name = faker.sentence(nb_words=2)
    if id is None:
        segment = Segment.objects.create(name=name)
        return segment
    segment = Segment.objects.create(name=name, id=id)
    return segment


def make_fake_project(name: str = None, id: int = None) -> Project:
    if name is None:
        name = faker.sentence(nb_words=2)
    if id is None:
        project = Project.objects.create(name=name)
        return project
    project = Project.objects.create(name=name, id=id)
    return project


def make_fake_sequence(source=None, title=None, cantus_id=None) -> Sequence:
    """Generates a fake Sequence object."""
    if source is None:
        source = make_fake_source(segment_name="Bower Sequence Database")
    if title is None:
        title = faker.sentence()
    if cantus_id is None:
        cantus_id = make_random_string(6, "0123456789")
    sequence = Sequence.objects.create(
        title=title,
        siglum=make_random_string(6),
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
    sequence.refresh_from_db()  # several fields (e.g., incipit) are calculated automatically
    # upon sequence save. By refreshing from db before returning, we ensure all the sequence's fields
    # are up-to-date. For more information, refer to main_app/signals.py
    return sequence


def make_fake_institution(
    name: Optional[str] = None,
    siglum: Optional[str] = None,
    city: Optional[str] = None,
    region: Optional[str] = None,
    country: Optional[str] = None,
) -> Institution:
    name = name if name else faker.sentence()
    siglum = siglum if siglum else faker.sentence(nb_words=1)
    city = city if city else faker.city()
    region = region if region else faker.country()
    country = country if country else faker.country()

    inst = Institution.objects.create(
        name=name, siglum=siglum, city=city, region=region, country=country
    )
    inst.save()

    return inst


def make_fake_source(
    published: bool = True,
    shelfmark: Optional[str] = None,
    segment_name: Optional[str] = None,
    segment: Optional[Segment] = None,
    holding_institution: Optional[Institution] = None,
    description: Optional[str] = None,
    summary: Optional[str] = None,
    provenance: Optional[Provenance] = None,
    century: Optional[Century] = None,
    full_source: Optional[bool] = True,
    indexing_notes: Optional[str] = None,
) -> Source:
    """Generates a fake Source object."""
    # The cursus_choices and source_status_choices lists in Source are lists of
    # tuples and we only need the first element of each tuple

    # if published...
    #     published already defaults to True
    if shelfmark is None:
        shelfmark = faker.sentence()
    if segment_name is None:
        segment_name = faker.sentence(nb_words=2)
    if segment is None:
        segment = make_fake_segment(name=segment_name)
    if holding_institution is None:
        holding_institution = make_fake_institution()
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
        shelfmark=shelfmark,
        segment=segment,
        holding_institution=holding_institution,
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
