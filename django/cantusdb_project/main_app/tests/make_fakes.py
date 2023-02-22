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

# Max values for two types of Char fields
LONG_CHAR_FIELD_MAX = 255
SHORT_CHAR_FIELD_MAX = 63

# Max positive integer accepted by Django's positive integer field
MAX_SEQUENCE_NUMBER = 2147483647

# The smallest full text would have 10 chars at least
MIN_NUMBER_TEXT_CHARS = 10
# Picked 10000 for performance reasons, much bigger than that got slow
MAX_NUMBER_TEXT_CHARS = 10000

# The incipit will be up to 100 characters of the full text
INCIPIT_LENGTH = 100

# Create a Faker instance with locale set to Latin
faker = Faker("la")


def make_fake_text(max_size: int, min_size: int = 5) -> str:
    """Generates fake text using with the Faker module.

    Size will be a random size between ``max_size`` and ``min_size``.

    Since it uses the Faker module it will ouput a random text in the language
    of the locale set by Faker.

    Args:
        max_size (int): Maximum size of the text.
        min_size (int, optional): Minimum size of the string. 
        Defaults to 5 because `faker.text` can only generate at least 5 characters.

    Returns:
        str: The fake text.
    """
    random_str = faker.text(max_nb_chars=random.randint(min_size, max_size))
    return random_str


def make_fake_century() -> Century:
    """Generates a fake Century object."""
    century = Century.objects.create(name=make_fake_text(LONG_CHAR_FIELD_MAX))
    return century


def make_fake_chant(source=None,
    folio=None,
    office=None,
    genre=None,
    position=None,
    c_sequence=None,
    cantus_id=None,
    feast=None,
    manuscript_full_text_std_spelling=None,
    manuscript_full_text_std_proofread=None,
    manuscript_full_text=None,
    volpiano=None,
    manuscript_syllabized_full_text=None,
    next_chant=None,
) -> Chant:
    """Generates a fake Chant object."""
    if source is None:
        source = make_fake_source(segment_name="CANTUS Database")
    if folio is None:
        # two digits and one letter
        folio = faker.bothify("##?")
    if office is None:
        office = make_fake_office()
    if genre is None:
        genre = make_fake_genre()
    if position is None:
        position = make_fake_text(SHORT_CHAR_FIELD_MAX)
    if c_sequence is None:
        c_sequence = random.randint(1, MAX_SEQUENCE_NUMBER)
    if cantus_id is None:
        cantus_id = faker.numerify("######")
    if feast is None:
        feast = make_fake_feast()
    if manuscript_full_text_std_spelling is None:
        manuscript_full_text_std_spelling = make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        )
    if manuscript_full_text_std_proofread is None:
        manuscript_full_text_std_proofread = False
    if manuscript_full_text is None:
        manuscript_full_text = manuscript_full_text_std_spelling
    if volpiano is None:
        volpiano = make_fake_text(20)
    if manuscript_syllabized_full_text is None:
        manuscript_syllabized_full_text = make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        )
        

    chant = Chant.objects.create(
        source=source,
        marginalia=make_fake_text(SHORT_CHAR_FIELD_MAX),
        folio=folio,
        c_sequence=c_sequence,
        office=office,
        genre=genre,
        position=position,
        # cantus_id in the form of six digits
        cantus_id=cantus_id,
        feast=feast,
        mode=make_fake_text(SHORT_CHAR_FIELD_MAX),
        differentia=make_fake_text(SHORT_CHAR_FIELD_MAX),
        finalis=make_fake_text(SHORT_CHAR_FIELD_MAX),
        extra=make_fake_text(SHORT_CHAR_FIELD_MAX),
        chant_range=make_fake_text(LONG_CHAR_FIELD_MAX),
        addendum=make_fake_text(LONG_CHAR_FIELD_MAX),
        manuscript_full_text_std_spelling=manuscript_full_text_std_spelling,
        incipit=manuscript_full_text_std_spelling[0:INCIPIT_LENGTH],
        manuscript_full_text_std_proofread=manuscript_full_text_std_proofread,
        manuscript_full_text=manuscript_full_text,
        manuscript_full_text_proofread=faker.boolean(),
        volpiano=volpiano,
        volpiano_proofread=faker.boolean(),
        image_link=faker.image_url(),
        cao_concordances=make_fake_text(SHORT_CHAR_FIELD_MAX),
        melody_id=make_fake_text(SHORT_CHAR_FIELD_MAX),
        manuscript_syllabized_full_text=manuscript_syllabized_full_text,
        indexing_notes=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        json_info=None,
        next_chant=next_chant,
    )
    return chant


def make_fake_feast() -> Feast:
    """Generates a fake Feast object."""
    feast = Feast.objects.create(
        name=faker.sentence(),
        description=faker.sentence(),
        # feast_code in the form of eight digits
        feast_code=faker.numerify("########"),
        notes=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
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
        mass_office=make_fake_text(SHORT_CHAR_FIELD_MAX),
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
    notation = Notation.objects.create(name=make_fake_text(SHORT_CHAR_FIELD_MAX))
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
    provenance = Provenance.objects.create(name=make_fake_text(SHORT_CHAR_FIELD_MAX))
    return provenance


def make_fake_rism_siglum() -> RismSiglum:
    """Generates a fake RismSiglum object."""
    rism_siglum = RismSiglum.objects.create(
        name=make_fake_text(SHORT_CHAR_FIELD_MAX),
        description=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
    )
    return rism_siglum


def make_fake_segment(name=None) -> Segment:
    """Generates a fake Segment object."""
    if not name:
        name = make_fake_text(SHORT_CHAR_FIELD_MAX)
    segment = Segment.objects.create(name=name)
    return segment


def make_fake_sequence(source=None, title=None, incipit=None, cantus_id=None) -> Sequence:
    """Generates a fake Sequence object."""
    if source is None:
        source = make_fake_source(segment_name="Bower Sequence Database")
    if title is None:
        title = make_fake_text(LONG_CHAR_FIELD_MAX)
    if incipit is None:
        incipit = make_fake_text(LONG_CHAR_FIELD_MAX)
    if cantus_id is None:
        cantus_id = faker.numerify("######")
    sequence = Sequence.objects.create(
        title=title,
        siglum=make_fake_text(LONG_CHAR_FIELD_MAX),
        incipit=incipit,
        # folio in the form of two digits and one letter
        folio=faker.bothify("##?"),
        s_sequence=make_fake_text(LONG_CHAR_FIELD_MAX),
        genre=make_fake_genre(),
        rubrics=make_fake_text(LONG_CHAR_FIELD_MAX),
        analecta_hymnica=make_fake_text(LONG_CHAR_FIELD_MAX),
        indexing_notes=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        date=make_fake_text(LONG_CHAR_FIELD_MAX),
        ah_volume=make_fake_text(LONG_CHAR_FIELD_MAX),
        source=source,
        # cantus_id in the form of six digits
        cantus_id=cantus_id,
        image_link=faker.image_url(),
    )
    return sequence


def make_fake_source(published=None, title=None, segment=None, segment_name=None, siglum=None, description=None, summary=None, provenance=None, full_source=None, rism_siglum=None, indexing_notes=None) -> Source:
    """Generates a fake Source object."""
    # The cursus_choices and source_status_choices lists in Source are lists of
    # tuples and we only need the first element of each tuple

    if title is None:
        title = faker.sentence()
    if siglum is None:
        siglum = make_fake_text(SHORT_CHAR_FIELD_MAX)
    if description is None:
        description = make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        )
    if published is None:
        published = True
    if segment is None:
        segment = make_fake_segment(name=segment_name)
    if rism_siglum is None:
        rism_siglum = make_fake_rism_siglum()
    if summary is None:
        summary = make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        )

    cursus_choices = [x[0] for x in Source.cursus_choices]
    source_status_choices = [x[0] for x in Source.source_status_choices]

    source = Source.objects.create(
        published=published,
        title=title,
        siglum=siglum,
        rism_siglum=rism_siglum,
        provenance=provenance,
        provenance_notes=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        full_source=full_source,
        date=make_fake_text(SHORT_CHAR_FIELD_MAX),
        cursus=random.choice(cursus_choices),
        segment=segment,
        source_status=random.choice(source_status_choices),
        complete_inventory=faker.boolean(),
        summary=summary,
        liturgical_occasions=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        description=description,
        selected_bibliography=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        image_link=faker.image_url(),
        indexing_notes=indexing_notes,
        indexing_date=make_fake_text(
            max_size=MAX_NUMBER_TEXT_CHARS, min_size=MIN_NUMBER_TEXT_CHARS
        ),
        json_info=None,
    )
    source.century.set([make_fake_century()])
    source.notation.set([make_fake_notation()])
    source.inventoried_by.set([make_fake_user()])
    source.full_text_entered_by.set([make_fake_user()])
    source.melodies_entered_by.set([make_fake_user()])
    source.proofreaders.set([make_fake_user()])
    source.other_editors.set([make_fake_user()])

    return source
