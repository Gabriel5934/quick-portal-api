from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import TestCase

from quickportal.models import (
    Business,
    BusinessDetails,
    BusinessMembership,
    BusinessRole,
    BusinessType,
)


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


class GenerateBusinessHierarchyCommandTests(TestCase):
    def test_generates_expected_hierarchy_and_store_details(self):
        output = StringIO()

        call_command("generate_business_hierarchy", seed=42, stdout=output)

        self.assertEqual(Business.objects.count(), 3)
        reseller = Business.objects.get(type=BusinessType.RESELLER)
        re_reseller = Business.objects.get(type=BusinessType.RE_RESELLER)
        store = Business.objects.get(type=BusinessType.STORE)
        self.assertIsNone(reseller.parent)
        self.assertEqual(re_reseller.parent, reseller)
        self.assertEqual(store.parent, re_reseller)
        self.assertFalse(hasattr(reseller, "details"))
        self.assertFalse(hasattr(re_reseller, "details"))
        self.assertEqual(BusinessDetails.objects.get().business, store)
        self.assertEqual(store.cnae, store.details.plan.cnae)
        self.assertRegex(reseller.document, r"^\d{14}$")
        self.assertIn("Generated business hierarchy", output.getvalue())

    def test_optionally_grants_admin_membership(self):
        user = User.objects.create_user(
            username="hierarchy-admin", email="admin@example.com"
        )

        call_command(
            "generate_business_hierarchy",
            seed=7,
            admin_email="ADMIN@example.com",
            stdout=StringIO(),
        )

        membership = BusinessMembership.objects.get()
        self.assertEqual(membership.user, user)
        self.assertEqual(membership.business.type, BusinessType.RESELLER)
        self.assertEqual(membership.role, BusinessRole.ADMIN)


class CreateBusinessCommandTests(TestCase):
    def run_command(self, *args, **options):
        output = StringIO()
        call_command("create_business", *args, stdout=output, **options)
        return output.getvalue()

    def test_creates_root_reseller_without_parent_id(self):
        output = self.run_command(seed=1)

        business = Business.objects.get()
        self.assertEqual(business.type, BusinessType.RESELLER)
        self.assertIsNone(business.parent)
        self.assertIn("Created Reseller", output)

    def test_creates_re_reseller_for_reseller_id(self):
        self.run_command(seed=1)
        reseller = Business.objects.get()

        self.run_command(reseller.id, seed=2)

        child = Business.objects.exclude(pk=reseller.pk).get()
        self.assertEqual(child.type, BusinessType.RE_RESELLER)
        self.assertEqual(child.parent, reseller)

    def test_store_flag_creates_store_for_reseller_id(self):
        self.run_command(seed=1)
        reseller = Business.objects.get()

        self.run_command(reseller.id, store=True, seed=2)

        child = Business.objects.exclude(pk=reseller.pk).get()
        self.assertEqual(child.type, BusinessType.STORE)
        self.assertEqual(child.parent, reseller)

    def test_creates_store_for_re_reseller_id(self):
        self.run_command(seed=1)
        reseller = Business.objects.get()
        self.run_command(reseller.id, seed=2)
        re_reseller = Business.objects.get(type=BusinessType.RE_RESELLER)

        self.run_command(re_reseller.id, seed=3)

        store = Business.objects.get(type=BusinessType.STORE)
        self.assertEqual(store.parent, re_reseller)

    def test_rejects_store_parent_and_store_flag_without_parent(self):
        self.run_command(seed=1)
        reseller = Business.objects.get()
        self.run_command(reseller.id, store=True, seed=2)
        store = Business.objects.get(type=BusinessType.STORE)

        with self.assertRaisesMessage(CommandError, "cannot have child"):
            self.run_command(store.id, seed=3)
        with self.assertRaisesMessage(CommandError, "requires a reseller"):
            self.run_command(store=True, seed=4)


class CreateRootBusinessCommandTests(TestCase):
    def test_creates_root_reseller(self):
        output = StringIO()

        call_command("create_root_business", "reseller", seed=11, stdout=output)

        business = Business.objects.get()
        self.assertEqual(business.type, BusinessType.RESELLER)
        self.assertIsNone(business.parent)
        self.assertIn("Created root Reseller", output.getvalue())

    def test_creates_root_store(self):
        output = StringIO()

        call_command("create_root_business", "store", seed=12, stdout=output)

        business = Business.objects.get()
        self.assertEqual(business.type, BusinessType.STORE)
        self.assertIsNone(business.parent)
        self.assertIn("Created root Store", output.getvalue())


class ListBusinessesCommandTests(TestCase):
    def test_prints_empty_state(self):
        output = StringIO()

        call_command("list_businesses", stdout=output)

        self.assertEqual(output.getvalue(), "No businesses found.\n")

    def test_prints_businesses_as_an_ordered_formatted_table(self):
        call_command("generate_business_hierarchy", seed=42, stdout=StringIO())
        reseller = Business.objects.get(type=BusinessType.RESELLER)
        re_reseller = Business.objects.get(type=BusinessType.RE_RESELLER)
        output = StringIO()

        call_command("list_businesses", stdout=output)

        table = output.getvalue()
        self.assertIn("| ID", table)
        self.assertIn("| TYPE", table)
        self.assertIn("| PAR", table)
        self.assertIn("| DOC", table)
        self.assertIn("| NAME", table)
        self.assertIn("| STATUS", table)
        self.assertIn(reseller.name[:11], table)
        self.assertIn(
            f"| {re_reseller.id}", table,
        )
        self.assertIn(str(reseller.id), table)
        self.assertTrue(all(len(line) <= 120 for line in table.splitlines()))
        self.assertTrue(table.rstrip().endswith("3 business(es)."))
