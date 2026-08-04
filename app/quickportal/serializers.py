import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from quickportal.models import (
    Acquirer, Business, BusinessDetails, Cnae, DocumentType, Fee,
    Plan, PlanFee, PosDevice, PosModel,
)
from quickportal.services.brasil_api import fetch_bank_info, fetch_cep_info, fetch_cnpj_info


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "password"]

    def create(self, validated_data):
        username = f"user_{uuid.uuid4().hex[:12]}"

        if validated_data.get("email") is None:
            raise serializers.ValidationError({"email": "This field is required."})

        existing_email = User.objects.filter(
            email__iexact=validated_data["email"]
        ).exists()

        if existing_email:
            raise serializers.ValidationError(
                {"email": "Email address already exists."}
            )

        return User.objects.create_user(
            username=username,
            email=validated_data["email"],
            password=validated_data["password"],
        )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password", "")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email."}
            )

        # Authenticate using the real username under the hood
        credentials = {
            User.USERNAME_FIELD: user.username,
            "password": password,
        }
        authenticated_user = authenticate(**credentials)

        if authenticated_user is None:
            raise serializers.ValidationError({"password": "Incorrect password."})

        if not authenticated_user.is_active:
            raise serializers.ValidationError({"email": "This account is inactive."})

        # Let SimpleJWT build the token pair from here
        self.user = authenticated_user
        data = {}
        refresh = self.get_token(authenticated_user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        return data


class AcquirerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Acquirer
        fields = ["id", "name"]


class PosModelSerializer(serializers.ModelSerializer):
    acquirer = AcquirerSerializer(read_only=True)

    class Meta:
        model = PosModel
        fields = ["id", "model", "acquirer"]


class CnaeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cnae
        fields = ["id", "code", "description", "mcc"]


class BusinessWriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=False)
    trade_name = serializers.CharField(required=False, allow_blank=True, default="")
    landline = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Business
        fields = ["document_type", "document", "name", "trade_name", "cnae", "email", "phone", "landline"]

    @staticmethod
    def _validate_digits(value, field_name):
        if value and not value.isdigit():
            raise serializers.ValidationError(f"{field_name} must contain only digits.")
        return value

    def validate_document(self, value):
        return self._validate_digits(value, "document")

    def validate_phone(self, value):
        return self._validate_digits(value, "phone")

    def validate_landline(self, value):
        return self._validate_digits(value, "landline")

    def validate(self, attrs):
        if self.instance is not None:
            immutable_errors = {}
            for field in ("document", "document_type"):
                if field in self.initial_data and self.initial_data[field] != getattr(self.instance, field):
                    immutable_errors[field] = "This field cannot be changed after creation."
            if immutable_errors:
                raise serializers.ValidationError(immutable_errors)

        document_type = attrs.get("document_type") or getattr(self.instance, "document_type", None)
        cnae = attrs.get("cnae")

        if document_type == DocumentType.CPF:
            errors = {}
            if not attrs.get("name") and not getattr(self.instance, "name", None):
                errors["name"] = "This field is required when document_type is CPF."
            if not cnae and not getattr(self.instance, "cnae", None):
                errors["cnae"] = "This field is required when document_type is CPF."
            if errors:
                raise serializers.ValidationError(errors)
        elif document_type == DocumentType.CNPJ:
            managed_fields = ("name", "trade_name", "cnae")
            conflicting = [f for f in managed_fields if f in self.initial_data]
            if conflicting:
                raise serializers.ValidationError({
                    f: "This field is auto-populated for CNPJ and must not be provided."
                    for f in conflicting
                })
            document = attrs.get("document") or getattr(self.instance, "document", None)
            if document and self.instance is None:
                info = fetch_cnpj_info(document)
                try:
                    attrs["cnae"] = Cnae.objects.get(code=info["cod_cnae"])
                except Cnae.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {"cnae": "The CNAE returned for this CNPJ is not registered."}
                    ) from exc
                attrs["trade_name"] = info["trade_name"]
                attrs["name"] = info["name"]

        return attrs


class FeeSerializer(serializers.ModelSerializer):
    network_code = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = Fee
        fields = [
            "id",
            "acquirer",
            "cnae",
            "network",
            "network_code",
            "installments",
            "value",
        ]


class PlanFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFee
        fields = ["fee", "value"]


class PlanReadSerializer(serializers.ModelSerializer):
    fees = PlanFeeSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "description",
            "split",
            "anticipation",
            "anticipation_fee",
            "acquirer",
            "cnae",
            "fees",
            "created_at",
        ]


class PlanWriteSerializer(serializers.ModelSerializer):
    fees = PlanFeeSerializer(many=True)

    class Meta:
        model = Plan
        fields = [
            "name",
            "description",
            "split",
            "anticipation",
            "anticipation_fee",
            "acquirer",
            "cnae",
            "fees",
        ]

    def validate_fees(self, value):
        seen = set()
        for fee in value:
            key = fee["fee"].pk
            if key in seen:
                raise serializers.ValidationError(
                    f"Duplicate fee with id {key}."
                )
            seen.add(key)
        return value

    def create(self, validated_data):
        fees_data = validated_data.pop("fees")
        plan = Plan.objects.create(**validated_data)
        PlanFee.objects.bulk_create(
            [PlanFee(plan=plan, **fee) for fee in fees_data]
        )
        return plan


class BusinessReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "document_type", "document", "name", "trade_name", "cnae", "email", "phone", "landline", "status"]


class BusinessDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessDetails
        fields = [
            "id", "business", "acquirer", "bank_code", "branch", "branch_digit", "account_number",
            "account_digit", "cep", "address_number", "address_line2",
            "projected_revenue", "commited_revenue", "amount_of_terminals", "plan",
        ]

    def validate_bank_code(self, value):
        fetch_bank_info(value)
        return value

    def validate_cep(self, value):
        fetch_cep_info(value)
        return value


class PosDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosDevice
        fields = ["id", "model", "serial", "business"]
