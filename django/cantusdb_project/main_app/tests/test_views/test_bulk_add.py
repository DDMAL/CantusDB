from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from main_app.models import Source, Chant
from main_app.tests.make_fakes import make_fake_source, make_fake_chant
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
