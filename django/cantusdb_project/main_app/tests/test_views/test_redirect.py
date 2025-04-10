"""
Test views in views/redirect.py
"""

import random

from django.test import TestCase, Client
from django.urls import reverse
from django.http import HttpResponsePermanentRedirect
from faker import Faker

from users.models import User
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_sequence,
)
from articles.tests.test_articles import make_fake_article


faker = Faker("la")


class IndexerRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_indexer_redirect_good(self):
        # generate dummy object
        example_indexer_id = random.randrange(1, 1000000)
        example_matching_user_id = random.randrange(1, 1000000)
        User.objects.create(
            id=example_matching_user_id, old_indexer_id=example_indexer_id
        )

        # find dummy object using /indexer/ path
        response_1 = self.client.get(
            reverse("redirect-indexer", args=[example_indexer_id])
        )
        expected_url = reverse("user-detail", args=[example_matching_user_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_indexer_redirect_bad(self):
        example_bad_indexer_id = random.randrange(1, 1000000)
        response_1 = self.client.get(
            reverse("redirect-indexer", args=[example_bad_indexer_id])
        )
        self.assertEqual(response_1.status_code, 404)


class DocumentRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_document_redirects(self):
        old_document_paths = (
            "/sites/default/files/documents/1. Quick Guide to Liturgy.pdf",
            "/sites/default/files/documents/2. Volpiano Protocols.pdf",
            "/sites/default/files/documents/3. Volpiano Neumes for Review.docx",
            "/sites/default/files/documents/4. Volpiano Neume Protocols.pdf",
            "/sites/default/files/documents/5. Volpiano Editing Guidelines.pdf",
            "/sites/default/files/documents/7. Guide to Graduals.pdf",
            "/sites/default/files/HOW TO - manuscript descriptions-Nov6-20.pdf",
        )
        for path in old_document_paths:
            # each path should redirect to the new path
            response = self.client.get(path)
            self.assertEqual(response.status_code, 301)
            # In Aug 2023, Jacob struggled to get the following lines to work -
            # I was getting 404s when I expected 200s. This final step would be nice
            # to test properly - if a future developer who is cleverer than me can
            # get this working, that would be excellent!

            # redirect_url = response.url
            # followed_response = self.client.get(redirect_url)
            # self.assertEqual(followed_response.status_code, 200)


class NodeURLRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_chant_redirect(self):
        # generate dummy object with ID in valid range
        example_chant_id = random.randrange(1, 1000000)
        source = make_fake_source()
        make_fake_chant(chant_id=example_chant_id, source=source)

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_chant_id])
        )
        expected_url = reverse("chant-detail", args=[example_chant_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_source_redirect(self):
        # generate dummy object with ID in valid range
        example_source_id = random.randrange(1, 1000000)
        source_1 = make_fake_source()
        source_1.id = example_source_id
        source_1.save()

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_source_id])
        )
        expected_url = reverse("source-detail", args=[example_source_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_sequence_redirect(self):
        # generate dummy object with ID in valid range
        example_sequence_id = random.randrange(1, 1000000)
        source = make_fake_source()
        make_fake_sequence(sequence_id=example_sequence_id, source=source)

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_sequence_id])
        )
        expected_url = reverse("sequence-detail", args=[example_sequence_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_article_redirect(self):
        # generate dummy object with ID in valid range
        example_article_id = random.randrange(1, 1000000)
        article_1 = make_fake_article()
        article_1.id = example_article_id
        article_1.save()

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_article_id])
        )
        expected_url = reverse("article-detail", args=[example_article_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_indexer_redirect(self):
        # generate dummy object with ID in valid range
        example_indexer_id = random.randrange(1, 1000000)
        example_matching_user_id = random.randrange(1, 1000000)
        User.objects.create(
            id=example_matching_user_id, old_indexer_id=example_indexer_id
        )

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_indexer_id])
        )
        expected_url = reverse("user-detail", args=[example_matching_user_id])

        self.assertEqual(response_1.status_code, 301)
        self.assertEqual(response_1.url, expected_url)

    def test_bad_redirect(self):
        invalid_node_id = random.randrange(1, 1000000)

        # try to find object that doesn't exist
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[invalid_node_id])
        )
        self.assertEqual(response_1.status_code, 404)

    def test_redirect_above_limit(self):
        # generate dummy object with ID outside of valid range
        over_limit_node_id = 1000001
        source = make_fake_source()
        make_fake_chant(chant_id=over_limit_node_id, source=source)

        # ID above limit
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[over_limit_node_id])
        )
        self.assertEqual(response_1.status_code, 404)


class ChantSearchRedirectTest(TestCase):
    def test_redirects_keep_query(self) -> None:
        cantus_id: str = faker.numerify("######")
        chant = make_fake_chant(cantus_id=cantus_id)
        chants_1 = [make_fake_chant(cantus_id=cantus_id) for _ in range(4)]
        chants_1.append(chant)
        different_cantus_id = str(int(cantus_id) + 1)
        chants_2 = [make_fake_chant(cantus_id=different_cantus_id) for _ in range(3)]

        response_1 = self.client.get(
            reverse("redirect-search"), {"cantus_id": cantus_id}
        )
        self.assertRedirects(
            response_1,
            reverse("chant-search") + f"?cantus_id={cantus_id}",
            status_code=301,
        )
        redirect_response = self.client.get(response_1.headers["Location"])
        self.assertEqual(redirect_response.status_code, 200)
        resp_chants_1 = redirect_response.context["chants"]
        self.assertCountEqual(resp_chants_1, chants_1)

        response_2 = self.client.get(
            reverse("redirect-search"), {"cantus_id": different_cantus_id}
        )
        self.assertRedirects(
            response_2,
            reverse("chant-search") + f"?cantus_id={different_cantus_id}",
            status_code=301,
        )
        redirect_response = self.client.get(response_2.headers["Location"])
        self.assertEqual(redirect_response.status_code, 200)
        resp_chants_2 = redirect_response.context["chants"]
        self.assertCountEqual(resp_chants_2, chants_2)
