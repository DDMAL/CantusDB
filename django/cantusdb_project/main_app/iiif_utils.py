"""
Utilities for parsing IIIF manifests and generating folio-to-image mappings.

Supports both IIIF Presentation API 2.x and 3.0 manifests.
"""

import csv
import io
import re
from dataclasses import dataclass

import requests


@dataclass
class CanvasInfo:
    """Represents a single canvas/page extracted from a IIIF manifest."""

    label: str
    image_url: str | None
    canvas_index: int


def fetch_manifest(manifest_url: str, timeout: int = 30) -> dict:
    """
    Fetch and parse a IIIF manifest JSON from the given URL.

    Args:
        manifest_url: URL to the IIIF manifest JSON.
        timeout: Request timeout in seconds.

    Returns:
        Parsed manifest as a dictionary.

    Raises:
        requests.RequestException: If the fetch fails.
        ValueError: If the response is not valid JSON.
    """
    response = requests.get(manifest_url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _get_label_text(label: object) -> str:
    """
    Extract plain text from a IIIF label, handling both API 2.x and 3.0 formats.

    API 2.x: label is a string or a list of strings.
    API 3.0: label is a dict like {"en": ["Folio 1r"]}.
    """
    if isinstance(label, str):
        return label
    if isinstance(label, list):
        # List of strings (API 2.x) or list of dicts
        for item in label:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                return item.get("@value", str(item))
        return str(label[0]) if label else ""
    if isinstance(label, dict):
        # API 3.0: {"en": ["Folio 1r"], "none": ["f. 1r"]}
        for values in label.values():
            if isinstance(values, list) and values:
                return str(values[0])
        return ""
    return str(label)


def _extract_image_url_v2(canvas: dict) -> str | None:
    """Extract the best image URL from a IIIF 2.x canvas."""
    images = canvas.get("images", [])
    if not images:
        return None
    resource = images[0].get("resource", {})
    # Try to get the IIIF Image API service URL
    service = resource.get("service", {})
    if isinstance(service, list):
        service = service[0] if service else {}
    service_id = service.get("@id", "")
    if service_id:
        # Construct a full image URL from the service
        return f"{service_id.rstrip('/')}/full/max/0/default.jpg"
    # Fall back to the resource @id (direct image URL)
    return resource.get("@id") or None


def _extract_image_url_v3(canvas: dict) -> str | None:
    """Extract the best image URL from a IIIF 3.0 canvas."""
    items = canvas.get("items", [])
    if not items:
        return None
    # Navigate: canvas -> AnnotationPage -> Annotation -> body
    annotation_page = items[0]
    annotations = annotation_page.get("items", [])
    if not annotations:
        return None
    body = annotations[0].get("body", {})
    # Try service first
    services = body.get("service", [])
    if isinstance(services, dict):
        services = [services]
    for service in services:
        service_id = service.get("id", service.get("@id", ""))
        if service_id:
            return f"{service_id.rstrip('/')}/full/max/0/default.jpg"
    # Fall back to body id
    return body.get("id") or None


def extract_canvases(manifest: dict) -> list[CanvasInfo]:
    """
    Extract canvas information from a IIIF manifest.

    Supports both Presentation API 2.x and 3.0.

    Args:
        manifest: Parsed IIIF manifest dictionary.

    Returns:
        List of CanvasInfo objects, one per canvas/page.
    """
    canvases = []

    # Detect API version
    context = manifest.get("@context", "")
    is_v3 = "iiif.io/api/presentation/3" in str(context)

    if is_v3:
        canvas_list = manifest.get("items", [])
        for i, canvas in enumerate(canvas_list):
            label = _get_label_text(canvas.get("label", ""))
            image_url = _extract_image_url_v3(canvas)
            canvases.append(
                CanvasInfo(label=label, image_url=image_url, canvas_index=i)
            )
    else:
        # API 2.x
        sequences = manifest.get("sequences", [])
        if not sequences:
            return canvases
        canvas_list = sequences[0].get("canvases", [])
        for i, canvas in enumerate(canvas_list):
            label = _get_label_text(canvas.get("label", ""))
            image_url = _extract_image_url_v2(canvas)
            canvases.append(
                CanvasInfo(label=label, image_url=image_url, canvas_index=i)
            )

    return canvases


# Regex patterns for extracting folio identifiers from canvas labels.
# Matches patterns like "f. 1r", "fol. 23v", "folio 123r", "1r", "001v",
# "p. 1", "page 10", etc. Anchored to start of the normalized string
# to avoid false positives (e.g. "Detail 2r" should NOT match "002r").
FOLIO_PATTERN = re.compile(
    r"""
    ^                            # Anchor to start of normalized string
    (?:f(?:ol(?:io)?)?\.?\s*)?   # Optional folio prefix
    (\d{1,4})                    # Page/folio number
    \s*
    ([rv](?:ecto|erso)?)?        # Optional recto/verso suffix
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize_folio(folio_str: str) -> str:
    """
    Normalize a folio string for comparison.

    Strips whitespace, lowercases, removes common prefixes and brackets.
    """
    s = folio_str.strip().lower()
    # Strip leading/trailing brackets
    s = s.strip("[](){}")
    # Remove common prefixes
    for prefix in ["fol.", "fol ", "folio ", "f.", "f "]:
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    return s


def _extract_folio_components(folio_str: str) -> tuple[str, str] | None:
    """
    Extract number and recto/verso suffix from a folio string.

    Returns (number, suffix) where suffix is 'r', 'v', or ''.
    The number is stripped of leading zeros for consistent comparison.
    Returns None if no folio pattern is found.
    """
    normalized = _normalize_folio(folio_str)
    match = FOLIO_PATTERN.search(normalized)
    if match:
        number = match.group(1).lstrip("0") or "0"
        suffix = (match.group(2) or "")[0:1].lower()  # 'r', 'v', or ''
        return (number, suffix)
    return None


def _build_folio_lookups(
    source_folios: list[str],
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """
    Build lookup dicts from source folios for efficient matching.

    Returns:
        (normalized_to_original, components_to_original)
    """
    normalized_to_original: dict[str, str] = {}
    components_to_original: dict[tuple[str, str], str] = {}
    for folio in source_folios:
        normalized_to_original[_normalize_folio(folio)] = folio
        components = _extract_folio_components(folio)
        if components:
            components_to_original[components] = folio
    return normalized_to_original, components_to_original


def match_canvas_to_folio(
    canvas_label: str,
    source_folios: list[str],
    *,
    folio_lookups: tuple[dict[str, str], dict[tuple[str, str], str]] | None = None,
) -> str | None:
    """
    Attempt to match a canvas label to a folio from the source.

    Uses heuristic matching:
    1. Exact match (case-insensitive, after normalization)
    2. Component-based match (number + recto/verso)

    Args:
        canvas_label: The label of the IIIF canvas.
        source_folios: List of folio strings from the source.
        folio_lookups: Optional pre-built lookup dicts from _build_folio_lookups.
            When calling in a loop, pass this to avoid rebuilding on every call.

    Returns:
        The matching folio string, or None if no match is found.
    """
    if not canvas_label or not source_folios:
        return None

    if folio_lookups is not None:
        normalized_to_original, components_to_original = folio_lookups
    else:
        normalized_to_original, components_to_original = _build_folio_lookups(
            source_folios
        )

    # Try exact normalized match
    canvas_normalized = _normalize_folio(canvas_label)
    if canvas_normalized in normalized_to_original:
        return normalized_to_original[canvas_normalized]

    # Try component-based match
    canvas_components = _extract_folio_components(canvas_label)
    if canvas_components and canvas_components in components_to_original:
        return components_to_original[canvas_components]

    return None


def generate_folio_image_mapping(
    canvases: list[CanvasInfo],
    source_folios: list[str],
) -> list[dict[str, str]]:
    """
    Generate a folio-to-image URL mapping from IIIF canvases and source folios.

    Each row in the output represents either:
    - A matched canvas-to-folio pair
    - An unmatched canvas (folio column empty, with a note)
    - An unmatched folio (image_url column empty, with a note)

    Args:
        canvases: List of CanvasInfo from the IIIF manifest.
        source_folios: List of folio strings from the source's chants.

    Returns:
        List of dicts with keys: 'folio', 'image_link', 'notes', 'canvas_label'
    """
    rows: list[dict[str, str]] = []
    matched_folios: set[str] = set()
    folio_lookups = _build_folio_lookups(source_folios)

    for canvas in canvases:
        matched_folio = match_canvas_to_folio(
            canvas.label, source_folios, folio_lookups=folio_lookups
        )
        note = ""
        folio = ""

        if matched_folio:
            folio = matched_folio
            matched_folios.add(matched_folio)
        else:
            note = "No matching folio in source"

        rows.append(
            {
                "folio": folio,
                "image_link": canvas.image_url or "",
                "notes": note,
                "canvas_label": canvas.label,
            }
        )

    # Add rows for folios that weren't matched to any canvas
    for folio in source_folios:
        if folio not in matched_folios:
            rows.append(
                {
                    "folio": folio,
                    "image_link": "",
                    "notes": "No matching canvas in manifest",
                    "canvas_label": "",
                }
            )

    return rows


# Leading characters that spreadsheet apps (Excel, Sheets) interpret as the
# start of a formula. Canvas labels come from a remote manifest, so a crafted
# label could execute on open (CWE-1236); prefix such values with an apostrophe.
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _escape_csv_field(value: str) -> str:
    """Neutralize spreadsheet formula injection in untrusted text."""
    if value.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + value
    return value


def mapping_to_csv(mapping: list[dict[str, str]]) -> str:
    """
    Convert a folio-image mapping to a CSV string.

    Args:
        mapping: List of dicts from generate_folio_image_mapping.

    Returns:
        CSV string with headers: folio, image_link, notes, canvas_label
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["folio", "image_link", "notes", "canvas_label"])
    for row in mapping:
        # Only canvas_label is untrusted; folio/image_link/notes are our own
        # data and prefixing a URL would corrupt it on re-import.
        writer.writerow(
            [
                row["folio"],
                row["image_link"],
                row["notes"],
                _escape_csv_field(row["canvas_label"]),
            ]
        )
    return output.getvalue().rstrip("\r\n")
