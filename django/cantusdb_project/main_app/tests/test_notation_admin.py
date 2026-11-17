from django.test import TestCase
from django.urls import reverse

from main_app.models import Notation
from main_app.tests.make_fakes import make_fake_source, make_fake_user


class NotationLabelsTest(TestCase):
    """The notation list belongs to the Clavis Sequentiarum (#2330)."""

    def setUp(self) -> None:
        self.client.force_login(make_fake_user(is_superuser=True))

    def test_taxonomy_manager_lists_it_next_to_sequences(self) -> None:
        response = self.client.get(reverse("admin:index"))
        names = [
            model["name"]
            for app in response.context["app_list"]
            for model in app["models"]
        ]
        label = "Sequence notations (Clavis Sequentiarum)"
        self.assertIn(label, names)
        self.assertNotIn("Notations", names)
        self.assertEqual(names[names.index(label) + 1], "Sequences")

    def test_source_admin_labels_the_field(self) -> None:
        source = make_fake_source()
        source.notation.add(Notation.objects.create(name="German neumes"))
        url = reverse("admin:main_app_source_change", args=[source.pk])
        self.assertContains(self.client.get(url), "Notation (Clavis Sequentiarum)")

    def test_its_own_pages_use_the_new_name(self) -> None:
        response = self.client.get(reverse("admin:main_app_notation_changelist"))
        self.assertContains(response, "Select sequence notation to change")

    def test_content_overview_link_selects_the_list(self) -> None:
        Notation.objects.create(name="German neumes")
        response = self.client.get(reverse("content-overview"))
        self.assertContains(
            response,
            '<a href="?model=sequence%20notations%20%28Clavis%20Sequentiarum%29">',
        )
        response = self.client.get(
            reverse("content-overview"),
            {"model": "sequence notations (Clavis Sequentiarum)"},
        )
        self.assertContains(response, "German neumes")
