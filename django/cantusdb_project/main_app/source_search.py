"""Construction and maintenance of the Source full-text search document."""

from collections.abc import Iterable
from dataclasses import dataclass

from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db import models
from django.db.models import Func, Value

from main_app.models import Source


@dataclass(frozen=True)
class SourceSearchField:
    """One public value included in a Source's search document.

    ``relation`` names a relation from ``Source``; ``multiple`` distinguishes
    many-to-many/reverse relations from select-related foreign keys.
    ``display_value`` indexes a model choice's human-readable label instead of
    its stored value. ``contributor`` and ``m2m_relation`` let signal wiring
    derive the relationship sets from this same declaration.
    """

    attribute: str
    relation: str | None = None
    multiple: bool = False
    display_value: bool = False
    contributor: bool = False
    m2m_relation: bool = False


# This is the complete, reviewable public search contract. Do not add a field
# elsewhere in this module: changing the indexed surface starts here.
SOURCE_SEARCH_FIELDS = (
    # Source metadata
    SourceSearchField("title"),
    SourceSearchField("siglum"),
    SourceSearchField("shelfmark"),
    SourceSearchField("name"),
    SourceSearchField("provenance_notes"),
    SourceSearchField("date"),
    SourceSearchField("cursus"),
    SourceSearchField("source_completeness", display_value=True),
    SourceSearchField("production_method", display_value=True),
    SourceSearchField("source_status"),
    SourceSearchField("summary"),
    SourceSearchField("liturgical_occasions"),
    SourceSearchField("description"),
    SourceSearchField("selected_bibliography"),
    SourceSearchField("indexing_notes"),
    SourceSearchField("indexing_date"),
    SourceSearchField("fragmentarium_id"),
    SourceSearchField("dact_id"),
    # Holding institution and provenance
    SourceSearchField("name", relation="holding_institution"),
    SourceSearchField("siglum", relation="holding_institution"),
    SourceSearchField("city", relation="holding_institution"),
    SourceSearchField("region", relation="holding_institution"),
    SourceSearchField("country", relation="holding_institution"),
    SourceSearchField("alternate_names", relation="holding_institution"),
    SourceSearchField("former_sigla", relation="holding_institution"),
    SourceSearchField("migrated_identifier", relation="holding_institution"),
    SourceSearchField("name", relation="provenance"),
    SourceSearchField("name", relation="segment"),
    # Source classifications and identifiers
    SourceSearchField("identifier", relation="identifiers", multiple=True),
    SourceSearchField("note", relation="identifiers", multiple=True),
    SourceSearchField(
        "type", relation="identifiers", multiple=True, display_value=True
    ),
    SourceSearchField("name", relation="century", multiple=True, m2m_relation=True),
    SourceSearchField("name", relation="notation", multiple=True, m2m_relation=True),
    SourceSearchField("name", relation="segment_m2m", multiple=True, m2m_relation=True),
    # Public contributor credits
    SourceSearchField(
        "full_name",
        relation="inventoried_by",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="full_text_entered_by",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="melodies_entered_by",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="description_entered_by",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="proofreaders",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="other_editors",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
    SourceSearchField(
        "full_name",
        relation="source_data_contributed_by",
        multiple=True,
        contributor=True,
        m2m_relation=True,
    ),
)

CONTRIBUTOR_RELATIONS = tuple(
    field.relation for field in SOURCE_SEARCH_FIELDS if field.contributor
)
SINGLE_VALUE_RELATIONS = tuple(
    dict.fromkeys(
        field.relation
        for field in SOURCE_SEARCH_FIELDS
        if field.relation and not field.multiple
    )
)
MULTIPLE_VALUE_RELATIONS = tuple(
    dict.fromkeys(
        field.relation
        for field in SOURCE_SEARCH_FIELDS
        if field.relation and field.multiple
    )
)
M2M_SEARCH_RELATIONS = tuple(
    field.relation for field in SOURCE_SEARCH_FIELDS if field.m2m_relation
)


def _field_values(source: Source, field: SourceSearchField) -> list[str]:
    """Read one declared field, including zero or more related instances."""
    if field.relation is None:
        instances = (source,)
    else:
        relation = getattr(source, field.relation)
        instances = (
            relation.all() if field.multiple else ((relation,) if relation else ())
        )

    values = []
    for instance in instances:
        if field.display_value:
            value = getattr(instance, f"get_{field.attribute}_display")()
        else:
            value = getattr(instance, field.attribute)
        if value:
            values.append(str(value))
    return values


def source_search_document(source: Source) -> str:
    """Return the public, human-searchable metadata for one source.

    URLs, audit fields, private institution notes, and permission-only
    relationships are deliberately omitted. The vector is a search aid, not a
    serialisation of the entire database row.
    """
    return " ".join(
        value
        for field in SOURCE_SEARCH_FIELDS
        for value in _field_values(source, field)
    )


def _search_vector(document: str) -> SearchVector:
    """Build an accent-insensitive vector with no English-language stemming."""
    unaccented_document = Func(
        Value(document), function="unaccent", output_field=models.TextField()
    )
    return SearchVector(unaccented_document, config="simple")


def source_search_query(query: str) -> SearchQuery:
    """Parse the public ``general`` parameter using web-search syntax."""
    unaccented_query = Func(
        Value(query), function="unaccent", output_field=models.TextField()
    )
    return SearchQuery(unaccented_query, config="simple", search_type="websearch")


def source_queryset_for_search() -> models.QuerySet[Source]:
    """Fetch every relation needed to build a Source search document."""
    return Source.objects.select_related(*SINGLE_VALUE_RELATIONS).prefetch_related(
        *MULTIPLE_VALUE_RELATIONS
    )


def update_source_search_vector(source_id: int) -> None:
    """Rebuild one source's stored vector, if the source still exists."""
    source = source_queryset_for_search().filter(pk=source_id).first()
    if source is not None:
        Source.objects.filter(pk=source.pk).update(
            search_vector=_search_vector(source_search_document(source))
        )


def rebuild_source_search_vectors(source_ids: Iterable[int] | None = None) -> int:
    """Rebuild vectors and return the number of source rows processed."""
    queryset = source_queryset_for_search()
    if source_ids is not None:
        queryset = queryset.filter(pk__in=set(source_ids))

    count = 0
    for source in queryset.iterator(chunk_size=100):
        Source.objects.filter(pk=source.pk).update(
            search_vector=_search_vector(source_search_document(source))
        )
        count += 1
    return count
