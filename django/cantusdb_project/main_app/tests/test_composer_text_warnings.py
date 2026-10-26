"""The trope composer and text warnings must agree on the text being saved."""

import json

from django.contrib.messages import WARNING, get_messages
from django.test import TestCase
from django.urls import reverse

from main_app.models import Chant
from main_app.tests.make_fakes import make_fake_chant, make_fake_source, make_fake_user


class ComposerTextWarningsTest(TestCase):
    def check_composed_text_warnings(self, editing: bool) -> None:
        for element_text, textarea, needs_warning in [
            ("Sanctus @", "Sanctus", True),
            ("Sanctus", "Sanctus @", False),
        ]:
            for acknowledged in [False, True]:
                with self.subTest(element_text=element_text, acknowledged=acknowledged):
                    user = make_fake_user()
                    source = make_fake_source(current_editors=[user])
                    # Clear prior messages so each request tests its own warnings.
                    self.client.cookies.clear()
                    self.client.force_login(user)
                    data = {
                        "folio": "001r",
                        "c_sequence": "1",
                        "manuscript_full_text_std_spelling": textarea,
                        "elements_json": json.dumps(
                            [{"kind": "core", "text": element_text}]
                        ),
                        "confirm_invalid_text": "1" if acknowledged else "",
                    }
                    if editing:
                        chant = make_fake_chant(
                            source=source, folio="001r", c_sequence=1
                        )
                        data["pk"] = str(chant.pk)
                        url = reverse("source-edit-chants", args=[source.pk])
                    else:
                        url = reverse("chant-create", args=[source.pk])

                    response = self.client.post(url, data)

                    self.assertEqual(response.status_code, 302)
                    chant = Chant.objects.get(source=source)
                    self.assertEqual(
                        chant.manuscript_full_text_std_spelling, element_text
                    )
                    self.assertEqual(chant.elements.get().text, element_text)
                    warnings = [
                        str(message)
                        for message in get_messages(response.wsgi_request)
                        if message.level == WARNING
                    ]
                    self.assertEqual(bool(warnings), needs_warning and not acknowledged)
                    if warnings:
                        self.assertIn('"@"', warnings[0])

    def test_create_warns_about_the_composed_text(self) -> None:
        self.check_composed_text_warnings(editing=False)

    def test_edit_warns_about_the_composed_text(self) -> None:
        self.check_composed_text_warnings(editing=True)
