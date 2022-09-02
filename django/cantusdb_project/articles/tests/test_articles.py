from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from articles.models import Article
from users.models import User
from main_app.models import Indexer
from main_app.tests.make_fakes import (
    make_fake_text,
    make_fake_indexer,
)

# run with `python -Wa manage.py test articles.tests.test_articles.py`
# the -Wa flag tells Python to display deprecation warnings

def make_fake_user():
    fake_email = "{f}@{g}.com".format(
        f=make_fake_text(12),
        g=make_fake_text(12),
    )
    user = get_user_model().objects.create(email=fake_email)
    return user

def make_fake_article(user=None):
    if user is None:
        user=make_fake_user()
    article = Article.objects.create(
        title=make_fake_text(max_size=12),
        author=make_fake_indexer(),
        created_by=user,
    )
    return article


class ArticleListViewTest(TestCase):
    def setUp(self):
        fake_user = make_fake_user()
        for i in range(10):
            make_fake_article()

    def test_view_url_path(self):
        for article in Article.objects.all():
            response = self.client.get(f"/article/{article.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for article in Article.objects.all():
            response = self.client.get(reverse("article-detail", args=[article.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_context_data(self):
        for article in Article.objects.all():
            response = self.client.get(reverse("article-detail", args=[article.id]))
            self.assertTrue("article" in response.context)
            self.assertEqual(article, response.context["article"])

    def test_url_and_templates(self):
        """Test the url and templates used"""
        article = make_fake_article()
        response = self.client.get(reverse("article-detail", args=[article.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "article_detail.html")

    def test_context(self):
        article = make_fake_article()
        response = self.client.get(reverse("article-detail", args=[article.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(article, response.context["article"])

