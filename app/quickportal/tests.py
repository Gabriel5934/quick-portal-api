
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from quickportal.models import (
    Acquirer,
    Business,
    Client,
    Fee,
    Network,
    Plan,
    PlanFee,
    PosModel,
    Status,
)


class FeeModelTests(TestCase):
    def setUp(self):
        self.acquirer = Acquirer.objects.create(name="OWN")
        self.network = Network.objects.create(name="Visa")
        self.client = Client.objects.create(
            user=User.objects.create_user(username="fee-owner")
        )

    def create_fee(self, **overrides):
        values = {
            "acquirer": self.acquirer,
            "cnae": "1234",
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

    def test_fee_can_only_have_one_plan_fee(self):
        fee = self.create_fee()
        first_plan = Plan.objects.create(name="First", client=self.client, cnae="1234")
        second_plan = Plan.objects.create(name="Second", client=self.client, cnae="1234")
        PlanFee.objects.create(plan=first_plan, fee=fee, value=Decimal("0.0010"))

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanFee.objects.create(
                plan=second_plan, fee=fee, value=Decimal("0.0020")
            )


class BusinessDetailsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="password123")
        self.plan_client = Client.objects.create(user=self.user)
        self.client.force_authenticate(self.user)
        self.business = Business.objects.create(
            document_type="CNPJ",
            document="12345678000195",
            name="Example Business",
            email="business@example.com",
            phone="11999999999",
        )
        self.plan = Plan.objects.create(
            name="Standard", client=self.plan_client, cnae="1234"
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
                "bank_code": "1",
                "branch": "1234",
                "branch_digit": "5",
                "account_number": "123456",
                "account_digit": "7",
                "cep": "01001000",
                "address_number": "100",
                "address_line2": "Suite 2",
                "projected_revenue": "1000.50",
                "commited_revenue": "800.00",
                "amount_of_terminals": 3,
                "plan": self.plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["projected_revenue"], str(Decimal("1000.50")))
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Status.PENDING)
        fetch_bank_info.assert_called_once_with("1")
        fetch_cep_info.assert_called_once_with("01001000")

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
