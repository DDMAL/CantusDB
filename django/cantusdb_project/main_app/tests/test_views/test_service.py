"""
Test views in views/service.py
"""

import random

from django.test import TestCase
from django.urls import reverse

from main_app.models import Service
from main_app.tests.make_fakes import make_fake_service


class ServiceListViewTest(TestCase):
    SERVICE_COUNT = 10
    fake_services: list[Service] = []

    @classmethod
    def setUpTestData(cls) -> None:
        cls.fake_services = [make_fake_service() for _ in range(cls.SERVICE_COUNT)]

    def test_view_url_path(self) -> None:
        response = self.client.get("/services/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self) -> None:
        response = self.client.get(reverse("service-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self) -> None:
        response = self.client.get(reverse("service-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "service_list.html")

    def test_context(self) -> None:
        response = self.client.get(reverse("service-list"))
        services = response.context["services"]
        # the list view should contain all services
        self.assertEqual(services.count(), self.SERVICE_COUNT)

    def test_json_response(self) -> None:
        response = self.client.get(
            reverse("service-list"), headers={"Accept": "application/json"}
        )
        self.assertEqual(response.headers["Content-Type"], "application/json")
        response_services = response.json()["services"]
        expected_services = [
            {
                "id": service.id,
                "name": service.name,
                "description": service.description,
            }
            for service in self.fake_services
        ]
        response_services_id_ordered = sorted(response_services, key=lambda x: x["id"])
        self.assertEqual(response_services_id_ordered, expected_services)


class ServiceDetailViewTest(TestCase):
    SERVICE_COUNT = 10
    fake_services: list[Service] = []

    @classmethod
    def setUpTestData(self) -> None:
        self.fake_services = [make_fake_service() for _ in range(self.SERVICE_COUNT)]

    def test_view_url_path(self) -> None:
        for service in Service.objects.all():
            response = self.client.get(f"/service/{service.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self) -> None:
        for service in Service.objects.all():
            response = self.client.get(reverse("service-detail", args=[service.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_context_data(self) -> None:
        for service in Service.objects.all():
            response = self.client.get(reverse("service-detail", args=[service.id]))
            self.assertTrue("service" in response.context)
            self.assertEqual(service, response.context["service"])

    def test_url_and_templates(self) -> None:
        service = random.choice(self.fake_services)
        response = self.client.get(reverse("service-detail", args=[service.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "service_detail.html")

    def test_context(self) -> None:
        service = random.choice(self.fake_services)
        response = self.client.get(reverse("service-detail", args=[service.id]))
        self.assertEqual(service, response.context["service"])

    def test_json_response(self) -> None:
        service = random.choice(self.fake_services)
        response = self.client.get(
            reverse("service-detail", args=[service.id]),
            headers={"Accept": "application/json"},
        )
        expected_service = {
            "id": service.id,
            "name": service.name,
            "description": service.description,
        }
        self.assertEqual(response.headers["Content-Type"], "application/json")
        response_service = response.json()["service"]
        self.assertEqual(response_service, expected_service)
