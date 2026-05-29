from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from quickportal.models import Acquirer, CnaeMccMapping, PosModel
from quickportal.serializers import (
    AcquirerSerializer,
    CnaeMccMappingSerializer,
    EmailTokenObtainPairSerializer,
    PosModelSerializer,
    UserCreateSerializer,
)
from quickportal.services.own_auth import get_own_token, OwnAuthError
from quickportal.services.own_merchant import register_merchant, MerchantRegistrationError


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class OwnAuthTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = get_own_token()
        except OwnAuthError as exc:
            return Response(
                {"error": "own_auth_failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        masked = token[:10] + "..." if len(token) > 10 else token
        return Response(
            {
                "status": "authenticated",
                "token_preview": masked,
                "message": "OWN Financial token acquired successfully.",
            },
            status=status.HTTP_200_OK,
        )


class MerchantRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = register_merchant(request.data)
        except OwnAuthError as exc:
            return Response(
                {"error": "own_auth_failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except MerchantRegistrationError as exc:
            error_status = (
                status.HTTP_502_BAD_GATEWAY
                if exc.status_code is None
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(
                {
                    "error": "merchant_registration_failed",
                    "detail": str(exc),
                    "upstream_status": exc.status_code,
                    "upstream_body": exc.response_body,
                },
                status=error_status,
            )

        return Response(result, status=status.HTTP_200_OK)


class AcquirerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        acquirers = Acquirer.objects.all()
        serializer = AcquirerSerializer(acquirers, many=True)
        return Response(serializer.data)


class PosModelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pos_models = PosModel.objects.select_related("acquirer").all()
        serializer = PosModelSerializer(pos_models, many=True)
        return Response(serializer.data)


class CnaeMccMappingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mappings = CnaeMccMapping.objects.all()
        serializer = CnaeMccMappingSerializer(mappings, many=True)
        return Response(serializer.data)
