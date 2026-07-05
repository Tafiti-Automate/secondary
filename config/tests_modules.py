from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from academics.models import SchoolProfile
from config.models import SchoolModule
from config.modules import ACADEMIC_MODULES, FULL_MODULES, get_enabled_modules


class SchoolModuleConfigurationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.school = SchoolProfile.objects.create(name="Modular Secondary")
        self.admin = User.objects.create_user(username="admin", password="test-pass-123", role="super_admin")
        self.client.login(username="admin", password="test-pass-123")

    def test_unconfigured_school_defaults_to_academic_only(self):
        self.assertEqual(get_enabled_modules(self.school), ACADEMIC_MODULES)
        response = self.client.get(reverse("staff:list"))
        self.assertEqual(response.status_code, 403)

    def test_full_preset_enables_every_module(self):
        response = self.client.post(reverse("module-settings"), {"preset": "full"})
        self.assertRedirects(response, reverse("module-settings"))
        self.assertEqual(get_enabled_modules(self.school), FULL_MODULES)
        self.assertEqual(SchoolModule.objects.filter(school=self.school, is_enabled=True).count(), len(FULL_MODULES))
        self.assertEqual(self.client.get(reverse("staff:list")).status_code, 200)

    def test_custom_configuration_blocks_direct_url(self):
        for code in FULL_MODULES:
            SchoolModule.objects.create(school=self.school, code=code, is_enabled=code == "finance")
        self.assertEqual(self.client.get(reverse("fees:dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("finance:dashboard")).status_code, 200)
