"""Genre and Service labels across search filters and editing forms (#1591)."""

import json
import re
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape, escapejs

from main_app.forms import (
    AdminChantForm,
    AdminSequenceForm,
    BrowseChantsBulkEditFormset,
    ChantCreateForm,
    ChantEditForm,
    SequenceEditForm,
)
from main_app.models import Chant, Genre, Service
from main_app.tests.make_fakes import (
    make_fake_segment,
    make_fake_source,
    make_fake_user,
)


class DropdownLabelsTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.genre = Genre.objects.create(name="AV", description="Antiphon verse")
        cls.service = Service.objects.create(name="V", description="First Vespers")
        cls.bracketed = Genre.objects.create(name="[?]", description="Unknown")
        cls.empty = Genre.objects.create(name="ZZ", description="Missing description")
        # Imported legacy rows can bypass the model's required-field validation.
        Genre.objects.filter(pk=cls.empty.pk).update(description="")
        cls.escaped = Genre.objects.create(name="<&>", description='A < B & "C"')
        cls.segment = make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        cls.source = make_fake_source(published=True, segment=[cls.segment])
        cls.chant = Chant.objects.create(
            source=cls.source,
            genre=cls.genre,
            service=cls.service,
            folio="001r",
            c_sequence=1,
            manuscript_full_text_std_spelling="Ave maria",
        )
        cls.other_chant = Chant.objects.create(
            source=cls.source,
            genre=cls.bracketed,
            service=cls.service,
            folio="001r",
            c_sequence=2,
            manuscript_full_text_std_spelling="Alleluia",
        )
        cls.user = make_fake_user()

    def test_search_filter_labels_and_values(self) -> None:
        for view, args in (
            ("chant-search", []),
            ("chant-search-ms", [self.source.pk]),
            ("ccdb-chant-search", []),
            ("browse-chants", [self.source.pk]),
        ):
            with self.subTest(view=view):
                response = self.client.get(reverse(view, args=args))
                self.assertEqual(response.status_code, 200)
                for genre, label in (
                    (self.genre, "AV - Antiphon verse"),
                    (self.bracketed, "[?] - Unknown"),
                    (self.empty, "ZZ"),
                    (self.escaped, '<&> - A < B & "C"'),
                ):
                    self.assertContains(
                        response,
                        f'<option value="{genre.pk}">{escape(label)}</option>',
                        html=True,
                    )
                if view != "browse-chants":
                    self.assertContains(
                        response,
                        f'<option value="{self.service.pk}">V - First Vespers</option>',
                        html=True,
                    )

    def test_filters_still_return_matching_chants(self) -> None:
        for view, args in (
            ("chant-search", []),
            ("chant-search-ms", [self.source.pk]),
            ("ccdb-chant-search", []),
            ("browse-chants", [self.source.pk]),
        ):
            with self.subTest(view=view):
                response = self.client.get(
                    reverse(view, args=args),
                    {
                        "genre": self.genre.pk,
                        "service": self.service.pk,
                        "db": self.segment.pk,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [chant.pk for chant in response.context["chants"]],
                    [self.chant.pk],
                )

    def test_edit_forms_render_full_selected_labels(self) -> None:
        for form_class in (
            ChantCreateForm,
            ChantEditForm,
            SequenceEditForm,
            AdminChantForm,
            AdminSequenceForm,
        ):
            with self.subTest(form=form_class.__name__):
                form = form_class(
                    initial={"genre": self.bracketed.pk, "service": self.service.pk}
                )
                self.assertInHTML(
                    f'<option value="{self.bracketed.pk}" selected>[?] - Unknown</option>',
                    str(form["genre"]),
                )
                self.assertEqual(
                    form.fields["genre"].clean(str(self.genre.pk)), self.genre
                )
                if "service" in form.fields:
                    self.assertInHTML(
                        f'<option value="{self.service.pk}" selected>V - First Vespers</option>',
                        str(form["service"]),
                    )

    def test_bulk_edit_selected_labels_and_values(self) -> None:
        formset = BrowseChantsBulkEditFormset(
            queryset=Chant.objects.filter(pk=self.chant.pk)
        )
        form = formset.forms[0]
        for field, obj, label in (
            ("genre", self.genre, "AV - Antiphon verse"),
            ("service", self.service, "V - First Vespers"),
        ):
            with self.subTest(field=field):
                self.assertInHTML(
                    f'<option value="{obj.pk}" selected>{label}</option>',
                    str(form[field]),
                )
                form.cleaned_data = {field: str(obj.pk)}
                self.assertEqual(getattr(form, f"clean_{field}")(), obj)

    def test_autocomplete_labels_search_and_order(self) -> None:
        self.client.force_login(self.user)
        for view, obj, label, queries in (
            ("genre-autocomplete", self.genre, "AV - Antiphon verse", ("AV", "verse")),
            (
                "service-autocomplete",
                self.service,
                "V - First Vespers",
                ("V", "vespers"),
            ),
            ("genre-autocomplete", self.bracketed, "[?] - Unknown", ("[?]", "Unknown")),
            ("genre-autocomplete", self.empty, "ZZ", ("ZZ",)),
        ):
            for query in queries:
                with self.subTest(view=view, query=query):
                    response = self.client.get(reverse(view), {"q": query})
                    self.assertEqual(response.status_code, 200)
                    results = response.json()["results"]
                    self.assertEqual(
                        [(result["id"], result["text"]) for result in results],
                        [(str(obj.pk), label)],
                    )
        response = self.client.get(reverse("genre-autocomplete"))
        self.assertEqual(
            [result["id"] for result in response.json()["results"]],
            [
                str(pk)
                for pk in Genre.objects.order_by("name").values_list("pk", flat=True)
            ],
        )

    def test_autocomplete_still_requires_login(self) -> None:
        for view in ("genre-autocomplete", "service-autocomplete"):
            with self.subTest(view=view):
                response = self.client.get(reverse(view))
                self.assertEqual(response.json()["results"], [])

    def test_suggested_chant_autofill_uses_full_label(self) -> None:
        self.source.current_editors.add(self.user)
        self.client.force_login(self.user)
        Chant.objects.filter(source=self.source).update(cantus_id="001234")
        suggestions = [
            {
                "cid": "001235",
                "count": 1,
                "info": {
                    "field_genre": "AV",
                    "field_full_text": "Ave maria",
                },
            }
        ]
        with patch("cantusindex.get_json_from_ci_api", return_value=suggestions):
            response = self.client.get(reverse("chant-create", args=[self.source.pk]))
        self.assertContains(
            response, f'autoFillSuggestedChant( "{escapejs("AV - Antiphon verse")}"'
        )
        suggestion = response.context["suggested_chants"][0]
        self.assertEqual(suggestion["genre_id"], self.genre.pk)
        self.assertEqual(suggestion["genre_name"], "AV")

    def test_cantus_index_autofill_receives_safe_full_labels(self) -> None:
        with patch("main_app.views.chant.get_ci_text_search", return_value=[]):
            response = self.client.get(reverse("ci-search", args=["Ave"]))
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script id="genre-options" type="application/json">(.*?)</script>',
            response.content.decode(),
        )
        self.assertIsNotNone(match)
        labels = {genre["id"]: genre for genre in json.loads(match[1])}
        self.assertEqual(labels[self.genre.pk]["label"], "AV - Antiphon verse")
        self.assertEqual(labels[self.escaped.pk]["label"], '<&> - A < B & "C"')
        self.assertNotIn("<", match[1])
