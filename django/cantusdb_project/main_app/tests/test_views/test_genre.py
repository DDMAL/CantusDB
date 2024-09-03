"""
Test views in views/genre.py
"""

import random

from django.test import TestCase
from django.urls import reverse

from main_app.models import Genre
from main_app.tests.make_fakes import make_fake_genre


class GenreListViewTest(TestCase):
    fake_genres: dict[str, Genre] = {}

    @classmethod
    def setUpTestData(cls) -> None:
        mass_office_genre = make_fake_genre(
            name="genre1",
            description="test",
            mass_office="Mass, Office",
        )
        mass_genre = make_fake_genre(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = make_fake_genre(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = make_fake_genre(
            name="genre4",
            description="test",
            mass_office="Old Hispanic",
        )
        cls.fake_genres = {
            "mass_office_genre": mass_office_genre,
            "mass_genre": mass_genre,
            "office_genre": office_genre,
            "old_hispanic_genre": old_hispanic_genre,
        }

    def test_view_url_path(self) -> None:
        response = self.client.get("/genres/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self) -> None:
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self) -> None:
        """Test the url and templates used"""
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_list.html")

    def test_filter_by_mass(self) -> None:
        # filter by Mass
        response = self.client.get(reverse("genre-list"), {"mass_office": "Mass"})
        genres = response.context["genres"]
        # Mass, Office and Mass should be in the list, while the others should not
        self.assertIn(self.fake_genres["mass_genre"], genres)
        self.assertIn(self.fake_genres["mass_office_genre"], genres)
        self.assertNotIn(self.fake_genres["office_genre"], genres)
        self.assertNotIn(self.fake_genres["old_hispanic_genre"], genres)

    def test_filter_by_office(self) -> None:
        # filter by Office
        response = self.client.get(reverse("genre-list"), {"mass_office": "Office"})
        genres = response.context["genres"]
        # Office, Office and Mass should be in the list, while the others should not
        self.assertNotIn(self.fake_genres["mass_genre"], genres)
        self.assertIn(self.fake_genres["mass_office_genre"], genres)
        self.assertIn(self.fake_genres["office_genre"], genres)
        self.assertNotIn(self.fake_genres["old_hispanic_genre"], genres)

    def test_no_filtering(self) -> None:
        # default is no filtering
        response = self.client.get(reverse("genre-list"))
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(self.fake_genres["mass_genre"], genres)
        self.assertIn(self.fake_genres["mass_office_genre"], genres)
        self.assertIn(self.fake_genres["office_genre"], genres)
        self.assertIn(self.fake_genres["old_hispanic_genre"], genres)

    def test_invalid_filtering(self) -> None:
        # invalid filtering parameter should default to no filtering
        response = self.client.get(
            reverse("genre-list"), {"mass_office": "invalid param"}
        )
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(self.fake_genres["mass_genre"], genres)
        self.assertIn(self.fake_genres["mass_office_genre"], genres)
        self.assertIn(self.fake_genres["office_genre"], genres)
        self.assertIn(self.fake_genres["old_hispanic_genre"], genres)

    def test_json_reponse(self) -> None:
        response = self.client.get(
            reverse("genre-list"), headers={"Accept": "application/json"}
        )
        expected_genres = [
            {
                "id": self.fake_genres[key].id,
                "name": self.fake_genres[key].name,
                "description": self.fake_genres[key].description,
                "mass_office": self.fake_genres[key].mass_office,
            }
            for key in self.fake_genres
        ]
        self.assertEqual(response.headers["Content-Type"], "application/json")
        response_genres = response.json()["genres"]
        response_genres_id_ordered = sorted(response_genres, key=lambda x: x["id"])
        self.assertEqual(response_genres_id_ordered, expected_genres)


class GenreDetailViewTest(TestCase):
    GENRE_COUNT = 10
    fake_genres: list[Genre] = []

    @classmethod
    def setUpTestData(cls) -> None:
        cls.fake_genres = [make_fake_genre() for _ in range(cls.GENRE_COUNT)]

    def test_view_url_path(self) -> None:
        for genre in Genre.objects.all():
            response = self.client.get(f"/genre/{genre.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self) -> None:
        for genre in Genre.objects.all():
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_context_data(self) -> None:
        for genre in Genre.objects.all():
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertTrue("genre" in response.context)
            self.assertEqual(genre, response.context["genre"])

    def test_url_and_templates(self) -> None:
        """Test the url and templates used"""
        genre = random.choice(self.fake_genres)
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_detail.html")

    def test_context(self) -> None:
        genre = random.choice(self.fake_genres)
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(genre, response.context["genre"])

    def test_json_response(self) -> None:
        genre = random.choice(self.fake_genres)
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]),
            headers={"Accept": "application/json"},
        )
        expected_genre = {
            "id": genre.id,
            "name": genre.name,
            "description": genre.description,
            "mass_office": genre.mass_office,
        }
        self.assertEqual(response.headers["Content-Type"], "application/json")
        response_genre = response.json()["genre"]
        self.assertEqual(response_genre, expected_genre)
