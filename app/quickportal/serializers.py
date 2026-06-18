import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from quickportal.models import Acquirer, Business, CnaeMccMapping, Fee, MccFee, Plan, PlanFee, PosModel


FEE_NETWORK_METHODS = {
    "mastercard": ["debit", "credit", "installmentsA", "installmentsB", "installmentsC", "installmentsD"],
    "visa": ["debit", "credit", "installmentsA", "installmentsB", "installmentsC", "installmentsD"],
    "elo": ["debit", "credit", "installmentsA", "installmentsB", "installmentsC", "installmentsD"],
    "pix": ["pix"],
}


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


class CnaeMccMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CnaeMccMapping
        fields = ["id", "cod_cnae", "desc_cnae", "cod_mcc"]


class BusinessWriteSerializer(serializers.ModelSerializer):
    cod_mcc = serializers.IntegerField(write_only=True)

    class Meta:
        model = Business
        fields = ["document_type", "document", "legal_name", "trade_name", "cod_mcc", "email", "phone_number"]

    def _resolve_mcc(self, cod_mcc):
        mapping = CnaeMccMapping.objects.filter(cod_mcc=cod_mcc).first()
        if mapping is None:
            raise serializers.ValidationError({"cod_mcc": f"No MCC mapping found for MCC code '{cod_mcc}'."})
        return mapping

    def create(self, validated_data):
        cod_mcc = validated_data.pop("cod_mcc")
        validated_data["mcc"] = self._resolve_mcc(cod_mcc)
        return Business.objects.create(**validated_data)

    def update(self, instance, validated_data):
        cod_mcc = validated_data.pop("cod_mcc", None)
        if cod_mcc is not None:
            validated_data["mcc"] = self._resolve_mcc(cod_mcc)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FeeSerializer(serializers.Serializer):
    def to_representation(self, instance: Fee):
        return {
            network: {
                method: getattr(instance, f"{network}{method[0].upper()}{method[1:]}")
                for method in methods
            }
            for network, methods in FEE_NETWORK_METHODS.items()
        }


class MccListSerializer(serializers.ModelSerializer):
    class Meta:
        model = MccFee
        fields = ["id", "mcc"]


class MccFeeSerializer(serializers.ModelSerializer):
    fee = FeeSerializer(read_only=True)

    class Meta:
        model = MccFee
        fields = ["id", "mcc", "fee"]


class PlanFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFee
        fields = ["network", "payment_type", "commission"]


class PlanReadSerializer(serializers.ModelSerializer):
    mcc = MccListSerializer(read_only=True)
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
            "mcc",
            "fees",
            "created_at",
        ]


class PlanWriteSerializer(serializers.ModelSerializer):
    mcc_id = serializers.PrimaryKeyRelatedField(
        source="mcc", queryset=MccFee.objects.all(), write_only=True
    )
    fees = PlanFeeSerializer(many=True)

    class Meta:
        model = Plan
        fields = [
            "name",
            "description",
            "split",
            "anticipation",
            "anticipation_fee",
            "mcc_id",
            "fees",
        ]

    def validate_fees(self, value):
        seen = set()
        for fee in value:
            key = (fee["network"], fee["payment_type"])
            if key in seen:
                raise serializers.ValidationError(
                    f"Duplicate fee for {fee['network']} / {fee['payment_type']}."
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
    mcc = CnaeMccMappingSerializer(read_only=True)

    class Meta:
        model = Business
        fields = ["id", "document_type", "document", "legal_name", "trade_name", "mcc", "email", "phone_number", "own_status"]
