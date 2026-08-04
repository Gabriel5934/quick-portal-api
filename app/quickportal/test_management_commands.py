from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase


class EnsureDevUserCommandTests(TestCase):
    email = "root@email.com"

    def run_command(self, password):
        output = StringIO()
        call_command("ensure_dev_user", self.email, password, stdout=output)
        return output.getvalue()

    def test_creates_active_user_with_supplied_credentials(self):
        output = self.run_command("first-password")

        user = User.objects.get(email=self.email)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("first-password"))
        self.assertIn("Created development user", output)

    def test_updates_existing_user_credentials(self):
        user = User.objects.create_user(
            username="existing-user",
            email=self.email.upper(),
            password="old-password",
            is_active=False,
        )

        output = self.run_command("new-password")

        user.refresh_from_db()
        self.assertEqual(user.email, self.email)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("new-password"))
        self.assertEqual(User.objects.filter(email__iexact=self.email).count(), 1)
        self.assertIn("Updated development user", output)
