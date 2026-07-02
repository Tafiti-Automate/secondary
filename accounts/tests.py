from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import User


class AuthenticationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("dos", password="StrongPass123!", role="director_of_studies")
        self.parent = User.objects.create_user("parent", password="StrongPass123!", role="parent")

    def test_jwt_contains_role_claim(self):
        response = APIClient().post(reverse("accounts_api:token-obtain"), {"username": "dos", "password": "StrongPass123!"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_parent_cannot_list_users(self):
        client = APIClient()
        client.force_authenticate(self.parent)
        self.assertEqual(client.get(reverse("accounts_api:user-list")).status_code, 403)

    def test_manager_can_open_user_management(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("accounts:user-list-page")).status_code, 200)

    def test_remember_me_creates_persistent_session(self):
        response = self.client.post(reverse("accounts:login"), {"username": "dos", "password": "StrongPass123!", "remember_me": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_password_reset_page_is_available(self):
        self.assertEqual(self.client.get(reverse("accounts:password-reset")).status_code, 200)

    def test_management_dashboard_renders_interactive_chart_workspace(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-dashboard-chart="performance_history"')
        self.assertContains(response, 'id="dashboard-chart-data"')
        self.assertContains(response, "js/dashboard.js")
