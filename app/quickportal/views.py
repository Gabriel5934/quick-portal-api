from django.db.models import Count
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from quickportal.models import Acquirer, Business, CnaeMccMapping, PosModel
from quickportal.serializers import (
    AcquirerSerializer,
    BusinessReadSerializer,
    BusinessWriteSerializer,
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


class BusinessPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BusinessListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        businesses = Business.objects.select_related("mcc").all()
        if document := request.query_params.get("document"):
            businesses = businesses.filter(document=document)
        if legal_name := request.query_params.get("legal_name"):
            businesses = businesses.filter(legal_name__icontains=legal_name)
        if trade_name := request.query_params.get("trade_name"):
            businesses = businesses.filter(trade_name__icontains=trade_name)
        status_counts = {
            item["own_status"]: item["total"]
            for item in businesses.values("own_status").annotate(total=Count("id"))
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
        serializer.is_valid(raise_exception=True)
        business = serializer.save()
        return Response(BusinessReadSerializer(business).data, status=status.HTTP_201_CREATED)


class BusinessDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        try:
            return Business.objects.select_related("mcc").get(pk=pk)
        except Business.DoesNotExist:
            return None

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
        serializer.is_valid(raise_exception=True)
        business = serializer.save()
        return Response(BusinessReadSerializer(business).data)

    def patch(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BusinessWriteSerializer(business, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        business = serializer.save()
        return Response(BusinessReadSerializer(business).data)

    def delete(self, request, pk):
        business = self._get_object(pk)
        if business is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        business.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
