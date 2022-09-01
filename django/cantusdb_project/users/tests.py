from django.test import TestCase
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

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