from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from quickportal.models import (
    Acquirer,
    Business,
    BusinessDetails,
    Cnae,
    Fee,
    Plan,
    PosDevice,
    PosModel,
    Status,
)
from quickportal.serializers import (
    AcquirerSerializer,
    BusinessReadSerializer,
    BusinessDetailsSerializer,
    BusinessWriteSerializer,
    CnaeSerializer,
    EmailTokenObtainPairSerializer,
    FeeSerializer,
    PlanReadSerializer,
    PlanWriteSerializer,
    PosDeviceSerializer,
    PosModelSerializer,
    UserCreateSerializer,
)
from quickportal.services.brasil_api import BrasilApiError
from quickportal.services.own_auth import get_own_token, OwnAuthError
from quickportal.services.own_merchant import register_merchant, MerchantRegistrationError


def _brasil_api_error_response(exc: BrasilApiError) -> Response:
    if exc.status_code and 400 <= exc.status_code < 500:
        return Response(
            {"error": f"invalid_{exc.resource or 'brasil_api_resource'}", "detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"error": "brasil_api_failed", "detail": str(exc)},
        status=status.HTTP_502_BAD_GATEWAY,
    )


def _get_object_or_none(model, pk):
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None


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


class CnaeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cnaes = Cnae.objects.order_by("code")
        return Response(CnaeSerializer(cnaes, many=True).data)


class CnaesWithFeesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        acquirer_value = request.query_params.get("acquirer", "").strip()
        if not acquirer_value:
            return Response(
                {"detail": "The acquirer query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        acquirer = None
        if acquirer_value.isdigit():
            acquirer = Acquirer.objects.filter(pk=int(acquirer_value)).first()
        if acquirer is None:
            acquirer = Acquirer.objects.filter(name__iexact=acquirer_value).first()
        if acquirer is None:
            return Response(
                {"detail": "Acquirer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        fee_exists = Fee.objects.filter(
            acquirer=acquirer,
            cnae=OuterRef("pk"),
        )
        cnaes = (
            Cnae.objects.annotate(has_fees=Exists(fee_exists))
            .filter(has_fees=True)
            .order_by("code")
        )
        return Response(CnaeSerializer(cnaes, many=True).data)


class FeeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        acquirer_value = request.query_params.get("acquirer", "").strip()
        cnae_value = request.query_params.get("cnae", "").strip()
        if not acquirer_value or not cnae_value:
            return Response(
                {"detail": "Both acquirer and cnae query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        acquirer = None
        if acquirer_value.isdigit():
            acquirer = Acquirer.objects.filter(pk=int(acquirer_value)).first()
        if acquirer is None:
            acquirer = Acquirer.objects.filter(name__iexact=acquirer_value).first()
        if acquirer is None:
            return Response(
                {"detail": "Acquirer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        cnae = "".join(character for character in cnae_value if character.isdigit())
        if not cnae:
            return Response(
                {"detail": "CNAE must contain at least one digit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fees = Fee.objects.filter(acquirer=acquirer, cnae__code=cnae).order_by(
            "network__name", "installments"
        )
        return Response(FeeSerializer(fees, many=True).data)


class PlanListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = Plan.objects.prefetch_related("fees").all()
        return Response(PlanReadSerializer(plans, many=True).data)

    def post(self, request):
        serializer = PlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(PlanReadSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            plan = Plan.objects.prefetch_related("fees").get(pk=pk)
        except Plan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlanReadSerializer(plan).data)


class BusinessPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BusinessListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        businesses = Business.objects.all()
        if document := request.query_params.get("document"):
            businesses = businesses.filter(document=document)
        if name := request.query_params.get("name"):
            businesses = businesses.filter(name__icontains=name)
        status_counts = {
            item["status"]: item["total"]
            for item in businesses.values("status").annotate(total=Count("id"))
        }
        paginator = BusinessPagination()
        page = paginator.paginate_queryset(businesses, request)
        serializer = BusinessReadSerializer(page, many=True)
        return Response({
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "count_by_status": status_counts,
            "results": serializer.data,
        })

    def post(self, request):
        serializer = BusinessWriteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data, status=status.HTTP_201_CREATED)


class BusinessDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        return _get_object_or_none(Business, pk)

    def get(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(BusinessReadSerializer(business).data)

    def put(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BusinessWriteSerializer(business, data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data)

    def patch(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BusinessWriteSerializer(business, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data)

    def delete(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        business.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessDetailsListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        details = BusinessDetails.objects.select_related("business", "plan")
        if business_id := request.query_params.get("business"):
            details = details.filter(business_id=business_id)
        return Response(BusinessDetailsSerializer(details, many=True).data)

    def post(self, request):
        serializer = BusinessDetailsSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        with transaction.atomic():
            details = serializer.save()
            details.business.status = Status.PENDING
            details.business.save(update_fields=["status"])
        return Response(BusinessDetailsSerializer(details).data, status=status.HTTP_201_CREATED)


class BusinessDetailsDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        details = _get_object_or_none(BusinessDetails, pk)
        if details is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(BusinessDetailsSerializer(details).data)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial=False):
        details = _get_object_or_none(BusinessDetails, pk)
        if details is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BusinessDetailsSerializer(details, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessDetailsSerializer(serializer.save()).data)

    def delete(self, request, pk):
        details = _get_object_or_none(BusinessDetails, pk)
        if details is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        details.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PosDeviceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = PosDevice.objects.select_related("model", "business")
        if business_id := request.query_params.get("business"):
            devices = devices.filter(business_id=business_id)
        return Response(PosDeviceSerializer(devices, many=True).data)

    def post(self, request):
        serializer = PosDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(PosDeviceSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class PosDeviceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = _get_object_or_none(PosDevice, pk)
        if device is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PosDeviceSerializer(device).data)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial=False):
        device = _get_object_or_none(PosDevice, pk)
        if device is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PosDeviceSerializer(device, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return Response(PosDeviceSerializer(serializer.save()).data)

    def delete(self, request, pk):
        device = _get_object_or_none(PosDevice, pk)
        if device is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        device.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
