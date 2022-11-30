from django.test import TestCase
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from main_app.models import Segment, Source
from main_app.tests.make_fakes import make_fake_user
from main_app.tests.test_views import get_random_search_term

# run with `python -Wa manage.py test users.tests`
# the -Wa flag tells Python to display deprecation warnings


class UserListViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        self.client.login(email='test@test.com', password='pass')

    def test_url_and_templates(self):
        response = self.client.get(reverse("user-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_list.html")

    def test_view(self):
        for i in range(5):
            get_user_model().objects.create(email=f"test{i}@test.com")

        response = self.client.get(reverse("user-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["users"]), 6)


class IndexerListViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_view_url_path(self):
        response = self.client.get("/indexers/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_list.html")

    def test_only_public_indexer_visible(self):
        """In the indexer list view, only public indexers (those who have at least one published source) should be visible"""
        # generate some indexers
        indexer_with_published_source = make_fake_user()
        indexer_with_unpublished_source = make_fake_user()
        indexer_with_no_source = make_fake_user()

        # generate published/unpublished sources and assign indexers to them
        unpublished_source = Source.objects.create(title="unpublished source", published=False)
        unpublished_source.inventoried_by.set([indexer_with_unpublished_source])

        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        source_with_multiple_indexers = Source.objects.create(
            title="unpublished source with multiple indexers", published=False,
        )
        source_with_multiple_indexers.inventoried_by.set(
            [indexer_with_published_source, indexer_with_unpublished_source]
        )

        # access the page context, only the public indexer should be in the context
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])
        self.assertNotIn(indexer_with_unpublished_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

    def test_search_full_name(self):
        """
        Indexer can be searched by passing a `q` parameter to the url \\
        Search fields include full name, country, city, and institution \\
        Only public indexers should appear in the results
        """
        indexer_with_published_source = make_fake_user()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        # search with a random slice of first name
        target = indexer_with_published_source.full_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_country(self):
        indexer_with_published_source = make_fake_user()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.country
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_city(self):
        indexer_with_published_source = make_fake_user()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.city
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_institution(self):
        indexer_with_published_source = make_fake_user()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.institution
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])


class UserDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create(email='test@test.com')

    def test_url_and_templates(self):
        user = get_user_model().objects.first()
        response = self.client.get(reverse('user-detail', args=[user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_detail.html")

    def test_context(self):
        user = get_user_model().objects.first()
        response = self.client.get(reverse('user-detail', args=[user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], user)