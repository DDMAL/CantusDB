"""Functions to make fake objects to be used for testing"""

import random
from typing import Optional, List, Any
from faker import Faker  # type: ignore[import-untyped]

from django.contrib.auth import get_user_model
from django.db.models import Max

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
from users.models import User as UserAnnotation


User = get_user_model()

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
    if words < 1:
        raise ValueError("words must be >= 1")
    if syllables_per_word < 1:
        raise ValueError("syllables_per_word must be >= 1")
    if neumes_per_syllable < 1:
        raise ValueError("neumes_per_syllable must be >= 1")
    if notes_per_neume < 1:
        raise ValueError("notes_per_neume must be >= 1")

    words_: List[str] = []
    for _ in range(words):
        syllables: List[str] = []
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


def make_fake_century(**kwargs: Any) -> Century:
    """Generates a fake Century object."""
    if "name" not in kwargs:
        kwargs["name"] = faker.sentence(nb_words=3)
    century = Century.objects.create(**kwargs)
    return century


def make_fake_chant(**kwargs: Any) -> Chant:
    """
    Generates a fake Chant object. Kwargs can be used to specify the value of fields.
    The `chant_id` field can be used to specify the id of the chant.

    The following fields will, if not specified, be given a fake value:
    - source (defaults to a source in the 'CANTUS Database' segment)
    - folio
    - c_sequence
    - manuscript_full_text_std_spelling
    - marginalia
    - service
    - genre
    - position
    - cantus_id
    - image_link
    - feast
    - mode
    - differentia
    - project
    - volpiano
    - finalis
    - extra
    - addendum
    - cao_concordances
    - melody_id
    - chant_range
    - manuscript_full_text, indexing_notes, manuscript_syllabized_full_text
    - manuscript_full_text_proofread, volpiano_proofread, manuscript_full_text_std_proofread, other_fields_proofread (default to False)
    """
    # Handle `source`, `folio`, and `c_sequence` fields,
    # which cannot be set to None
    if kwargs.get("source") is None:
        kwargs["source"] = make_fake_source(segment_name="CANTUS Database")
    if kwargs.get("folio") is None:
        kwargs["folio"] = faker.bothify("##?")
    if kwargs.get("c_sequence") is None:
        # When c_sequence is not specified, iterate + 1 on the maximum c_sequence
        # of the chants with the same source and folio
        current_max_c_sequence = (
            kwargs["source"]
            .chant_set.filter(folio=kwargs["folio"])
            .aggregate(Max("c_sequence"))["c_sequence__max"]
        )
        kwargs["c_sequence"] = (
            current_max_c_sequence + 1 if current_max_c_sequence else 1
        )

    kwargs["marginalia"] = kwargs.get("marginalia", make_random_string(1))
    kwargs["service"] = kwargs.get("service", make_fake_service())
    kwargs["genre"] = kwargs.get("genre", make_fake_genre())
    kwargs["position"] = kwargs.get("position", make_random_string(1))
    kwargs["cantus_id"] = kwargs.get("cantus_id", make_random_string(6, "0123456789"))
    kwargs["image_link"] = kwargs.get("image_link", faker.image_url())
    kwargs["feast"] = kwargs.get("feast", make_fake_feast())
    kwargs["mode"] = kwargs.get("mode", make_random_string(1, "0123456789*?"))
    kwargs["differentia"] = kwargs.get("differentia", make_random_string(2))
    kwargs["project"] = kwargs.get("project", make_fake_project())
    kwargs["volpiano"] = kwargs.get("volpiano", make_fake_volpiano())
    kwargs["finalis"] = kwargs.get("finalis", make_random_string(1, "abcdefg"))
    kwargs["extra"] = kwargs.get("extra", make_random_string(3, "0123456789"))
    kwargs["addendum"] = kwargs.get(
        "addendum", make_random_string(3, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    )
    kwargs["cao_concordances"] = kwargs.get(
        "cao_concordances", make_random_string(12, "ABCDEFGHIJKLMNOPQRSTUVWXYZ  ")
    )
    kwargs["melody_id"] = kwargs.get(
        "melody_id", "m" + make_random_string(8, "0123456789.")
    )
    kwargs["chant_range"] = kwargs.get(
        "chant_range",
        make_fake_volpiano(
            words=1, syllables_per_word=1, neumes_per_syllable=1, notes_per_neume=1
        ).replace(
            "---", "-"
        ),  # chant_range is of the form "1-x-y-4", x, y are volpiano notes
    )

    # The following fields, when not specified, are generated with a random sentence
    for field in [
        "manuscript_full_text_std_spelling",
        "manuscript_full_text",
        "indexing_notes",
        "manuscript_syllabized_full_text",
    ]:
        kwargs[field] = kwargs.get(field, faker.sentence())

    # The following fields, when not specified, default to False
    for field in [
        "manuscript_full_text_proofread",
        "volpiano_proofread",
        "manuscript_full_text_std_proofread",
        "other_fields_proofread",
    ]:
        kwargs[field] = kwargs.get(field, False)

    # Remove `chant_id` from kwargs. If specified, it will be used to set the id of the chant.
    chant_id = kwargs.pop("chant_id", None)

    chant = Chant(**kwargs)
    if chant_id is not None:
        chant.id = chant_id
    chant.save()
    chant.refresh_from_db()  # several fields (e.g., incipit) are calculated automatically
    # upon chant save. By refreshing from db before returning, we ensure all the chant's fields
    # are up-to-date. For more information, refer to main_app/signals.py
    return chant


def make_fake_feast(**kwargs: Any) -> Feast:
    """Generates a fake Feast object."""
    for field in ["name", "description", "notes"]:
        kwargs[field] = kwargs.get(field, faker.sentence())
    kwargs["feast_code"] = kwargs.get("feast_code", make_random_string(8, "0123456789"))
    kwargs["month"] = kwargs.get("month", random.randint(1, 12))
    kwargs["day"] = kwargs.get("day", random.randint(1, 31))
    feast = Feast.objects.create(**kwargs)
    return feast


def make_fake_genre(
    name: Optional[str] = None,
    description: Optional[str] = None,
    mass_office: Optional[str] = None,
) -> Genre:
    """Generates a fake Genre object."""
    if name is None:
        name = faker.lexify("???")
    if description is None:
        description = faker.sentence()
    if mass_office is None:
        mass_office = random.choice(["Mass", "Office", "Mass, Office", "Old Hispanic"])
    genre = Genre.objects.create(
        name=name,
        description=description,
        mass_office=mass_office,
    )
    return genre


def make_fake_user(is_indexer: bool = True) -> UserAnnotation:
    """Generates a fake User object."""
    user: UserAnnotation = User.objects.create(
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


def make_fake_service(
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Service:
    """Generates a fake Service object."""
    if name is None:
        name = faker.lexify("???")
    if description is None:
        description = faker.sentence()
    service = Service.objects.create(
        name=name,
        description=description,
    )
    return service


def make_fake_provenance() -> Provenance:
    """Generates a fake Provenance object."""
    provenance = Provenance.objects.create(name=faker.sentence(nb_words=3))
    return provenance


def make_fake_segment(name: Optional[str] = None, id: Optional[int] = None) -> Segment:
    """Generates a fake Segment object."""
    if name is None:
        name = faker.sentence(nb_words=2)
    if id is None:
        segment = Segment.objects.create(name=name)
        return segment
    segment = Segment.objects.create(name=name, id=id)
    return segment


def make_fake_project(name: Optional[str] = None, id: Optional[int] = None) -> Project:
    if name is None:
        name = faker.sentence(nb_words=2)
    if id is None:
        project = Project.objects.create(name=name)
        return project
    project = Project.objects.create(name=name, id=id)
    return project


def make_fake_sequence(
    sequence_id: Optional[int] = None,
    source: Optional[Source] = None,
    title: Optional[str] = None,
    cantus_id: Optional[str] = None,
    siglum: Optional[str] = None,
    folio: Optional[str] = None,
) -> Sequence:
    """Generates a fake Sequence object."""
    if source is None:
        source = make_fake_source(segment_name="Bower Sequence Database")
    if title is None:
        title = faker.sentence()
    if cantus_id is None:
        cantus_id = make_random_string(6, "0123456789")
    if siglum is None:
        siglum = make_random_string(6)
    if folio is None:
        # two digits and one letter
        folio = faker.bothify("##?")
    sequence = Sequence(
        title=title,
        siglum=siglum,
        # folio in the form of two digits and one letter
        folio=folio,
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
    if sequence_id is not None:
        sequence.id = sequence_id
    sequence.save()
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
    is_private_collector: bool = False,
) -> Institution:
    """
    Generate a fake institution.

    Note that one of the `siglum` and `is_private_collector` arguments
    must be specified. If a `siglum` is specified, `is_private_collector`
    must be empty (in which case it defaults to False) or set to False.

    If `is_private_collector` is set to False, and no `siglum` is specified,
    a random siglum will be generated.
    """
    assert siglum is None or not is_private_collector

    if not is_private_collector:
        siglum = siglum if siglum else make_random_string(6)

    name = name if name else faker.sentence()
    city = city if city else faker.city()
    region = region if region else faker.country()
    country = country if country else faker.country()

    inst = Institution.objects.create(
        name=name,
        siglum=siglum,
        city=city,
        region=region,
        country=country,
        is_private_collector=is_private_collector,
    )
    inst.save()

    return inst


def make_fake_source(**kwargs: Any) -> Source:
    """
    Generates a fake Source object. Kwargs can be used to specify the value of fields.

    The following fields will, if not specified, be given a fake value:
    - published (defaults to True)
    - shelfmark
    - segment (if segment_name is specified, a segment will be generated with that name)
    - holding_institution
    - provenance
    - full_source (defaults to True)
    - source_completeness (defaults to FULL_SOURCE)
    - cursus
    - source_status
    - image_link
    - date
    - indexing_notes
    - description
    - summary
    - liturgical_occasions
    - selected_bibliography
    - indexing_date
    - provenance_notes
    - century
    - notation
    - all fields related to user involvement (inventoried_by, full_text_entered_by, etc.)
    """
    # Handle `shelfmark` and `published` fields, which cannot be set to None
    if kwargs.get("shelfmark") is None:
        kwargs["shelfmark"] = faker.sentence()
    if kwargs.get("published") is None:
        kwargs["published"] = True

    if "segment" not in kwargs:
        if "segment_name" in kwargs:
            kwargs["segment"] = [make_fake_segment(name=kwargs["segment_name"])]
            kwargs.pop("segment_name")
        else:
            kwargs["segment"] = [make_fake_segment()]
    segments = kwargs.pop("segment")
    kwargs["holding_institution"] = kwargs.get(
        "holding_institution", make_fake_institution()
    )
    kwargs["provenance"] = kwargs.get("provenance", make_fake_provenance())
    kwargs["full_source"] = kwargs.get("full_source", True)
    kwargs["source_completeness"] = kwargs.get(
        "source_completeness", Source.SourceCompletenessChoices.FULL_SOURCE
    )
    cursus_choices = [x[0] for x in Source.cursus_choices]
    source_status_choices = [x[0] for x in Source.source_status_choices]
    kwargs["cursus"] = kwargs.get("cursus", random.choice(cursus_choices))
    kwargs["source_status"] = kwargs.get(
        "source_status", random.choice(source_status_choices)
    )
    kwargs["image_link"] = kwargs.get("image_link", faker.image_url())
    kwargs["date"] = kwargs.get("date", faker.sentence(nb_words=3))

    # For the following text fields: if not specified, generate a fake sentence
    for field in [
        "indexing_notes",
        "description",
        "summary",
        "liturgical_occasions",
        "selected_bibliography",
        "indexing_date",
        "provenance_notes",
    ]:
        kwargs[field] = kwargs.get(field, faker.sentence())

    # Remove the "century" key from kwargs. As a many-to-many field,
    # the century field is handled after instance creation.
    century = kwargs.pop("century", make_fake_century())

    source = Source.objects.create(**kwargs)

    source.century.set([century])
    source.notation.set([make_fake_notation()])
    source.inventoried_by.set([make_fake_user()])
    source.full_text_entered_by.set([make_fake_user()])
    source.description_entered_by.set([make_fake_user()])
    source.melodies_entered_by.set([make_fake_user()])
    source.proofreaders.set([make_fake_user()])
    source.other_editors.set([make_fake_user()])
    source.segment_m2m.set(segments)

    return source


def get_random_search_term(target: str) -> str:
    """Helper function for generating a random slice of a string.

    Args:
        target (str): The content of the field to search.

    Returns:
        str: A random slice of `target`
    """
    if len(target) <= 2:
        search_term = target
    else:
        slice_start = random.randint(0, len(target) - 2)
        slice_end = random.randint(slice_start + 2, len(target))
        search_term = target[slice_start:slice_end]
    return search_term
