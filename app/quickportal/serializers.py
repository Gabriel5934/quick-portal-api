import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from quickportal.models import Acquirer, CnaeMccMapping, PosModel


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
