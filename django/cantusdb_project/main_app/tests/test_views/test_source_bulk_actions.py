import ujson

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from main_app.models import Source, Chant
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_segment,
)
from users.models import User


class AddImageLinksViewTest(TestCase):
    auth_user: User
    non_auth_user: User
    source: Source

    @classmethod
    def setUpTestData(cls) -> None:
        user_model = get_user_model()
        cls.auth_user = user_model.objects.create(
            email="authuser@test.com", password="12345", is_staff=True
        )
        cls.non_auth_user = user_model.objects.create(
            email="nonauthuser@test.com", password="12345", is_staff=False
        )
        cls.source = make_fake_source(published=True)
        for folio in ["001r", "001v", "003", "004A"]:
            make_fake_chant(source=cls.source, folio=folio, image_link=None)
        # Make a second chant for one of the folios, with an existing image link.
        # We'll update this image_link in the process.
        make_fake_chant(
            source=cls.source, folio="001v", image_link="https://i-already-exist.com"
        )
        # Make a final chant for a different folio with an existing image link. We
        # won't update this image_link in the process.
        make_fake_chant(
            source=cls.source, folio="004B", image_link="https://i-already-exist.com/2"
        )

    def test_permissions(self) -> None:
        with self.subTest("Test unauthenticated user"):
            response = self.client.get(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={reverse('source-add-image-links', args=[self.source.id])}",
                status_code=302,
                target_status_code=200,
            )
            response = self.client.post(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={reverse('source-add-image-links', args=[self.source.id])}",
                status_code=302,
                target_status_code=200,
            )
        with self.subTest("Test non-staff user"):
            self.client.force_login(self.non_auth_user)
            response = self.client.get(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 403)
            response = self.client.post(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 403)
        with self.subTest("Test staff user"):
            self.client.force_login(self.auth_user)
            response = self.client.get(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 200)
            # Post redirect is tested in the `test_form` method

    def test_form(self) -> None:
        with self.subTest("Test form fields"):
            self.client.force_login(self.auth_user)
            response = self.client.get(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "source_add_image_links.html")
            form = response.context["form"]
            self.assertListEqual(
                list(form.fields.keys()), ["001r", "001v", "003", "004A", "004B"]
            )
        with self.subTest("Test form submission"):
            response = self.client.post(
                reverse("source-add-image-links", args=[self.source.id]),
                {
                    "001r": "https://example.com/001r",
                    "001v": "https://example.com/001v",
                    "004A": "https://example.com/004A",
                },
            )
            self.assertRedirects(
                response,
                reverse("source-detail", args=[self.source.id]),
                status_code=302,
                target_status_code=200,
            )
        with self.subTest("Test saved data"):
            chants_001r = Chant.objects.filter(source=self.source, folio="001r").all()
            self.assertEqual(len(chants_001r), 1)
            self.assertEqual(chants_001r[0].image_link, "https://example.com/001r")
            chants_001v = Chant.objects.filter(source=self.source, folio="001v").all()
            self.assertEqual(len(chants_001v), 2)
            for chant in chants_001v:
                self.assertEqual(chant.image_link, "https://example.com/001v")
            chants_003 = Chant.objects.filter(source=self.source, folio="003").all()
            self.assertEqual(len(chants_003), 1)
            self.assertIsNone(chants_003[0].image_link)
            chants_004B = Chant.objects.filter(source=self.source, folio="004B").all()
            self.assertEqual(len(chants_004B), 1)
            self.assertEqual(chants_004B[0].image_link, "https://i-already-exist.com/2")


class AddChantsViewTest(TestCase):
    auth_user: User
    non_auth_user: User
    source: Source

    @classmethod
    def setUpTestData(cls) -> None:
        segment = make_fake_segment(id=4063)
        cls.source = make_fake_source(published=True, segment=segment)
        user_model = get_user_model()
        cls.auth_user = user_model.objects.create(
            email="authuser@test.com", password="12345", is_staff=True
        )
        cls.non_auth_user = user_model.objects.create(
            email="nonauthuser@test.com", password="12345", is_staff=False
        )

    def test_permissions(self) -> None:
        with self.subTest("Test unauthenticated user"):
            response = self.client.get(
                reverse("source-add-chants", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={reverse('source-add-chants', args=[self.source.id])}",
                status_code=302,
                target_status_code=200,
            )
            response = self.client.post(
                reverse("source-add-chants", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={reverse('source-add-chants', args=[self.source.id])}",
                status_code=302,
                target_status_code=200,
            )
        with self.subTest("Test non-staff user"):
            self.client.force_login(self.non_auth_user)
            response = self.client.get(
                reverse("source-add-chants", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 403)
            response = self.client.post(
                reverse("source-add-chants", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 403)
        with self.subTest("Test staff user"):
            self.client.force_login(self.auth_user)
            response = self.client.get(
                reverse("source-add-chants", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 200)
            # Post redirect is tested in the `test_post` method

    def test_post(self) -> None:
        """
        Tests the following possibilities for the POST request:
            - the data sent with the POST request does not pass
                ChantCreateFromCSVForm validation
            - the data sent with the POST request passes ChantCreateFromCSVForm
                validation, but not the ChantCreateFormset validation
            - the data sent with the POST request passes ChantCreateFromCSVForm
                validation and the ChantCreateFormset validation
        """
        self.client.force_login(self.auth_user)
        with self.subTest("Invalid ChantCreateFromCSVForm"):
            response = self.client.post(
                reverse("source-add-chants", args=[self.source.id]),
                {
                    "new_chants": "Some text that is not JSON.",
                },
            )
            self.assertEqual(response.status_code, 400)
            self.assertJSONEqual(
                response.content,
                {
                    "form_error": "The submitted form is invalid. Please try again.",
                },
            )
        with self.subTest("Valid ChantCreateFromCSVForm; invalid chants"):
            make_fake_chant(source=self.source, folio="001r", c_sequence=1)
            invalid_new_chants = [
                {
                    "folio": "001r",  # This chant repeats the folio
                    "c_sequence": 1,  # and c_sequence of an existing chant
                    "full_text_std_spelling": "Some standard full text",
                },
                {
                    "folio": "001v",
                    "c_sequence": 1,
                    # This chant contains no full_text_std_spelling
                    "polyphony": "Some polyphony",  # Not a valid choice for this field
                },
                {  # a valid chant
                    "folio": "001v",
                    "c_sequence": 2,
                    "full_text_std_spelling": "Some other standard full text",
                },
            ]
            response = self.client.post(
                reverse("source-add-chants", args=[self.source.id]),
                {
                    "new_chants": ujson.dumps(invalid_new_chants),
                },
            )
            self.assertEqual(response.status_code, 400)
            formset_errors = response.json()["formset_errors"]
            expected_formset_errors = [
                {
                    "form_idx": 0,
                    "field_name": "__all__",
                    "error": [
                        "Chant with the same sequence and folio already exists in this source."
                    ],
                },
                {
                    "form_idx": 1,
                    "field_name": "full_text_std_spelling",
                    "error": ["This field is required."],
                },
                {
                    "form_idx": 1,
                    "field_name": "polyphony",
                    "error": [
                        "Select a valid choice. Some polyphony is not one of the available choices."
                    ],
                },
            ]
            self.assertEqual(formset_errors, expected_formset_errors)
            # Test no additional chants were saved
            self.assertEqual(Chant.objects.filter(source=self.source).count(), 1)
        with self.subTest("Valid ChantCreateFromCSVForm; valid chants"):
            valid_new_chants = [
                {
                    "folio": "001v",
                    "c_sequence": 1,
                    "full_text_std_spelling": "Some standard full text",
                },
                {
                    "folio": "001v",
                    "c_sequence": 2,
                    "full_text_std_spelling": "Some other standard full text",
                },
            ]
            response = self.client.post(
                reverse("source-add-chants", args=[self.source.id]),
                {
                    "new_chants": ujson.dumps(valid_new_chants),
                },
            )
            self.assertRedirects(
                response,
                reverse("browse-chants", args=[self.source.id]),
                status_code=302,
                target_status_code=200,
            )
            chants = Chant.objects.filter(source=self.source).all()
            self.assertEqual(len(chants), 3)
