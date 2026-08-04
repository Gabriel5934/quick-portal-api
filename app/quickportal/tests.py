
import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from quickportal.models import (
    Acquirer,
    Business,
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
            document_type="CNPJ",
            document="12345678000195",
            name="Example Business",
            email="business@example.com",
            phone="11999999999",
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

    def test_rejects_non_digit_bank_account_fields(self):
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
            document_type="CNPJ",
            document="12345678000195",
            name="Example Business",
            email="business@example.com",
            phone="11999999999",
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
