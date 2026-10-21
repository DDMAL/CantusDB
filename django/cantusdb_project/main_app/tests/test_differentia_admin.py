from django.test import TestCase
from django.urls import reverse

from main_app.models import Differentia, Sequence
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_user,
)


class DifferentiaAdminTest(TestCase):
    def setUp(self) -> None:
        self.client.force_login(make_fake_user(is_superuser=True))
        self.differentia = Differentia.objects.create(differentia_id="118a")

    def change_page(self) -> str:
        url = reverse("admin:main_app_differentia_change", args=[self.differentia.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_links_to_the_chants_and_sequences_that_use_it(self) -> None:
        make_fake_chant(diff_db=self.differentia)
        make_fake_chant(diff_db=self.differentia)
        make_fake_chant()
        sequence = make_fake_sequence()
        Sequence.objects.filter(pk=sequence.pk).update(diff_db=self.differentia)

        page = self.change_page()
        chant_list = reverse("admin:main_app_chant_changelist")
        sequence_list = reverse("admin:main_app_sequence_changelist")
        query = f"?diff_db__id__exact={self.differentia.pk}"
        self.assertIn(f'<a href="{chant_list}{query}">2 chants</a>', page)
        self.assertIn(f'<a href="{sequence_list}{query}">1 sequence</a>', page)

        # The link must narrow the list rather than be rejected by the admin.
        response = self.client.get(chant_list + query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 2)

    def test_says_when_nothing_uses_it(self) -> None:
        self.assertIn("No chants or sequences", self.change_page())
