"""Admin-integration tests for the ChantElement inline on ChantAdmin.

These exercise the server-side paths that can't be checked from a unit test of the
model alone: that the inline formset renders on the chant change page, that saving the
change form persists inline elements, and that the edit is captured in the chant's
django-reversion history (ChantAdmin is a VersionAdmin, which follows inline models).
"""

from typing import Dict, List

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse
from reversion.models import Version

from main_app.models import ChantElement
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_chant_element,
    make_fake_user,
)


def _serialize_form(html: bytes, form_id: str) -> Dict[str, List[str]]:
    """Turn a rendered admin form back into a re-postable data dict.

    Captures the current value of every input/select/textarea so the form can be
    submitted unchanged — keeping the chant's required fields valid — leaving the test
    free to append inline-element rows. Mirrors what a browser would submit: unchecked
    checkboxes are omitted, and a single-select with nothing marked falls back to its
    first option.
    """
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form", id=form_id)
    data: Dict[str, List[str]] = {}

    def add(name: str, value: str) -> None:
        data.setdefault(name, []).append(value)

    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name or inp.get("type") in ("submit", "button", "reset", "file"):
            continue
        if inp.get("type") in ("checkbox", "radio"):
            if inp.has_attr("checked"):
                add(name, inp.get("value", "on"))
            continue
        add(name, inp.get("value", ""))

    for textarea in form.find_all("textarea"):
        name = textarea.get("name")
        if name:
            add(name, textarea.text)

    for select in form.find_all("select"):
        name = select.get("name")
        if not name:
            continue
        options = select.find_all("option")
        selected = [opt for opt in options if opt.has_attr("selected")]
        if select.has_attr("multiple"):
            for opt in selected:
                add(name, opt.get("value", ""))
        else:
            chosen = selected[0] if selected else (options[0] if options else None)
            if chosen is not None:
                add(name, chosen.get("value", ""))

    return data


class ChantElementInlineAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = make_fake_user(is_superuser=True)

    def setUp(self) -> None:
        self.client.force_login(self.superuser)
        self.chant = make_fake_chant()
        self.change_url = reverse("admin:main_app_chant_change", args=[self.chant.pk])

    def test_inline_renders_on_chant_change_page(self) -> None:
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 200)
        # The inline formset's management form and its empty-form template are present.
        self.assertContains(response, "elements-TOTAL_FORMS")
        self.assertContains(response, "elements-__prefix__-kind")

    def test_adding_element_via_inline_saves_and_is_versioned(self) -> None:
        data = _serialize_form(self.client.get(self.change_url).content, "chant_form")
        # Add one component element, exactly as clicking "Add another" once would submit.
        data["elements-TOTAL_FORMS"] = ["1"]
        data["elements-0-chant"] = [str(self.chant.pk)]
        data["elements-0-order"] = ["1"]
        data["elements-0-kind"] = [ChantElement.Kind.COMPONENT]
        data["elements-0-text"] = ["Trope text"]
        data["elements-0-cantus_id"] = ["g00001:01"]

        response = self.client.post(self.change_url, data)
        self.assertEqual(response.status_code, 302)  # a successful admin save redirects

        element = self.chant.elements.get()
        self.assertEqual(element.kind, ChantElement.Kind.COMPONENT)
        self.assertEqual(element.text, "Trope text")
        self.assertEqual(element.cantus_id, "g00001:01")

        # The inline edit lands in the chant's revision, and the element is captured in
        # the same revision (VersionAdmin follows the inline relation).
        chant_versions = Version.objects.get_for_object(self.chant)
        self.assertTrue(chant_versions.exists())
        revision = chant_versions[0].revision
        self.assertTrue(
            revision.version_set.filter(
                content_type__model="chantelement",
                object_id=str(element.pk),
            ).exists(),
            "inline element should be captured in the chant's revision",
        )

    def test_editing_existing_element_via_inline_updates_it(self) -> None:
        element = make_fake_chant_element(
            chant=self.chant, kind=ChantElement.Kind.CORE, cantus_id=""
        )
        data = _serialize_form(self.client.get(self.change_url).content, "chant_form")
        # The rendered inline row is index 0; change its text and re-post.
        data["elements-0-text"] = ["Revised core text"]

        response = self.client.post(self.change_url, data)
        self.assertEqual(response.status_code, 302)

        element.refresh_from_db()
        self.assertEqual(element.text, "Revised core text")
        self.assertEqual(self.chant.elements.count(), 1)
