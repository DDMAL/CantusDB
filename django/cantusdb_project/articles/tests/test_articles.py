from django.test import TestCase
from django.urls import reverse
from articles.models import Article
from faker import Faker
from main_app.tests.make_fakes import (
    make_fake_user,
)

# run with `python -Wa manage.py test articles.tests.test_articles`
# the -Wa flag tells Python to display deprecation warnings

# Create a Faker instance with locale set to Latin
faker = Faker("la")

def make_fake_article(user=None):
    if user is None:
        user = make_fake_user()
    article = Article.objects.create(
        # updated to use Faker (previously called method from make_fakes that no longer exists)
        title=faker.sentence(),
        author=make_fake_user(),
    )
    return article


class ArticleListViewTest(TestCase):
    def setUp(self):
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
