from django.urls import reverse
from django.test import TestCase
from main_app.views.feast import FeastListView
from django.http.response import JsonResponse
import json
from .make_fakes import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.db.models import Q

# run with `python -Wa manage.py test main_app.tests.test_views_general`
# the -Wa flag tells Python to display deprecation warnings


def get_random_search_term(target):
    """Helper function for generating a random slice of a string.

    Args:
        target (str): The content of the field to search.
    
    Returns:
        str: A random slice of `target`
    """
    if len(target) <= 2:
        search_term = target
    else:
        slice_start = random.randint(0, len(target) - 2)
        slice_end = random.randint(slice_start + 2, len(target))
        search_term = target[slice_start:slice_end]
    return search_term


class IndexerListViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_list.html")

    def test_only_public_indexer_visible(self):
        """In the indexer list view, only public indexers (those who have at least one public source) should be visible"""
        # generate some indexers
        indexer_with_public_source = make_fake_indexer()
        indexer_with_private_source = make_fake_indexer()
        indexer_with_no_source = make_fake_indexer()

        # generate public/private sources and assign indexers to them
        private_source = Source.objects.create(title="private source", public=False)
        private_source.inventoried_by.set([indexer_with_private_source])

        public_source = Source.objects.create(title="published source", public=True)
        public_source.inventoried_by.set([indexer_with_public_source])

        source_with_multiple_indexers = Source.objects.create(
            title="private source with multiple indexers", public=False,
        )
        source_with_multiple_indexers.inventoried_by.set(
            [indexer_with_public_source, indexer_with_private_source]
        )

        # access the page context, only the public indexer should be in the context
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

    def test_search_given_name(self):
        """
        Indexer can be searched by passing a `q` parameter to the url \\
        Search fields include first name, family name, country, city, and institution \\
        Only public indexers should appear in the results
        """
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        # search with a random slice of first name
        target = indexer_with_public_source.given_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_family_name(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.family_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_country(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.country
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_city(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.city
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_institution(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.institution
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])


class IndexerDetailViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_detail.html")

    def test_context(self):
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(indexer, response.context["indexer"])


class FeastListViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_list.html")

    def test_filter_by_month(self):
        for i in range(1, 13):
            Feast.objects.create(name=f"test_feast{i}", month=i)
        for i in range(1, 13):
            month = str(i)
            response = self.client.get(reverse("feast-list"), {"month": month})
            self.assertEqual(response.status_code, 200)
            feasts = response.context["feasts"]
            self.assertTrue(all(feast.month == i for feast in feasts))

    def test_ordering(self):
        """Feast can be ordered by name or feast_code"""
        # Order by feast_code
        response = self.client.get(reverse("feast-list"), {"sort_by": "feast_code"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "feast_code")

        # Order by name
        response = self.client.get(reverse("feast-list"), {"sort_by": "name"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"sort_by": ""})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"sort_by": make_fake_text(max_size=5)}
        )
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

    def test_search_name(self):
        """Feast can be searched by any part of its name, description, or feast_code"""
        feast = make_fake_feast()
        target = feast.name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_description(self):
        feast = make_fake_feast()
        target = feast.description
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_feast_code(self):
        feast = make_fake_feast()
        target = feast.feast_code
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_pagination(self):
        PAGINATE_BY = FeastListView.paginate_by
        # test 2 full pages of feasts
        feast_count = PAGINATE_BY * 2
        for i in range(feast_count):
            make_fake_feast()
        page_count = int(feast_count / PAGINATE_BY)
        assert page_count == 2
        for page_num in range(1, page_count + 1):
            response = self.client.get(reverse("feast-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["feasts"]), PAGINATE_BY)

        # test a little more than 2 full pages of feasts
        new_feast_count = feast_count + random.randint(1, PAGINATE_BY - 1)
        for i in range(new_feast_count - feast_count):
            make_fake_feast()
        new_page_count = page_count + 1
        # The last page should have the same number of feasts as we added
        response = self.client.get(reverse("feast-list"), {"page": new_page_count})
        self.assertEqual(response.status_code, 200)
        self.assertTrue("is_paginated" in response.context)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["feasts"]), new_feast_count - feast_count)

        # test the "last" syntax
        response = self.client.get(reverse("feast-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("feast-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": new_page_count + 1})
        self.assertEqual(response.status_code, 404)


class FeastDetailViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_detail.html")

    def test_context(self):
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(feast, response.context["feast"])

    def test_most_frequent_chants(self):
        source = Source.objects.create(public=True, visible=True, title="public_source")
        feast = make_fake_feast()
        # 3 chants with cantus id: 300000
        for i in range(3):
            Chant.objects.create(feast=feast, cantus_id="300000", source=source)
        # 2 chants with cantus id: 200000
        for i in range(2):
            Chant.objects.create(feast=feast, cantus_id="200000", source=source)
        # 1 chant with cantus id: 100000
        Chant.objects.create(feast=feast, cantus_id="100000", source=source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response.context["frequent_chants_zip"]
        # the items in zip should be ordered by chant count
        # the first field is cantus id
        self.assertEqual(frequent_chants_zip[0][0], "300000")
        self.assertEqual(frequent_chants_zip[1][0], "200000")
        self.assertEqual(frequent_chants_zip[2][0], "100000")
        # the last field is cantus count
        self.assertEqual(frequent_chants_zip[0][-1], 3)
        self.assertEqual(frequent_chants_zip[1][-1], 2)
        self.assertEqual(frequent_chants_zip[2][-1], 1)

    def test_sources_containing_this_feast(self):
        big_source = Source.objects.create(
            public=True, visible=True, title="big_source", siglum="big"
        )
        small_source = Source.objects.create(
            public=True, visible=True, title="small_source", siglum="small"
        )
        feast = make_fake_feast()
        # 3 chants in the big source
        for i in range(3):
            Chant.objects.create(feast=feast, source=big_source)
        # 1 chant in the small source
        Chant.objects.create(feast=feast, source=small_source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources_zip = response.context["sources_zip"]
        # the items in zip should be ordered by chant count
        # the first field is siglum
        self.assertEqual(sources_zip[0][0].siglum, "big")
        self.assertEqual(sources_zip[1][0].siglum, "small")
        # the second field is chant_count
        self.assertEqual(sources_zip[0][1], 3)
        self.assertEqual(sources_zip[1][1], 1)


class GenreListViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_list.html")

    def test_filter_by_mass(self):
        mass_office_genre = Genre.objects.create(
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
        )
        # filter by Mass
        response = self.client.get(reverse("genre-list"), {"mass_office": "Mass"})
        genres = response.context["genres"]
        # Mass, Office and Mass should be in the list, while the others should not
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertNotIn(office_genre, genres)
        self.assertNotIn(old_hispanic_genre, genres)

    def test_filter_by_office(self):
        mass_office_genre = Genre.objects.create(
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
        )
        # filter by Office
        response = self.client.get(reverse("genre-list"), {"mass_office": "Office"})
        genres = response.context["genres"]
        # Office, Office and Mass should be in the list, while the others should not
        self.assertNotIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertNotIn(old_hispanic_genre, genres)

    def test_no_filtering(self):
        mass_office_genre = Genre.objects.create(
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
        )
        # default is no filtering
        response = self.client.get(reverse("genre-list"))
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertIn(old_hispanic_genre, genres)

    def test_invalid_filtering(self):
        mass_office_genre = Genre.objects.create(
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
        )
        # invalid filtering parameter should default to no filtering
        response = self.client.get(
            reverse("genre-list"), {"mass_office": "invalid param"}
        )
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertIn(old_hispanic_genre, genres)


class GenreDetailViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        genre = make_fake_genre()
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_detail.html")

    def test_context(self):
        genre = make_fake_genre()
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(genre, response.context["genre"])

    def test_chants_by_genre(self):
        genre = make_fake_genre()
        chant1 = Chant.objects.create(incipit="chant1", genre=genre, cantus_id="100000")
        chant2 = Chant.objects.create(incipit="chant2", genre=genre, cantus_id="100000")
        chant3 = Chant.objects.create(incipit="chant3", genre=genre, cantus_id="123456")
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        # the context should be a list of dicts, each corresponding to one cantus id
        chant_info_list = response.context["object_list"]
        # the chant info list should be ordered by the number of chants
        # the first one should be the one that has two chants
        self.assertEqual(chant_info_list[0]["cantus_id"], "100000")
        self.assertEqual(chant_info_list[0]["num_chants"], 2)
        self.assertEqual(chant_info_list[1]["cantus_id"], "123456")
        self.assertEqual(chant_info_list[1]["num_chants"], 1)

    def test_search_incipit(self):
        genre = make_fake_genre()
        chant1 = Chant.objects.create(incipit="chant1", genre=genre, cantus_id="100000")
        chant2 = Chant.objects.create(incipit="chant2", genre=genre, cantus_id="123456")
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)

        # search for the common part of incipit
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "chant"}
        )
        # both cantus_ids should be in the list
        self.assertEqual(len(response.context["object_list"]), 2)
        # search for the unique part of incipit
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "chant1"}
        )
        # only one record should be in the list
        self.assertEqual(len(response.context["object_list"]), 1)
        # search for random incipit that don't exist
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "random"}
        )
        # the list should be empty
        self.assertEqual(len(response.context["object_list"]), 0)


class OfficeListViewTest(TestCase):
    def test_url_and_templates(self):
        response = self.client.get(reverse("office-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "office_list.html")

    def test_context(self):
        # make a certain number of offices
        office_cnt = random.randint(1, 10)
        for i in range(office_cnt):
            make_fake_office()
        office = Office.objects.first()
        response = self.client.get(reverse("office-list"))
        offices = response.context["offices"]
        # the list view should contain all offices
        self.assertEqual(offices.count(), office_cnt)


class OfficeDetailViewTest(TestCase):
    def test_url_and_templates(self):
        office = make_fake_office()
        response = self.client.get(reverse("office-detail", args=[office.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "office_detail.html")

    def test_context(self):
        office = make_fake_office()
        response = self.client.get(reverse("office-detail", args=[office.id]))
        self.assertEqual(office, response.context["office"])


class SourceListViewTest(TestCase):
    def test_url_and_templates(self):
        response = self.client.get(reverse("source-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_list.html")

    def test_provenances_and_centuries_in_context(self):
        """Test the `provenances` and `centuries` in the context. They are displayed as options in the selectors"""
        provenance = make_fake_provenance()
        century = make_fake_century()
        response = self.client.get(reverse("source-list"))
        provenances = response.context["provenances"]
        self.assertIn({"id": provenance.id, "name": provenance.name}, provenances)
        centuries = response.context["centuries"]
        self.assertIn({"id": century.id, "name": century.name}, centuries)

    def test_only_public_sources_visible(self):
        """For a source to be displayed in the list, its `public` and `visible` fields must both be `True`"""
        public_source = Source.objects.create(
            public=True, visible=True, title="public source"
        )
        private_source1 = Source.objects.create(
            public=False, visible=True, title="private source"
        )
        private_source2 = Source.objects.create(
            public=False, visible=False, title="private source"
        )
        private_source3 = Source.objects.create(
            public=True, visible=False, title="private source"
        )
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        self.assertIn(public_source, sources)
        self.assertNotIn(private_source1, sources)
        self.assertNotIn(private_source2, sources)
        self.assertNotIn(private_source3, sources)

    def test_filter_by_segment(self):
        """The source list can be filtered by `segment`, `provenance`, `century`, and `full_source`"""
        cantus_segment = Segment.objects.create(name="cantus")
        clavis_segment = Segment.objects.create(name="clavis")
        chant_source = Source.objects.create(
            segment=cantus_segment, title="chant source", public=True, visible=True
        )
        seq_source = Source.objects.create(
            segment=clavis_segment, title="sequence source", public=True, visible=True
        )

        # display chant sources only
        response = self.client.get(
            reverse("source-list"), {"segment": cantus_segment.id}
        )
        sources = response.context["sources"]
        self.assertIn(chant_source, sources)
        self.assertNotIn(seq_source, sources)

        # display sequence sources only
        response = self.client.get(
            reverse("source-list"), {"segment": clavis_segment.id}
        )
        sources = response.context["sources"]
        self.assertIn(seq_source, sources)
        self.assertNotIn(chant_source, sources)

    def test_filter_by_provenance(self):
        aachen = make_fake_provenance()
        albi = make_fake_provenance()
        aachen_source = Source.objects.create(
            provenance=aachen,
            public=True,
            visible=True,
            title="source originated in Aachen",
        )
        albi_source = Source.objects.create(
            provenance=albi,
            public=True,
            visible=True,
            title="source originated in Albi",
        )
        no_provenance_source = Source.objects.create(
            public=True, visible=True, title="source with empty provenance"
        )

        # display sources in Aachen
        response = self.client.get(reverse("source-list"), {"provenance": aachen.id})
        sources = response.context["sources"]
        # only aachen_source should be in the list
        self.assertIn(aachen_source, sources)
        self.assertNotIn(albi_source, sources)
        self.assertNotIn(no_provenance_source, sources)

    def test_filter_by_century(self):
        ninth_century = Century.objects.create(name="09th century")
        ninth_century_first_half = Century.objects.create(
            name="09th century (1st half)"
        )
        tenth_century = Century.objects.create(name="10th century")

        ninth_century_source = Source.objects.create(
            public=True, visible=True, title="source",
        )
        ninth_century_source.century.set([ninth_century])

        ninth_century_first_half_source = Source.objects.create(
            public=True, visible=True, title="source",
        )
        ninth_century_first_half_source.century.set([ninth_century_first_half])

        multiple_century_source = Source.objects.create(
            public=True, visible=True, title="source",
        )
        multiple_century_source.century.set([ninth_century, tenth_century])

        # display sources in ninth century
        response = self.client.get(
            reverse("source-list"), {"century": ninth_century.id}
        )
        sources = response.context["sources"]
        # ninth_century_source, ninth_century_first_half_source, and
        # multiple_century_source should all be in the list
        self.assertIn(ninth_century_source, sources)
        self.assertIn(ninth_century_first_half_source, sources)
        self.assertIn(multiple_century_source, sources)

        # display sources in ninth century first half
        response = self.client.get(
            reverse("source-list"), {"century": ninth_century_first_half.id}
        )
        sources = response.context["sources"]
        # only ninth_century_first_half_source should be in the list
        self.assertNotIn(ninth_century_source, sources)
        self.assertIn(ninth_century_first_half_source, sources)
        self.assertNotIn(multiple_century_source, sources)

    def test_filter_by_full_source(self):
        full_source = Source.objects.create(
            full_source=True, public=True, visible=True, title="full source"
        )
        fragment = Source.objects.create(
            full_source=False, public=True, visible=True, title="fragment"
        )
        unknown = Source.objects.create(
            public=True, visible=True, title="full_source field is empty"
        )

        # display full sources
        response = self.client.get(reverse("source-list"), {"fullsource": "true"})
        sources = response.context["sources"]
        # full_source and unknown_source should be in the list, fragment should not
        self.assertIn(full_source, sources)
        self.assertNotIn(fragment, sources)
        self.assertIn(unknown, sources)

        # display fragments
        response = self.client.get(reverse("source-list"), {"fullsource": "false"})
        sources = response.context["sources"]
        # fragment should be in the list, full_source and unknown_source should not
        self.assertNotIn(full_source, sources)
        self.assertIn(fragment, sources)
        self.assertNotIn(unknown, sources)

        # display all sources
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        # all three should be in the list
        self.assertIn(full_source, sources)
        self.assertIn(fragment, sources)
        self.assertIn(unknown, sources)

    def test_search_by_title(self):
        """The "general search" field searches in `title`, `siglum`, `rism_siglum`, `description`, and `summary`"""
        source = Source.objects.create(
            title=make_fake_text(max_size=20), public=True, visible=True
        )
        search_term = get_random_search_term(source.title)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_siglum(self):
        source = Source.objects.create(
            siglum=make_fake_text(max_size=20), public=True, visible=True, title="title"
        )
        search_term = get_random_search_term(source.siglum)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_name(self):
        rism_siglum = make_fake_rism_siglum()
        source = Source.objects.create(
            rism_siglum=rism_siglum, public=True, visible=True, title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.name)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_description(self):
        rism_siglum = make_fake_rism_siglum()
        source = Source.objects.create(
            rism_siglum=rism_siglum, public=True, visible=True, title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_description(self):
        source = Source.objects.create(
            description=make_fake_text(max_size=200),
            public=True,
            visible=True,
            title="title",
        )
        search_term = get_random_search_term(source.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_summary(self):
        source = Source.objects.create(
            summary=make_fake_text(max_size=200),
            public=True,
            visible=True,
            title="title",
        )
        search_term = get_random_search_term(source.summary)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_indexing_notes(self):
        """The "indexing notes" field searches in `indexing_notes` and indexer/editor related fields"""
        source = Source.objects.create(
            indexing_notes=make_fake_text(max_size=200),
            public=True,
            visible=True,
            title="title",
        )
        search_term = get_random_search_term(source.indexing_notes)
        response = self.client.get(reverse("source-list"), {"indexing": search_term})
        self.assertIn(source, response.context["sources"])


class SourceDetailViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_detail.html")

    def test_context_chant_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_sequence_folios(self):
        # create a sequence source and several sequences in it
        source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            title="a sequence source",
        )
        Sequence.objects.create(source=source, folio="001r")
        Sequence.objects.create(source=source, folio="001r")
        Sequence.objects.create(source=source, folio="001v")
        Sequence.objects.create(source=source, folio="001v")
        Sequence.objects.create(source=source, folio="002r")
        Sequence.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])
        # the folios should be ordered by the "folio" field
        self.assertEqual(folios.query.order_by, ("folio",))

    def test_context_feasts_with_folios(self):
        # create a source and several chants (associated with feasts) in it
        source = make_fake_source()
        feast_1 = make_fake_feast()
        feast_2 = make_fake_feast()
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="002r", feast=feast_1)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [("001r", feast_1), ("001v", feast_2), ("002r", feast_1)]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)

    def test_context_sequences(self):
        # create a sequence source and several sequences in it
        source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            title="a sequence source",
        )
        sequence = Sequence.objects.create(source=source)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the sequence should be in the list of sequences
        self.assertIn(sequence, response.context["sequences"])
        # the list of sequences should be ordered by the "sequence" field
        self.assertEqual(response.context["sequences"].query.order_by, ("sequence",))


class SequenceListViewTest(TestCase):
    def test_url_and_templates(self):
        response = self.client.get(reverse("sequence-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_list.html")

    def test_ordering(self):
        # the sequences in the list should be ordered by the "siglum" and "sequence" fields
        response = self.client.get(reverse("sequence-list"))
        sequences = response.context["sequences"]
        self.assertEqual(sequences.query.order_by, ("siglum", "sequence"))

    def test_search_incipit(self):
        # create a public sequence source and some sequence in it
        source = Source.objects.create(
            public=True, visible=True, title="a sequence source"
        )
        sequence = Sequence.objects.create(
            incipit=make_fake_text(max_size=30), source=source
        )
        search_term = get_random_search_term(sequence.incipit)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"incipit": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_siglum(self):
        # create a public sequence source and some sequence in it
        source = Source.objects.create(
            public=True, visible=True, title="a sequence source"
        )
        sequence = Sequence.objects.create(
            siglum=make_fake_text(max_size=10), source=source
        )
        search_term = get_random_search_term(sequence.siglum)
        # request the page, search for the siglum
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_cantus_id(self):
        # create a public sequence source and some sequence in it
        source = Source.objects.create(
            public=True, visible=True, title="a sequence source"
        )
        # faker generates a fake cantus id, in the form of two letters followed by five digits
        sequence = Sequence.objects.create(
            cantus_id=faker.bothify("??#####"), source=source
        )
        search_term = get_random_search_term(sequence.cantus_id)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"cantus_id": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])


class SequenceDetailViewTest(TestCase):
    def test_url_and_templates(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_detail.html")

    def test_concordances(self):
        sequence = make_fake_sequence()
        sequence_with_same_cantus_id = Sequence.objects.create(
            cantus_id=sequence.cantus_id
        )
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        concordances = response.context["concordances"]
        self.assertIn(sequence_with_same_cantus_id, concordances)


class ChantListViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_list.html")

    def test_filter_by_source(self):
        source = make_fake_source()
        another_source = make_fake_source()
        chant_in_source = Chant.objects.create(source=source)
        chant_in_another_source = Chant.objects.create(source=another_source)
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        chants = response.context["chants"]
        self.assertIn(chant_in_source, chants)
        self.assertNotIn(chant_in_another_source, chants)

    def test_filter_by_feast(self):
        source = make_fake_source()
        feast = make_fake_feast()
        another_feast = make_fake_feast()
        chant_in_feast = Chant.objects.create(source=source, feast=feast)
        chant_in_another_feast = Chant.objects.create(
            source=source, feast=another_feast
        )
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "feast": feast.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_feast, chants)
        self.assertNotIn(chant_in_another_feast, chants)

    def test_filter_by_genre(self):
        source = make_fake_source()
        genre = make_fake_genre()
        another_genre = make_fake_genre()
        chant_in_genre = Chant.objects.create(source=source, genre=genre)
        chant_in_another_genre = Chant.objects.create(
            source=source, genre=another_genre
        )
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "genre": genre.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_genre, chants)
        self.assertNotIn(chant_in_another_genre, chants)

    def test_filter_by_folio(self):
        source = make_fake_source()
        chant_on_folio = Chant.objects.create(source=source, folio="001r")
        chant_on_another_folio = Chant.objects.create(source=source, folio="002r")
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "folio": "001r"}
        )
        chants = response.context["chants"]
        self.assertIn(chant_on_folio, chants)
        self.assertNotIn(chant_on_another_folio, chants)

    def test_search_full_text(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=100)
        )
        search_term = get_random_search_term(chant.manuscript_full_text)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_incipit(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, incipit=make_fake_text(max_size=30))
        search_term = get_random_search_term(chant.incipit)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_full_text_std_spelling(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text_std_spelling=make_fake_text(max_size=100),
        )
        search_term = get_random_search_term(chant.manuscript_full_text_std_spelling)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_context_source(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        self.assertEqual(source, response.context["source"])

    def test_context_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_feasts_with_folios(self):
        # create a source and several chants (associated with feasts) in it
        source = make_fake_source()
        feast_1 = make_fake_feast()
        feast_2 = make_fake_feast()
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="002r", feast=feast_1)
        # request the page
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [("001r", feast_1), ("001v", feast_2), ("002r", feast_1)]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)


class ChantDetailViewTest(TestCase):
    def test_url_and_templates(self):
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_detail.html")

    def test_context_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        chant = Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_previous_and_next_folio(self):
        # create a source and several chants in it
        source = make_fake_source()
        # three folios: 001r, 001v, 002r
        chant_without_previous_folio = Chant.objects.create(source=source, folio="001r")
        chant_with_previous_and_next_folio = Chant.objects.create(
            source=source, folio="001v"
        )
        chant_without_next_folio = Chant.objects.create(source=source, folio="002v")
        # request the page and check the context variables
        # for the chant on 001r, there is no previous folio, and the next folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_previous_folio.id])
        )
        self.assertIsNone(response.context["previous_folio"])
        self.assertEqual(response.context["next_folio"], "001v")

        # for the chant on 001v, previous folio should be 001r, and next folio should be 002v
        response = self.client.get(
            reverse("chant-detail", args=[chant_with_previous_and_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001r")
        self.assertEqual(response.context["next_folio"], "002v")

        # for the chant on 002v, there is no next folio, and the previous folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001v")
        self.assertIsNone(response.context["next_folio"])


class ChantByCantusIDViewTest(TestCase):
    def test_url_and_templates(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_seq_by_cantus_id.html")

    def test_queryset(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertIn(chant, response.context["chants"])


class ChantSearchViewTest(TestCase):
    def test_url_and_templates(self):
        response = self.client.get(reverse("chant-search"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_search_by_office(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = get_random_search_term(office.name)
        response = self.client.get(reverse("chant-search"), {"office": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_genre(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(reverse("chant-search"), {"genre": genre.id})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_cantus_id(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(reverse("chant-search"), {"cantus_id": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_mode(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(reverse("chant-search"), {"mode": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_feast(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(reverse("chant-search"), {"feast": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_melody(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        chant_with_melody = Chant.objects.create(
            source=source, volpiano=make_fake_text(max_size=20)
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(reverse("chant-search"), {"melodies": "true"})
        # only chants with melodies should be in the result
        self.assertIn(chant_with_melody, response.context["chants"])
        self.assertNotIn(chant_without_melody, response.context["chants"])

    def test_keyword_search_starts_with(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        chant = Chant.objects.create(
            source=source, incipit=make_fake_text(max_size=200)
        )
        # use the beginning part of the incipit as search term
        search_term = chant.incipit[0 : random.randint(1, len(chant.incipit))]
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "starts_with"}
        )
        self.assertIn(chant, response.context["chants"])

    def test_keyword_search_contains(self):
        source = Source.objects.create(public=True, visible=True, title="a source")
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=400)
        )
        # split full text into words
        full_text_words = chant.manuscript_full_text.split(" ")
        # use a random subset of words as search term
        search_term = " ".join(
            random.choices(
                full_text_words, k=random.randint(1, max(len(full_text_words) - 1, 1))
            )
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertIn(chant, response.context["chants"])


class ChantSearchMSViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-search-ms", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_search_by_office(self):
        # source = Source.objects.create(public=True, visible=True, title="a source")
        source = make_fake_source()
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = get_random_search_term(office.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"office": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_genre(self):
        source = make_fake_source()
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"genre": genre.id}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_cantus_id(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"cantus_id": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_mode(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"mode": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_feast(self):
        source = make_fake_source()
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"feast": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_melody(self):
        source = make_fake_source()
        chant_with_melody = Chant.objects.create(
            source=source, volpiano=make_fake_text(max_size=20)
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"melodies": "true"}
        )
        # only chants with melodies should be in the result
        self.assertIn(chant_with_melody, response.context["chants"])
        self.assertNotIn(chant_without_melody, response.context["chants"])

    def test_keyword_search_starts_with(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, incipit=make_fake_text(max_size=200)
        )
        # use the beginning part of the incipit as search term
        search_term = chant.incipit[0 : random.randint(1, len(chant.incipit))]
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertIn(chant, response.context["chants"])

    def test_keyword_search_contains(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=400)
        )
        # split full text into words
        full_text_words = chant.manuscript_full_text.split(" ")
        # use a random subset of words as search term
        search_term = " ".join(
            random.choices(
                full_text_words, k=random.randint(1, max(len(full_text_words) - 1, 1))
            )
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertIn(chant, response.context["chants"])


class FullIndexViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "full_index.html")

    def test_chant_source_queryset(self):
        chant_source = make_fake_source()
        chant = Chant.objects.create(source=chant_source)
        response = self.client.get(reverse("chant-index"), {"source": chant_source.id})
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Clavis Sequentiarium"),
            title="a sequence source",
        )
        sequence = Sequence.objects.create(source=seq_source)
        response = self.client.get(reverse("chant-index"), {"source": seq_source.id})
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])

class JsonMelodyExportTest(TestCase):
    def test_json_melody_export(self):
        chants = None
        pass


class JsonNodeExportTest(TestCase):
    def test_json_node_export(self):
        pass

class JsonSourcesExportTest(TestCase):
    def test_json_sources_export(self):
        pass

class JsonNextChantsTest(TestCase):

    def test_existing_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = Chant.objects.create(
            source = fake_source_1,
            cantus_id = "2000"
        )

        fake_chant_1 = Chant.objects.create(
            source = fake_source_1,
            next_chant = fake_chant_2,
            cantus_id = "1000"
        )
        
        fake_chant_4 = Chant.objects.create(
            source = fake_source_2,
            cantus_id = "2000"
        )

        fake_chant_3 = Chant.objects.create(
            source = fake_source_2,
            next_chant = fake_chant_4,
            cantus_id = "1000"
        )

        path = reverse("json-nextchants", args=["1000"])
        response = self.client.get(path)
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {"2000": 2})

    def test_nonexistent_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = Chant.objects.create(
            source = fake_source_1,
        )
        fake_chant_1 = Chant.objects.create(
            source = fake_source_1,
            next_chant = fake_chant_2
        )
        
        fake_chant_4 = Chant.objects.create(
            source = fake_source_2,
        )
        fake_chant_3 = Chant.objects.create(
            source = fake_source_2,
            next_chant = fake_chant_4
        )

        path = reverse("json-nextchants", args=["9000"])
        response = self.client.get(reverse("json-nextchants", args=["9000"]))
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {})



class PermissionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")
        Group.objects.create(name="contributor")
        Group.objects.create(name="editor")

        for i in range(5):
            source = make_fake_source()
            for i in range(5):
                Chant.objects.create(source=source)
                Sequence.objects.create(source=source)
                
    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()

    def test_login(self):
        source = make_fake_source()
        chant = make_fake_chant()
        sequence = make_fake_sequence()

        # currently not logged in, should redirect

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertRedirects(response, f'/login/?next=/chant-create/{source.id}')       

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertRedirects(response, f'/login/?next=/chant-delete/{chant.id}')        
        
        # ChantEditVolpianoView
        response = self.client.get(f'/edit-volpiano/{source.id}')
        self.assertRedirects(response, f'/login/?next=/edit-volpiano/{source.id}')        

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertRedirects(response, f'/login/?next=/edit-sequence/{sequence.id}')        

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertRedirects(response, '/login/?next=/source-create/')    

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertRedirects(response, f'/login/?next=/edit-source/{source.id}')

        # UserSourceListView
        response = self.client.get('/my-sources/')
        self.assertRedirects(response, '/login/?next=/my-sources/')        

        # UserListView
        response = self.client.get('/users/')
        self.assertRedirects(response, '/login/?next=/users/')        

    def test_permissions_project_manager(self):
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # get random source, chant and sequence
        source = Source.objects.order_by('?').first()
        chant = Chant.objects.order_by('?').first()
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertEqual(response.status_code, 200)

        # ChantEditVolpianoView
        response = self.client.get(f'/edit-volpiano/{source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 200)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertEqual(response.status_code, 200)

    def test_permissions_contributor(self):
        contributor = Group.objects.get(name='contributor') 
        contributor.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = Chant.objects.filter(source=assigned_source).order_by('?').first()

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = Chant.objects.filter(source=source_created_by_contributor).order_by('?').first()

        # did not create the source, was not assigned the source
        restricted_source = Source.objects.filter(~Q(created_by=self.user)&~Q(id=assigned_source.id)).order_by('?').first()
        restricted_chant = Chant.objects.filter(source=restricted_source).order_by('?').first()
        
        # a random sequence
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-create/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-create/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{restricted_chant.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-delete/{chant_in_source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-delete/{chant_in_assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantEditVolpianoView
        response = self.client.get(f'/edit-volpiano/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-volpiano/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-volpiano/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-source/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-source/{assigned_source.id}')
        self.assertEqual(response.status_code, 403)

    def test_permissions_editor(self):
        editor = Group.objects.get(name='editor') 
        editor.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = Chant.objects.filter(source=assigned_source).order_by('?').first()

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = Chant.objects.filter(source=source_created_by_contributor).order_by('?').first()

        # did not create the source, was not assigned the source
        restricted_source = Source.objects.filter(~Q(created_by=self.user)&~Q(id=assigned_source.id)).order_by('?').first()
        restricted_chant = Chant.objects.filter(source=restricted_source).order_by('?').first()
        
        # a random sequence
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-create/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-create/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{restricted_chant.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-delete/{chant_in_source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-delete/{chant_in_assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantEditVolpianoView
        response = self.client.get(f'/edit-volpiano/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-volpiano/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-volpiano/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-source/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-source/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

    def test_permissions_default(self):
        self.client.login(email='test@test.com', password='pass')

        # get random source, chant and sequence
        source = Source.objects.order_by('?').first()
        chant = Chant.objects.order_by('?').first()
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertEqual(response.status_code, 403)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertEqual(response.status_code, 403)

        # ChantEditVolpianoView
        response = self.client.get(f'/edit-volpiano/{source.id}')
        self.assertEqual(response.status_code, 403)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 403)

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertEqual(response.status_code, 403)

class ChantCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_url_and_templates(self):
        source = make_fake_source()

        response = self.client.get(reverse("chant-create", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_create.html")

        response = self.client.get(reverse("chant-create", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_create_chant(self):
        source = make_fake_source()
        response = self.client.post(
            reverse("chant-create", args=[source.id]), 
            {"manuscript_full_text_std_spelling": "initial", "folio": "001r", "sequence_number": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chant-create', args=[source.id]))  
        chant = Chant.objects.first()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "initial")

class ChantDeleteViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_context(self):
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(chant, response.context["object"])

    def test_url_and_templates(self):
        chant = make_fake_chant()

        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_confirm_delete.html")

        response = self.client.get(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 302)

    def test_non_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)

class ChantEditVolpianoViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_url_and_templates(self):
        source = make_fake_source()
        Chant.objects.create(source=source)

        response = self.client.get(reverse("source-edit-volpiano", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        response = self.client.get(reverse("source-edit-volpiano", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

        # trying to access chant-edit with a source that has no chant should return 404
        source = make_fake_source()

        response = self.client.get(reverse("source-edit-volpiano", args=[source.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_update_chant(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, manuscript_full_text_std_spelling="initial")

        response = self.client.get(
            reverse('source-edit-volpiano', args=[source.id]), 
            {'pk': chant.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        response = self.client.post(
            reverse('source-edit-volpiano', args=[source.id]), 
            {'manuscript_full_text_std_spelling': 'test', 'pk': chant.id})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chant-detail', args=[chant.id]))  
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text_std_spelling, 'test')

class SequenceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_context(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(sequence, response.context["object"])

    def test_url_and_templates(self):
        sequence = make_fake_sequence()

        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sequence_edit.html")

        response = self.client.get(reverse("sequence-edit", args=[sequence.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_update_sequence(self):
        sequence = make_fake_sequence()
        response = self.client.post(
            reverse('sequence-edit', args=[sequence.id]), 
            {'title': 'test'})
        self.assertEqual(response.status_code, 302)
        sequence.refresh_from_db()
        self.assertEqual(sequence.title, 'test')

class SourceCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_url_and_templates(self):
        response = self.client.get(reverse("source-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_create_form.html")

    def test_create_source(self):
        response = self.client.post(
            reverse('source-create'), 
            {'title': 'test'})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('source-create'))       

        source = Source.objects.first()
        self.assertEqual(source.title, 'test')

class SourceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_context(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(source, response.context["object"])

    def test_url_and_templates(self):
        source = make_fake_source()

        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_edit.html")

        response = self.client.get(reverse("source-edit", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_edit_source(self):
        source = make_fake_source()

        response = self.client.post(
            reverse('source-edit', args=[source.id]), 
            {'title': 'test'})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('source-detail', args=[source.id]))       
        source.refresh_from_db()
        self.assertEqual(source.title, 'test')

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
