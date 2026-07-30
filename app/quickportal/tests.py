
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from quickportal.models import Acquirer, Business, Fee, MccFee, Plan, PosModel, Status


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
        fee = Fee.objects.create()
        mcc = MccFee.objects.create(mcc="1234", fee=fee)
        self.plan = Plan.objects.create(name="Standard", mcc=mcc)

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
