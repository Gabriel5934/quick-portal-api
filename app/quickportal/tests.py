
import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from quickportal.models import (
    Acquirer,
    Business,
    BusinessMembership,
    BusinessRole,
    BusinessType,
    Cnae,
    Fee,
    Network,
    Plan,
    PlanFee,
    PosModel,
    Status,
)
from quickportal.services.brasil_api import BrasilApiError


class PopulateCnaesCommandTests(TestCase):
    def test_loads_custom_keys_and_normalizes_codes(self):
        with TemporaryDirectory() as directory:
            file_path = Path(directory) / "cnaes.json"
            file_path.write_text(
                json.dumps(
                    [
                        {"customCode": "47.11-3/02", "customDescription": "Retail", "customMcc": 5411},
                        {"customCode": "62.01-5/01", "customDescription": "Software", "customMcc": "5734"},
                    ]
                ),
                encoding="utf-8",
            )

            call_command(
                "populate_cnaes",
                "customCode",
                "customDescription",
                "customMcc",
                file=str(file_path),
                stdout=StringIO(),
            )

        self.assertQuerySetEqual(
            Cnae.objects.order_by("code").values_list("code", "description", "mcc"),
            [("4711302", "Retail", "5411"), ("6201501", "Software", "5734")],
        )


class PopulateNetworksCommandTests(TestCase):
    def test_creates_and_updates_network_colors_without_duplicates(self):
        existing = Network.objects.create(name="visa", color="#000000")
        with TemporaryDirectory() as directory:
            file_path = Path(directory) / "networks.json"
            file_path.write_text(
                json.dumps(
                    [
                        {"name": "Visa", "color": "#1b34cb"},
                        {"name": "Pix", "color": "#39b4aa"},
                        {"color": "#ffffff"},
                    ]
                ),
                encoding="utf-8",
            )

            call_command(
                "populate_networks", file=str(file_path), stdout=StringIO()
            )

        self.assertEqual(Network.objects.filter(name__iexact="visa").count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Visa")
        self.assertEqual(existing.color, "#1b34cb")
        self.assertEqual(Network.objects.get(name="Pix").color, "#39b4aa")

    def test_rejects_invalid_color(self):
        with TemporaryDirectory() as directory:
            file_path = Path(directory) / "networks.json"
            file_path.write_text(
                json.dumps([{"name": "Visa", "color": "blue"}]),
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "Invalid color for network Visa"):
                call_command(
                    "populate_networks", file=str(file_path), stdout=StringIO()
                )


class CreateFeesCommandTests(TestCase):
    def test_creates_expected_fee_matrix(self):
        acquirer = Acquirer.objects.create(name="OWN")
        cnae = Cnae.objects.create(
            code="4711302", description="Retail", mcc="5411"
        )

        call_command(
            "create_fees",
            "OWN",
            "47.11-3/02",
            stdout=StringIO(),
        )

        fees = Fee.objects.filter(acquirer=acquirer, cnae=cnae)
        self.assertEqual(fees.count(), 68)
        for network_name in ("visa", "mastercard", "elo"):
            self.assertEqual(
                set(
                    fees.filter(network__name__iexact=network_name).values_list(
                        "installments", flat=True
                    )
                ),
                set(range(22)),
            )
        self.assertTrue(
            fees.filter(network__name__iexact="pix", installments=-1).exists()
        )
        self.assertTrue(
            fees.filter(network__name__iexact="acquirer", installments=-2).exists()
        )
        self.assertFalse(
            fees.exclude(value__gte=Decimal("0.01"), value__lte=Decimal("0.05")).exists()
        )


class NetworkListApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="network-reader")
        self.client.force_authenticate(self.user)

    def test_returns_network_names_and_colors(self):
        visa = Network.objects.create(name="Visa", color="#1b34cb")

        response = self.client.get(reverse("network_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [{"id": visa.id, "name": "Visa", "color": "#1b34cb"}],
        )


class CnaeListApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cnae-reader")
        self.client.force_authenticate(self.user)

    def test_returns_all_cnaes_ordered_by_code(self):
        software = Cnae.objects.create(code="6201501", description="Software", mcc="5734")
        retail = Cnae.objects.create(code="4711302", description="Retail", mcc="5411")

        response = self.client.get(reverse("cnae_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {"id": retail.id, "code": "4711302", "description": "Retail", "mcc": "5411"},
                {"id": software.id, "code": "6201501", "description": "Software", "mcc": "5734"},
            ],
        )

    def test_returns_only_cnaes_with_fees(self):
        retail = Cnae.objects.create(code="4711302", description="Retail", mcc="5411")
        software = Cnae.objects.create(code="6201501", description="Software", mcc="5734")
        acquirer = Acquirer.objects.create(name="OWN")
        other_acquirer = Acquirer.objects.create(name="OTHER")
        network = Network.objects.create(name="visa")
        Fee.objects.create(
            acquirer=acquirer,
            cnae=retail,
            network=network,
            installments=0,
            value=Decimal("0.0123"),
        )
        Fee.objects.create(
            acquirer=other_acquirer,
            cnae=software,
            network=network,
            installments=0,
            value=Decimal("0.0123"),
        )

        response = self.client.get(
            reverse("cnaes_with_fees_list"), {"acquirer": acquirer.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [{"id": retail.id, "code": "4711302", "description": "Retail", "mcc": "5411"}],
        )

    def test_cnaes_with_fees_requires_acquirer(self):
        response = self.client.get(reverse("cnaes_with_fees_list"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cnaes_with_fees_returns_not_found_for_unknown_acquirer(self):
        response = self.client.get(
            reverse("cnaes_with_fees_list"), {"acquirer": "unknown"}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FeeListApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fee-reader")
        self.client.force_authenticate(self.user)
        self.acquirer = Acquirer.objects.create(name="OWN")
        self.visa = Network.objects.create(name="visa")
        self.retail = Cnae.objects.create(
            code="4711302", description="Retail", mcc="5411"
        )
        self.software = Cnae.objects.create(
            code="6201501", description="Software", mcc="5734"
        )

    def test_returns_fees_for_acquirer_and_normalized_cnae(self):
        matching_fee = Fee.objects.create(
            acquirer=self.acquirer,
            cnae=self.retail,
            network=self.visa,
            installments=0,
            value=Decimal("0.0123"),
        )
        Fee.objects.create(
            acquirer=self.acquirer,
            cnae=self.software,
            network=self.visa,
            installments=0,
            value=Decimal("0.0250"),
        )

        response = self.client.get(
            reverse("fee_list"),
            {"acquirer": "OWN", "cnae": "47.11-3/02"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], matching_fee.id)

    def test_requires_acquirer_and_cnae(self):
        response = self.client.get(reverse("fee_list"), {"acquirer": "OWN"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FeeModelTests(TestCase):
    def setUp(self):
        self.acquirer = Acquirer.objects.create(name="OWN")
        self.network = Network.objects.create(name="Visa")
        self.cnae = Cnae.objects.create(
            code="1234", description="Test CNAE", mcc="1234"
        )

    def create_fee(self, **overrides):
        values = {
            "acquirer": self.acquirer,
            "cnae": self.cnae,
            "network": self.network,
            "installments": -1,
            "value": Decimal("0.0092"),
        }
        values.update(overrides)
        return Fee.objects.create(**values)

    def test_allows_negative_installments(self):
        fee = self.create_fee()
        self.assertEqual(fee.installments, -1)

    def test_fee_dimensions_are_unique(self):
        self.create_fee()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_fee(value=Decimal("0.0100"))

    def test_plan_and_fee_combination_is_unique(self):
        fee = self.create_fee()
        first_plan = Plan.objects.create(
            name="First", acquirer=self.acquirer, cnae=self.cnae
        )
        second_plan = Plan.objects.create(
            name="Second", acquirer=self.acquirer, cnae=self.cnae
        )
        PlanFee.objects.create(plan=first_plan, fee=fee, value=Decimal("0.0010"))
        PlanFee.objects.create(plan=second_plan, fee=fee, value=Decimal("0.0020"))

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanFee.objects.create(
                plan=first_plan, fee=fee, value=Decimal("0.0030")
            )


class PlanApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="plan-reader")
        self.client.force_authenticate(self.user)
        self.cnae = Cnae.objects.create(
            code="4711302", description="Retail", mcc="5411"
        )
        self.plan = Plan.objects.create(name="Standard", cnae=self.cnae)

    def test_list_includes_cnae_code(self):
        response = self.client.get(reverse("plan_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["cnae"], self.cnae.id)
        self.assertEqual(response.data[0]["cnae_code"], "4711302")

    def test_detail_includes_cnae_code(self):
        response = self.client.get(reverse("plan_detail", args=[self.plan.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cnae_code"], "4711302")


class BusinessDetailsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="password123")
        self.client.force_authenticate(self.user)
        self.business = Business.objects.create(
            type=BusinessType.STORE,
            document_type="CNPJ",
            document="12345678000195",
            name="Example Business",
            email="business@example.com",
            phone="11999999999",
        )
        BusinessMembership.objects.create(
            user=self.user, business=self.business, role=BusinessRole.MANAGER
        )
        self.cnae = Cnae.objects.create(
            code="1234", description="Test CNAE", mcc="1234"
        )
        self.acquirer = Acquirer.objects.create(name="OWN")
        self.plan = Plan.objects.create(
            name="Standard", acquirer=self.acquirer, cnae=self.cnae
        )

    @patch("quickportal.serializers.fetch_cep_info")
    @patch("quickportal.serializers.fetch_bank_info")
    def test_creates_business_details_after_external_validation(
        self, fetch_bank_info, fetch_cep_info
    ):
        response = self.client.post(
            reverse("business_details_list_create"),
            {
                "business": self.business.id,
                "acquirer": self.acquirer.id,
                "bank_code": "102",
                "branch": "1234",
                "branch_digit": "5",
                "account_number": "123456",
                "account_digit": "7",
                "cep": "12244867",
                "address_number": "82",
                "address_line2": "Floradas da Serra",
                "projected_revenue": 10,
                "commited_revenue": 10,
                "amount_of_terminals": 2,
                "plan": self.plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["acquirer"], self.acquirer.id)
        self.assertEqual(response.data["projected_revenue"], str(Decimal("10.00")))
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Status.PENDING)
        fetch_bank_info.assert_called_once_with("102")
        fetch_cep_info.assert_called_once_with("12244867")

    @patch("quickportal.serializers.fetch_cep_info")
    @patch("quickportal.serializers.fetch_bank_info")
    def test_returns_field_error_for_invalid_bank_code(
        self, fetch_bank_info, _fetch_cep_info
    ):
        fetch_bank_info.side_effect = BrasilApiError(
            "Brasil API returned status 404", status_code=404, resource="bank"
        )

        response = self.client.post(
            reverse("business_details_list_create"),
            {
                "business": self.business.id,
                "bank_code": "999",
                "branch": "1234",
                "branch_digit": "5",
                "account_number": "123456",
                "account_digit": "7",
                "cep": "01001000",
                "address_number": "100",
                "projected_revenue": "1000.50",
                "commited_revenue": "800.00",
                "amount_of_terminals": 3,
                "plan": self.plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {"bank_code": ["Brasil API returned status 404"]}
        )

    @patch("quickportal.serializers.fetch_cep_info")
    @patch("quickportal.serializers.fetch_bank_info")
    def test_rejects_non_digit_bank_account_fields(
        self, _fetch_bank_info, _fetch_cep_info
    ):
        response = self.client.post(
            reverse("business_details_list_create"),
            {
                "business": self.business.id,
                "bank_code": "1",
                "branch": "12A4",
                "branch_digit": "5",
                "account_number": "123456",
                "account_digit": "7",
                "cep": "01001000",
                "address_number": "100",
                "projected_revenue": "1000.50",
                "commited_revenue": "800.00",
                "amount_of_terminals": 3,
                "plan": self.plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", response.data)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Status.NOT_STARTED)


class PosDeviceApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="password123")
        self.client.force_authenticate(self.user)
        self.business = Business.objects.create(
            type=BusinessType.STORE,
            document_type="CNPJ",
            document="12345678000195",
            name="Example Business",
            email="business@example.com",
            phone="11999999999",
        )
        BusinessMembership.objects.create(
            user=self.user, business=self.business, role=BusinessRole.MANAGER
        )
        acquirer = Acquirer.objects.create(name="Acquirer")
        self.pos_model = PosModel.objects.create(model="PAX A920", acquirer=acquirer)

    def test_creates_pos_device(self):
        response = self.client.post(
            reverse("pos_device_list_create"),
            {"model": self.pos_model.id, "serial": "123456789", "business": self.business.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["serial"], "123456789")


class BusinessHierarchyModelTests(TestCase):
    def make_business(self, name, business_type, parent=None):
        return Business(
            type=business_type,
            parent=parent,
            document_type="CPF",
            document=f"{Business.objects.count() + 1:011d}",
            name=name,
            email=f"{name.lower().replace(' ', '-')}@example.com",
            phone="11999999999",
        )

    def test_accepts_supported_hierarchy_and_root_store(self):
        reseller = self.make_business("Reseller", BusinessType.RESELLER)
        reseller.full_clean()
        reseller.save()
        re_reseller = self.make_business(
            "Re Reseller", BusinessType.RE_RESELLER, reseller
        )
        re_reseller.full_clean()
        re_reseller.save()
        for parent in (None, reseller, re_reseller):
            store = self.make_business("Store", BusinessType.STORE, parent)
            store.full_clean()

    def test_rejects_invalid_parent_type_combinations(self):
        reseller = self.make_business("Reseller", BusinessType.RESELLER)
        reseller.save()
        store = self.make_business("Store", BusinessType.STORE)
        store.save()
        invalid = [
            self.make_business("Nested reseller", BusinessType.RESELLER, reseller),
            self.make_business("Root re reseller", BusinessType.RE_RESELLER),
            self.make_business("Re reseller", BusinessType.RE_RESELLER, store),
            self.make_business("Nested store", BusinessType.STORE, store),
        ]
        for business in invalid:
            with self.subTest(name=business.name), self.assertRaises(ValidationError):
                business.full_clean()

    def test_rejects_self_parent_and_duplicate_membership(self):
        business = self.make_business("Store", BusinessType.STORE)
        business.save()
        business.parent = business
        with self.assertRaises(ValidationError):
            business.full_clean()

        user = User.objects.create_user(username="member")
        BusinessMembership.objects.create(
            user=user, business=business, role=BusinessRole.VIEWER
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusinessMembership.objects.create(
                user=user, business=business, role=BusinessRole.ADMIN
            )

    def test_parent_delete_is_protected_and_user_delete_cascades_membership(self):
        reseller = self.make_business("Reseller", BusinessType.RESELLER)
        reseller.full_clean()
        reseller.save()
        store = self.make_business("Store", BusinessType.STORE, reseller)
        store.full_clean()
        store.save()
        with self.assertRaises(ProtectedError):
            reseller.delete()

        user = User.objects.create_user(username="member")
        BusinessMembership.objects.create(
            user=user, business=store, role=BusinessRole.VIEWER
        )
        user.delete()
        self.assertTrue(Business.objects.filter(pk=store.pk).exists())
        self.assertFalse(BusinessMembership.objects.exists())


class BusinessAuthorizationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tenant-user")
        self.client.force_authenticate(self.user)
        self.reseller = self.make_business("Reseller", BusinessType.RESELLER)
        self.re_reseller = self.make_business(
            "Re Reseller", BusinessType.RE_RESELLER, self.reseller
        )
        self.direct_store = self.make_business(
            "Direct Store", BusinessType.STORE, self.reseller
        )
        self.nested_store = self.make_business(
            "Nested Store", BusinessType.STORE, self.re_reseller
        )
        self.unrelated_store = self.make_business(
            "Unrelated Store", BusinessType.STORE
        )

    @staticmethod
    def make_business(name, business_type, parent=None):
        number = Business.objects.count() + 1
        business = Business(
            type=business_type,
            parent=parent,
            document_type="CNPJ",
            document=f"{number:014d}",
            name=name,
            email=f"business-{number}@example.com",
            phone="11999999999",
        )
        business.full_clean()
        business.save()
        return business

    def test_delete_business_with_children_returns_conflict(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.ADMIN
        )

        response = self.client.delete(
            reverse("business_detail", args=[self.reseller.id])
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data["detail"],
            "The business cannot be deleted while it has child businesses.",
        )
        self.assertTrue(Business.objects.filter(pk=self.reseller.pk).exists())

    def test_reseller_membership_scopes_list_and_counts_to_descendants(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.VIEWER
        )
        response = self.client.get(reverse("business_list_create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(response.data["count_by_status"], {Status.NOT_STARTED: 4})
        self.assertSetEqual(
            {item["id"] for item in response.data["results"]},
            {
                self.reseller.id,
                self.re_reseller.id,
                self.direct_store.id,
                self.nested_store.id,
            },
        )

    def test_business_list_can_be_filtered_to_direct_children(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.VIEWER
        )

        response = self.client.get(
            reverse("business_list_create"), {"parent": self.reseller.id}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertSetEqual(
            {item["id"] for item in response.data["results"]},
            {self.re_reseller.id, self.direct_store.id},
        )

    def test_re_reseller_and_store_memberships_only_see_their_branches(self):
        membership = BusinessMembership.objects.create(
            user=self.user,
            business=self.re_reseller,
            role=BusinessRole.VIEWER,
        )
        response = self.client.get(reverse("business_list_create"))
        self.assertSetEqual(
            {item["id"] for item in response.data["results"]},
            {self.re_reseller.id, self.nested_store.id},
        )
        membership.business = self.direct_store
        membership.save(update_fields=["business"])
        response = self.client.get(reverse("business_list_create"))
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.direct_store.id],
        )

    def test_viewer_cannot_write_and_unrelated_detail_is_hidden(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.VIEWER
        )
        response = self.client.patch(
            reverse("business_detail", args=[self.direct_store.id]),
            {"phone": "11888888888"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(
            reverse("business_detail", args=[self.unrelated_store.id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_overlapping_memberships_use_most_permissive_role(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.VIEWER
        )
        BusinessMembership.objects.create(
            user=self.user, business=self.direct_store, role=BusinessRole.MANAGER
        )
        response = self.client.patch(
            reverse("business_detail", args=[self.direct_store.id]),
            {"phone": "11888888888"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_manages_descendant_memberships_but_not_final_root_admin(self):
        root_admin = BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.ADMIN
        )
        new_user = User.objects.create_user(
            username="new-member", email="new@example.com"
        )
        response = self.client.post(
            reverse("business_membership_list_create", args=[self.direct_store.id]),
            {"user": new_user.id, "role": BusinessRole.VIEWER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.delete(
            reverse(
                "business_membership_detail",
                args=[self.reseller.id, root_admin.id],
            )
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superuser_bypasses_scope_but_staff_does_not(self):
        superuser = User.objects.create_superuser(
            username="super", email="super@example.com", password="password"
        )
        self.client.force_authenticate(superuser)
        response = self.client.get(reverse("business_list_create"))
        self.assertEqual(response.data["count"], 5)

        staff = User.objects.create_user(username="staff", is_staff=True)
        self.client.force_authenticate(staff)
        response = self.client.get(reverse("business_list_create"))
        self.assertEqual(response.data["count"], 0)

    def test_pos_device_rejects_non_store_business(self):
        BusinessMembership.objects.create(
            user=self.user, business=self.reseller, role=BusinessRole.ADMIN
        )
        acquirer = Acquirer.objects.create(name="POS acquirer")
        pos_model = PosModel.objects.create(model="PAX", acquirer=acquirer)
        response = self.client.post(
            reverse("pos_device_list_create"),
            {
                "model": pos_model.id,
                "serial": "123456",
                "business": self.reseller.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business", response.data)

    @patch("quickportal.views.register_merchant")
    def test_merchant_registration_requires_store_write_access_and_strips_business(
        self, register_merchant
    ):
        register_merchant.return_value = {"status": "ok"}
        BusinessMembership.objects.create(
            user=self.user,
            business=self.direct_store,
            role=BusinessRole.MANAGER,
        )
        response = self.client.post(
            reverse("own_merchant_register"),
            {"business": self.direct_store.id, "merchant": "payload"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        register_merchant.assert_called_once_with({"merchant": "payload"})

        BusinessMembership.objects.filter(user=self.user).update(
            role=BusinessRole.VIEWER
        )
        response = self.client.post(
            reverse("own_merchant_register"),
            {"business": self.direct_store.id, "merchant": "payload"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
