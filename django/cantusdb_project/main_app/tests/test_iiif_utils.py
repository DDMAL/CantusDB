"""
Tests for main_app.iiif_utils (IIIF manifest parsing and folio matching).
"""

import csv
import io
from unittest.mock import patch, MagicMock

import requests
from django.test import TestCase
from django.urls import reverse

from main_app.iiif_utils import (
    CanvasInfo,
    ManifestTooLargeError,
    extract_canvases,
    fetch_manifest,
    generate_folio_image_mapping,
    mapping_to_csv,
    match_canvas_to_folio,
    _get_label_text,
    _normalize_folio,
    _extract_folio_components,
)
from main_app.models import Source
from main_app.models.source_url import SourceURL
from main_app.tests.make_fakes import make_fake_source, make_fake_chant
from main_app.tests.mixins import CustomAccessTestMixin

# ---- Sample IIIF manifests for testing ----

SAMPLE_MANIFEST_V2 = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@type": "sc:Manifest",
    "sequences": [
        {
            "canvases": [
                {
                    "@id": "https://example.com/canvas/1",
                    "label": "f. 1r",
                    "images": [
                        {
                            "resource": {
                                "@id": "https://example.com/image/1/full/full/0/default.jpg",
                                "service": {
                                    "@id": "https://example.com/image/1",
                                },
                            }
                        }
                    ],
                },
                {
                    "@id": "https://example.com/canvas/2",
                    "label": "f. 1v",
                    "images": [
                        {
                            "resource": {
                                "@id": "https://example.com/image/2/full/full/0/default.jpg",
                                "service": {
                                    "@id": "https://example.com/image/2",
                                },
                            }
                        }
                    ],
                },
                {
                    "@id": "https://example.com/canvas/3",
                    "label": "f. 2r",
                    "images": [
                        {
                            "resource": {
                                "@id": "https://example.com/image/3/full/full/0/default.jpg",
                                "service": {
                                    "@id": "https://example.com/image/3",
                                },
                            }
                        }
                    ],
                },
            ]
        }
    ],
}

SAMPLE_MANIFEST_V3 = {
    "@context": "http://iiif.io/api/presentation/3/context.json",
    "type": "Manifest",
    "items": [
        {
            "type": "Canvas",
            "label": {"en": ["Folio 1 recto"]},
            "items": [
                {
                    "type": "AnnotationPage",
                    "items": [
                        {
                            "type": "Annotation",
                            "body": {
                                "id": "https://example.com/v3/image/1/full/max/0/default.jpg",
                                "service": [
                                    {
                                        "id": "https://example.com/v3/image/1",
                                        "type": "ImageService3",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
        {
            "type": "Canvas",
            "label": {"en": ["Folio 1 verso"]},
            "items": [
                {
                    "type": "AnnotationPage",
                    "items": [
                        {
                            "type": "Annotation",
                            "body": {
                                "id": "https://example.com/v3/image/2/full/max/0/default.jpg",
                                "service": [
                                    {
                                        "id": "https://example.com/v3/image/2",
                                        "type": "ImageService3",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
    ],
}


class GetLabelTextTest(TestCase):
    def test_string_label(self) -> None:
        self.assertEqual(_get_label_text("f. 1r"), "f. 1r")

    def test_list_label(self) -> None:
        self.assertEqual(_get_label_text(["f. 1r", "Folio 1"]), "f. 1r")

    def test_dict_label_v3(self) -> None:
        self.assertEqual(_get_label_text({"en": ["Folio 1 recto"]}), "Folio 1 recto")

    def test_dict_label_multiple_languages(self) -> None:
        label = {"en": ["Folio 1 recto"], "none": ["f. 1r"]}
        result = _get_label_text(label)
        self.assertIn(result, ["Folio 1 recto", "f. 1r"])

    def test_empty_string(self) -> None:
        self.assertEqual(_get_label_text(""), "")

    def test_empty_dict(self) -> None:
        self.assertEqual(_get_label_text({}), "")


class NormalizeFolioTest(TestCase):
    def test_simple_folio(self) -> None:
        self.assertEqual(_normalize_folio("001r"), "001r")

    def test_strip_prefix_fol(self) -> None:
        self.assertEqual(_normalize_folio("fol. 1r"), "1r")

    def test_strip_prefix_folio(self) -> None:
        self.assertEqual(_normalize_folio("folio 1r"), "1r")

    def test_strip_prefix_f(self) -> None:
        self.assertEqual(_normalize_folio("f. 1r"), "1r")

    def test_whitespace(self) -> None:
        self.assertEqual(_normalize_folio("  001v  "), "001v")

    def test_case_insensitive(self) -> None:
        self.assertEqual(_normalize_folio("FOL. 1R"), "1r")


class ExtractFolioComponentsTest(TestCase):
    def test_simple_recto(self) -> None:
        self.assertEqual(_extract_folio_components("1r"), ("1", "r"))

    def test_simple_verso(self) -> None:
        self.assertEqual(_extract_folio_components("2v"), ("2", "v"))

    def test_zero_padded(self) -> None:
        self.assertEqual(_extract_folio_components("001r"), ("1", "r"))

    def test_with_prefix(self) -> None:
        self.assertEqual(_extract_folio_components("f. 1r"), ("1", "r"))

    def test_no_suffix(self) -> None:
        self.assertEqual(_extract_folio_components("23"), ("23", ""))

    def test_full_word_recto(self) -> None:
        self.assertEqual(_extract_folio_components("1 recto"), ("1", "r"))

    def test_no_match(self) -> None:
        self.assertIsNone(_extract_folio_components("front cover"))


class ExtractCanvasesTest(TestCase):
    def test_v2_manifest(self) -> None:
        canvases = extract_canvases(SAMPLE_MANIFEST_V2)
        self.assertEqual(len(canvases), 3)
        self.assertEqual(canvases[0].label, "f. 1r")
        self.assertEqual(
            canvases[0].image_url,
            "https://example.com/image/1/full/max/0/default.jpg",
        )
        self.assertEqual(canvases[0].canvas_index, 0)
        self.assertEqual(canvases[1].label, "f. 1v")
        self.assertEqual(canvases[2].label, "f. 2r")

    def test_v3_manifest(self) -> None:
        canvases = extract_canvases(SAMPLE_MANIFEST_V3)
        self.assertEqual(len(canvases), 2)
        self.assertEqual(canvases[0].label, "Folio 1 recto")
        self.assertEqual(
            canvases[0].image_url,
            "https://example.com/v3/image/1/full/max/0/default.jpg",
        )
        self.assertEqual(canvases[1].label, "Folio 1 verso")

    def test_empty_manifest(self) -> None:
        canvases = extract_canvases({})
        self.assertEqual(canvases, [])

    def test_v2_no_sequences(self) -> None:
        manifest = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [],
        }
        canvases = extract_canvases(manifest)
        self.assertEqual(canvases, [])

    def test_v2_canvas_no_images(self) -> None:
        manifest = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [{"canvases": [{"label": "blank", "images": []}]}],
        }
        canvases = extract_canvases(manifest)
        self.assertEqual(len(canvases), 1)
        self.assertIsNone(canvases[0].image_url)

    def test_v2_fallback_to_resource_id(self) -> None:
        manifest = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [
                {
                    "canvases": [
                        {
                            "label": "page 1",
                            "images": [
                                {"resource": {"@id": "https://example.com/direct.jpg"}}
                            ],
                        }
                    ]
                }
            ],
        }
        canvases = extract_canvases(manifest)
        self.assertEqual(canvases[0].image_url, "https://example.com/direct.jpg")

    def test_malformed_manifests_yield_no_canvases(self) -> None:
        # fetch_manifest guarantees valid JSON, not a conforming IIIF
        # structure, and the view calls extract_canvases outside the
        # try/except that guards the fetch. Anything raised here would be an
        # unhandled 500 rather than the "no canvases found" message.
        for manifest in (
            [],
            "a string",
            None,
            42,
            {"sequences": {}},
            {"sequences": [None]},
            {"sequences": [{"canvases": None}]},
            {"@context": "http://iiif.io/api/presentation/3/context.json", "items": {}},
        ):
            with self.subTest(manifest=manifest):
                self.assertEqual(extract_canvases(manifest), [])

    def test_null_values_inside_canvases(self) -> None:
        # A manifest can carry explicit nulls where we expect objects.
        manifest = {
            "sequences": [
                {
                    "canvases": [
                        None,
                        {"label": "f. 1r", "images": None},
                        {"label": "f. 1v", "images": [{"resource": None}]},
                        {"label": "f. 2r", "images": [{"resource": {"service": None}}]},
                    ]
                }
            ]
        }
        canvases = extract_canvases(manifest)
        self.assertEqual(len(canvases), 4)
        self.assertEqual([c.image_url for c in canvases], [None, None, None, None])
        self.assertEqual(canvases[1].label, "f. 1r")

    def test_v3_null_values_inside_canvases(self) -> None:
        manifest = {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "items": [
                {"label": {"en": ["Folio 1 recto"]}, "items": None},
                {
                    "label": {"en": ["Folio 1 verso"]},
                    "items": [{"items": [{"body": None}]}],
                },
                {
                    "label": {"en": ["Folio 2 recto"]},
                    "items": [{"items": [{"body": {"service": None}}]}],
                },
            ],
        }
        canvases = extract_canvases(manifest)
        self.assertEqual(len(canvases), 3)
        self.assertEqual([c.image_url for c in canvases], [None, None, None])


class FetchManifestTest(TestCase):
    @staticmethod
    def _mock_response(chunks: list[bytes], headers: dict | None = None) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.headers = headers or {}
        response.iter_content.return_value = iter(chunks)
        return response

    @patch("main_app.iiif_utils.requests.get")
    def test_parses_streamed_json(self, mock_get: MagicMock) -> None:
        mock_get.return_value = self._mock_response([b'{"@id": "x", ', b'"a": 1}'])
        self.assertEqual(
            fetch_manifest("https://example.com/m.json"), {"@id": "x", "a": 1}
        )
        self.assertTrue(mock_get.call_args.kwargs["stream"])

    @patch("main_app.iiif_utils.requests.get")
    def test_invalid_json_raises_value_error(self, mock_get: MagicMock) -> None:
        mock_get.return_value = self._mock_response([b"<html>not json</html>"])
        with self.assertRaises(ValueError):
            fetch_manifest("https://example.com/m.json")

    @patch("main_app.iiif_utils.MAX_MANIFEST_BYTES", 32)
    @patch("main_app.iiif_utils.requests.get")
    def test_rejects_oversized_content_length(self, mock_get: MagicMock) -> None:
        response = self._mock_response([b"{}"], headers={"Content-Length": "9999"})
        mock_get.return_value = response
        with self.assertRaises(ManifestTooLargeError):
            fetch_manifest("https://example.com/m.json")
        # Rejected before reading the body at all.
        response.iter_content.assert_not_called()

    @patch("main_app.iiif_utils.MAX_MANIFEST_BYTES", 32)
    @patch("main_app.iiif_utils.requests.get")
    def test_rejects_oversized_streamed_body(self, mock_get: MagicMock) -> None:
        # No Content-Length header, as on a chunked response: the running
        # total is what has to stop it.
        mock_get.return_value = self._mock_response([b"x" * 16] * 4)
        with self.assertRaises(ManifestTooLargeError):
            fetch_manifest("https://example.com/m.json")

    @patch("main_app.iiif_utils.MAX_MANIFEST_BYTES", 32)
    @patch("main_app.iiif_utils.requests.get")
    def test_understated_content_length_still_capped(self, mock_get: MagicMock) -> None:
        # A hostile server can declare a small size and send a large body.
        mock_get.return_value = self._mock_response(
            [b"x" * 16] * 4, headers={"Content-Length": "2"}
        )
        with self.assertRaises(ManifestTooLargeError):
            fetch_manifest("https://example.com/m.json")

    @patch("main_app.iiif_utils.time.monotonic")
    @patch("main_app.iiif_utils.requests.get")
    def test_slow_drip_hits_the_total_deadline(
        self, mock_get: MagicMock, mock_monotonic: MagicMock
    ) -> None:
        # Each chunk arrives inside the read timeout, so requests never times
        # out on its own; only the total deadline stops this.
        mock_get.return_value = self._mock_response([b"x"] * 100)
        # Start at 0, then jump past a 30s budget on the second check.
        mock_monotonic.side_effect = [0, 1, 2, 31, 60, 90]
        with self.assertRaises(requests.Timeout):
            fetch_manifest("https://example.com/m.json", timeout=30)

    @patch("main_app.iiif_utils.time.monotonic")
    @patch("main_app.iiif_utils.requests.get")
    def test_prompt_response_is_not_timed_out(
        self, mock_get: MagicMock, mock_monotonic: MagicMock
    ) -> None:
        mock_get.return_value = self._mock_response([b'{"a": ', b"1}"])
        mock_monotonic.side_effect = [0, 1, 2]
        self.assertEqual(fetch_manifest("https://example.com/m.json"), {"a": 1})


class MatchCanvasToFolioTest(TestCase):
    def test_exact_match(self) -> None:
        folios = ["001r", "001v", "002r"]
        self.assertEqual(match_canvas_to_folio("001r", folios), "001r")

    def test_match_with_prefix(self) -> None:
        folios = ["001r", "001v", "002r"]
        self.assertEqual(match_canvas_to_folio("f. 001r", folios), "001r")

    def test_component_match(self) -> None:
        folios = ["001r", "001v", "002r"]
        self.assertEqual(match_canvas_to_folio("f. 1r", folios), "001r")

    def test_verbose_label_match(self) -> None:
        folios = ["001r", "001v"]
        self.assertEqual(match_canvas_to_folio("Folio 1 recto", folios), "001r")

    def test_no_match(self) -> None:
        folios = ["001r", "001v"]
        self.assertIsNone(match_canvas_to_folio("front cover", folios))

    def test_empty_label(self) -> None:
        self.assertIsNone(match_canvas_to_folio("", ["001r"]))

    def test_empty_folios(self) -> None:
        self.assertIsNone(match_canvas_to_folio("001r", []))


class GenerateFolioImageMappingTest(TestCase):
    def test_full_match(self) -> None:
        canvases = [
            CanvasInfo(label="f. 1r", image_url="https://img/1", canvas_index=0),
            CanvasInfo(label="f. 1v", image_url="https://img/2", canvas_index=1),
        ]
        folios = ["1r", "1v"]
        mapping = generate_folio_image_mapping(canvases, folios)
        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[0]["folio"], "1r")
        self.assertEqual(mapping[0]["image_link"], "https://img/1")
        self.assertEqual(mapping[0]["notes"], "")
        self.assertEqual(mapping[1]["folio"], "1v")

    def test_unmatched_canvas(self) -> None:
        canvases = [
            CanvasInfo(
                label="front cover", image_url="https://img/cover", canvas_index=0
            ),
            CanvasInfo(label="f. 1r", image_url="https://img/1", canvas_index=1),
        ]
        folios = ["1r"]
        mapping = generate_folio_image_mapping(canvases, folios)
        self.assertEqual(len(mapping), 2)
        # First row is the unmatched canvas
        self.assertEqual(mapping[0]["folio"], "")
        self.assertEqual(mapping[0]["notes"], "No matching folio in source")
        # Second row is the matched canvas
        self.assertEqual(mapping[1]["folio"], "1r")

    def test_unmatched_folio(self) -> None:
        canvases = [
            CanvasInfo(label="f. 1r", image_url="https://img/1", canvas_index=0),
        ]
        folios = ["1r", "2r"]
        mapping = generate_folio_image_mapping(canvases, folios)
        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[0]["folio"], "1r")
        # Unmatched folio appended at the end
        self.assertEqual(mapping[1]["folio"], "2r")
        self.assertEqual(mapping[1]["image_link"], "")
        self.assertEqual(mapping[1]["notes"], "No matching canvas in manifest")

    def test_empty_canvases(self) -> None:
        mapping = generate_folio_image_mapping([], ["1r"])
        self.assertEqual(len(mapping), 1)
        self.assertEqual(mapping[0]["notes"], "No matching canvas in manifest")

    def test_empty_folios(self) -> None:
        canvases = [
            CanvasInfo(label="f. 1r", image_url="https://img/1", canvas_index=0),
        ]
        mapping = generate_folio_image_mapping(canvases, [])
        self.assertEqual(len(mapping), 1)
        self.assertEqual(mapping[0]["notes"], "No matching folio in source")


class MappingToCSVTest(TestCase):
    def test_basic_csv(self) -> None:
        mapping = [
            {
                "folio": "1r",
                "image_link": "https://img/1",
                "notes": "",
                "canvas_label": "f. 1r",
            },
            {
                "folio": "",
                "image_link": "https://img/cover",
                "notes": "No matching folio in source",
                "canvas_label": "front cover",
            },
        ]
        csv_str = mapping_to_csv(mapping)
        lines = csv_str.strip().split("\n")
        self.assertEqual(len(lines), 3)  # header + 2 data rows
        self.assertIn("folio", lines[0])
        self.assertIn("image_link", lines[0])
        self.assertIn("notes", lines[0])
        self.assertIn("canvas_label", lines[0])
        self.assertIn("1r", lines[1])
        self.assertIn("https://img/1", lines[1])

    def test_escapes_formula_injection_in_manifest_derived_columns(self) -> None:
        # canvas_label and image_link are both read out of the remote
        # manifest, so a value starting with a formula trigger character must
        # be neutralized before it can execute in Excel/Sheets (CWE-1236).
        for trigger in ("=", "+", "-", "@", "\t", "\r"):
            for column in ("canvas_label", "image_link"):
                with self.subTest(trigger=repr(trigger), column=column):
                    mapping = [
                        {
                            "folio": "1r",
                            "image_link": "https://img/1",
                            "notes": "",
                            "canvas_label": "f. 1r",
                        }
                    ]
                    mapping[0][column] = f"{trigger}cmd|'/c calc'!A1"
                    rows = list(csv.reader(io.StringIO(mapping_to_csv(mapping))))
                    self.assertEqual(
                        rows[1][
                            ["folio", "image_link", "notes", "canvas_label"].index(
                                column
                            )
                        ],
                        f"'{trigger}cmd|'/c calc'!A1",
                    )

    def test_leaves_ordinary_values_untouched(self) -> None:
        # A real http(s) URL never starts with a trigger character, so
        # escaping the link column must not alter it.
        mapping = [
            {
                "folio": "1r",
                "image_link": "https://img/1/full/max/0/default.jpg",
                "notes": "",
                "canvas_label": "f. 1r",
            }
        ]
        rows = list(csv.reader(io.StringIO(mapping_to_csv(mapping))))
        self.assertEqual(
            rows[1],
            ["1r", "https://img/1/full/max/0/default.jpg", "", "f. 1r"],
        )


class SourceIIIFMappingViewTest(CustomAccessTestMixin, TestCase):
    source: Source
    default_user = "superuser"

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.source = make_fake_source(published=True)
        for folio in ["001r", "001v", "002r"]:
            make_fake_chant(source=cls.source, folio=folio)
        cls.manifest_url = SourceURL.objects.create(
            source=cls.source,
            url="https://example.com/manifest.json",
            url_type=SourceURL.URLTypes.IIIF_MANIFEST,
        )

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            reverse("source-iiif-mapping", args=[self.source.id]),
            get_allowed_users=["superuser"],
            post_allowed_users=[],
            test_name="IIIF mapping",
        )

    @patch("main_app.views.source.fetch_manifest")
    def test_generates_csv(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = SAMPLE_MANIFEST_V2
        response = self.client.get(
            reverse("source-iiif-mapping", args=[self.source.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(
            f"source_{self.source.id}_iiif_mapping.csv",
            response["Content-Disposition"],
        )
        content = response.content.decode("utf-8")
        self.assertIn("folio", content)
        self.assertIn("image_link", content)
        self.assertIn("notes", content)

    def test_no_manifest_redirects_with_error(self) -> None:
        source_no_manifest = make_fake_source(published=True)
        make_fake_chant(source=source_no_manifest, folio="001r")
        response = self.client.get(
            reverse("source-iiif-mapping", args=[source_no_manifest.id])
        )
        self.assertEqual(response.status_code, 302)

    @patch("main_app.views.source.fetch_manifest")
    def test_manifest_fetch_failure_redirects_with_error(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.side_effect = requests.RequestException("Connection failed")
        response = self.client.get(
            reverse("source-iiif-mapping", args=[self.source.id])
        )
        self.assertEqual(response.status_code, 302)

    @patch("main_app.views.source.fetch_manifest")
    def test_oversized_manifest_redirects_with_error(
        self, mock_fetch: MagicMock
    ) -> None:
        # ManifestTooLargeError subclasses ValueError, so it has to be caught
        # ahead of the "not valid JSON" branch to report the real reason.
        mock_fetch.side_effect = ManifestTooLargeError("too big")
        response = self.client.get(
            reverse("source-iiif-mapping", args=[self.source.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [str(m) for m in response.wsgi_request._messages],
            ["IIIF manifest is too large to process."],
        )

    @patch("main_app.views.source.fetch_manifest")
    def test_malformed_manifest_redirects_with_error(
        self, mock_fetch: MagicMock
    ) -> None:
        # A JSON array parses fine but is not a IIIF manifest; this must not
        # reach the view as an unhandled exception.
        mock_fetch.return_value = []
        response = self.client.get(
            reverse("source-iiif-mapping", args=[self.source.id])
        )
        self.assertEqual(response.status_code, 302)

    @patch("main_app.views.source.fetch_manifest")
    def test_manifest_empty_canvases_redirects_with_error(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.return_value = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "sequences": [{"canvases": []}],
        }
        response = self.client.get(
            reverse("source-iiif-mapping", args=[self.source.id])
        )
        self.assertEqual(response.status_code, 302)
