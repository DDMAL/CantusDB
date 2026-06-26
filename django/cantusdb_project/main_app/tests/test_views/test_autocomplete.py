"""
Test cases for views in views/autocomplete.py
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from main_app.tests.make_fakes import make_fake_century, make_fake_feast


class AutocompleteViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        self.client.login(email="test@test.com", password="pass")

    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="editor")
        u1 = get_user_model().objects.create(email="hello@test.com")
        u2 = get_user_model().objects.create(full_name="Lucas")
        editor = Group.objects.get(name="editor")
        editor.user_set.add(u1)
        inactive_user = get_user_model().objects.create(email="inactive@test.com")
        inactive_user.is_active = False
        inactive_user.save()

        for i in range(10):
            make_fake_century()

        make_fake_feast(
            name="Adalberti", description="Adalbert of Prague, Bishop and Martyr"
        )
        make_fake_feast(
            name="Ad Mandatum", description="At the Mandatum (Foot-Washing)"
        )
        make_fake_feast(
            name="Dom. Pentecostes",
            description='Pentecost Sunday (also "Whitsunday")',
        )

    def test_active_users_autocomplete(self):
        response = self.client.get(reverse("active-users-autocomplete"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data["results"]), 3)

    def test_all_users_autocomplete(self):
        response = self.client.get(reverse("all-users-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 4)

        response2 = self.client.get(reverse("all-users-autocomplete"), {"q": "L"})
        self.assertEqual(response2.status_code, 200)
        data = response2.json()
        self.assertEqual(len(data["results"]), 1)

    def test_century_autocomplete(self):
        response = self.client.get(reverse("century-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 10)

    def test_feast_autocomplete(self):
        response = self.client.get(reverse("feast-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)

        # Searches match feast name
        response = self.client.get(reverse("feast-autocomplete"), {"q": "Adalberti"})
        data = response.json()
        self.assertEqual(len(data["results"]), 1)

        # Searches also match feast description (keyword only in description)
        response = self.client.get(reverse("feast-autocomplete"), {"q": "Prague"})
        data = response.json()
        self.assertEqual(len(data["results"]), 1)

        response = self.client.get(reverse("feast-autocomplete"), {"q": "Whitsunday"})
        data = response.json()
        self.assertEqual(len(data["results"]), 1)

    def test_non_authenticated_user(self):
        self.client.logout()
        response = self.client.get(reverse("active-users-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        response = self.client.get(reverse("all-users-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        response = self.client.get(reverse("century-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # FeastAutocomplete is intentionally public: the chant search page is
        # reachable anonymously and uses this endpoint to populate its Select2
        # feast widget.
        response = self.client.get(reverse("feast-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
