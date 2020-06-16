import random
from pprint import pprint

from django.test import TestCase
from django.urls import reverse
from faker import Faker

from main_app.models import Indexer
from main_app.models import Feast
from main_app.views import FeastListView, IndexerListView

fake = Faker()


class IndexerListViewTest(TestCase):
    PAGE_SIZE = IndexerListView.paginate_by
    MIN_PAGES = 1
    MAX_PAGES = 6

    @classmethod
    def setUpTestData(cls):
        # Create at least 100 + [1,99] indexers, this way we can test pagination since
        # we're paginating by 100 items
        cls.number_of_indexers = cls.PAGE_SIZE * random.randint(
            cls.MIN_PAGES, cls.MAX_PAGES
        ) + random.randint(1, cls.PAGE_SIZE)

        for i in range(cls.number_of_indexers):
            indexer = Indexer.objects.create(
                first_name=fake.first_name(),
                family_name=fake.last_name(),
                institution=fake.company(),
                city=fake.city(),
                country=fake.country(),
            )

    def test_view_url_path(self):
        response = self.client.get("/indexers/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_list.html")

    def test_pagination(self):
        # To get total number of pages do a ceiling integer division
        q, r = divmod(self.number_of_indexers, self.PAGE_SIZE)
        pages = q + bool(r)

        # Test all pages
        for page_num in range(1, pages + 1):
            response = self.client.get(reverse("indexer-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"] == True)
            if page_num == pages and (self.number_of_indexers % self.PAGE_SIZE != 0):
                self.assertTrue(
                    len(response.context["indexers"])
                    == (self.number_of_indexers % self.PAGE_SIZE)
                )
            else:
                self.assertTrue(len(response.context["indexers"]) == self.PAGE_SIZE)

        # Test the "last" syntax
        response = self.client.get(reverse("indexer-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("indexer-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("indexer-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("indexer-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("indexer-list"), {"page": pages + 1})
        self.assertEqual(response.status_code, 404)

    def test_search(self):
        number_of_indexers = Indexer.objects.count()

        # Search by first name
        random_indexer = Indexer.objects.get(
            id=random.randint(1, number_of_indexers + 1)
        )

        # Search the whole first name
        response = self.client.get(
            reverse("indexer-list"), {"q": random_indexer.first_name}
        )
        self.assertEqual(response.status_code, 200)
        # Check object_list (which has the whole queryset, not paginated) instead of
        # indexers which is paginated and might not contain random_indexer if it
        # is not on the first page
        self.assertTrue(random_indexer in response.context["paginator"].object_list)

        # Search for a three letter slice of the first name
        first_name = random_indexer.first_name
        first_name_length = len(first_name)
        if first_name_length > 3:
            # If the name is 3 letters or less we would search for the complete name
            # which we already tested above
            slice_begin = random.randint(0, first_name_length - 3)
            slice_end = slice_begin + 3
            response = self.client.get(
                reverse("indexer-list"),
                {"q": random_indexer.first_name[slice_begin:slice_end]},
            )
            self.assertEqual(response.status_code, 200)
            # Check object_list (which has the whole queryset, not paginated) instead of
            # indexers which is paginated and might not contain random_indexer if it
            # is not on the first page
            self.assertTrue(random_indexer in response.context["paginator"].object_list)


class IndexerDetailViewTest(TestCase):
    NUM_INDEXERS = 10

    @classmethod
    def setUpTestData(cls):
        for i in range(cls.NUM_INDEXERS):
            indexer = Indexer.objects.create(
                first_name=fake.first_name(),
                family_name=fake.last_name(),
                institution=fake.company(),
                city=fake.city(),
                country=fake.country(),
            )

    def test_view_url_path(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(f"/indexers/{indexer.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "indexer_detail.html")

    def test_view_context_data(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
            self.assertTrue("indexer" in response.context)
            self.assertEqual(indexer, response.context["indexer"])


class FeastListViewTest(TestCase):
    PAGE_SIZE = FeastListView.paginate_by
    fixtures = ["feast_fixtures.json"]

    def setUp(self):
        self.number_of_feasts = Feast.objects.all().count()
        return super().setUp()

    def test_view_url_path(self):
        response = self.client.get("/feasts/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_list.html")

    # TODO: maybe make a more general method to test pagination that I can apply
    # to all list views?
    def test_pagination(self):
        # To get total number of pages do a ceiling integer division
        q, r = divmod(self.number_of_feasts, self.PAGE_SIZE)
        pages = q + bool(r)

        # Test all pages
        for page_num in range(1, pages + 1):
            response = self.client.get(reverse("feast-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"] == True)
            if page_num == pages and (self.number_of_feasts % self.PAGE_SIZE != 0):
                self.assertEqual(
                    len(response.context["feasts"]),
                    self.number_of_feasts % self.PAGE_SIZE
                )
            else:
                self.assertEqual(len(response.context["feasts"]), self.PAGE_SIZE)

        # Test the "last" syntax
        response = self.client.get(reverse("feast-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("feast-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": pages + 1})
        self.assertEqual(response.status_code, 404)

    def test_filter_by_month(self):
        for i in range(1, 13):
            month = str(i)
            response = self.client.get(reverse("feast-list"), {"month": month})
            self.assertEqual(response.status_code, 200)
            feasts = response.context["paginator"].object_list
            # Check if all the feasts in the queryset have the month specified
            self.assertTrue(all(feast.month == i for feast in feasts))

    def test_ordering(self):
        # Order by feast_code
        response = self.client.get(reverse("feast-list"), {"ordering": "feast_code"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "feast_code")

        # Order by name
        response = self.client.get(reverse("feast-list"), {"ordering": "name"})
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"ordering": ""})
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"ordering": random.randint(1, 100)}
        )
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        response = self.client.get(
            reverse("feast-list"), {"ordering": fake.text(max_nb_chars=20)}
        )
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")


class FeastDetailViewTest(TestCase):
    fixtures = ["feast_fixtures.json"]
    SLICE_SIZE = 10

    def setUp(self):
        self.number_of_feasts = Feast.objects.all().count()
        self.slice_begin = random.randint(0, self.number_of_feasts - self.SLICE_SIZE)
        self.slice_end = self.slice_begin + self.SLICE_SIZE
        return super().setUp()

    def test_view_url_path(self):
        for feast in Feast.objects.all()[self.slice_begin:self.slice_end]:
            response = self.client.get(f"/feasts/{feast.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for feast in Feast.objects.all()[self.slice_begin:self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        for feast in Feast.objects.all()[self.slice_begin:self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "feast_detail.html")

    def test_view_context_data(self):
        for feast in Feast.objects.all()[self.slice_begin:self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertTrue("feast" in response.context)
            self.assertEqual(feast, response.context["feast"])
