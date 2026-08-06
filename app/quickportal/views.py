from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Exists, OuterRef
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from quickportal.models import (
    Acquirer,
    BusinessDetails,
    BusinessMembership,
    BusinessRole,
    BusinessType,
    Cnae,
    Fee,
    Network,
    Plan,
    PosDevice,
    PosModel,
    Status,
)
from quickportal.serializers import (
    AcquirerSerializer,
    BusinessReadSerializer,
    BusinessDetailsSerializer,
    BusinessMembershipReadSerializer,
    BusinessMembershipWriteSerializer,
    BusinessWriteSerializer,
    CnaeSerializer,
    EmailTokenObtainPairSerializer,
    FeeSerializer,
    NetworkSerializer,
    PlanReadSerializer,
    PlanWriteSerializer,
    PosDeviceSerializer,
    PosModelSerializer,
    UserCreateSerializer,
)
from quickportal.services.brasil_api import BrasilApiError
from quickportal.services.business_access import (
    accessible_businesses,
    get_accessible_business_or_404,
    has_business_role,
    has_governing_ancestor_admin,
)
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


WRITE_ROLES = {BusinessRole.ADMIN, BusinessRole.MANAGER}


def _require_business_role(user, business, allowed_roles):
    if not has_business_role(user, business, allowed_roles):
        raise PermissionDenied()


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
        business_id = request.data.get("business")
        if business_id is None:
            return Response(
                {"business": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        business = get_accessible_business_or_404(request.user, business_id)
        if business.type != BusinessType.STORE:
            return Response(
                {"business": ["Merchant registration requires a store."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _require_business_role(request.user, business, WRITE_ROLES)
        payload = request.data.copy()
        payload.pop("business", None)
        try:
            result = register_merchant(payload)
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


class NetworkListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        networks = Network.objects.order_by("id")
        return Response(NetworkSerializer(networks, many=True).data)


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

        fees = (
            Fee.objects.select_related("network")
            .filter(acquirer=acquirer, cnae__code=cnae)
            .order_by("network__name", "installments")
        )
        return Response(FeeSerializer(fees, many=True).data)


class PlanListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = Plan.objects.select_related("cnae").prefetch_related("fees").all()
        return Response(PlanReadSerializer(plans, many=True).data)

    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied()
        serializer = PlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(PlanReadSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            plan = Plan.objects.select_related("cnae").prefetch_related("fees").get(pk=pk)
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
        businesses = accessible_businesses(request.user).order_by("id")
        if document := request.query_params.get("document"):
            businesses = businesses.filter(document=document)
        if name := request.query_params.get("name"):
            businesses = businesses.filter(name__icontains=name)
        status_counts = {
            item["status"]: item["total"]
            for item in businesses.order_by().values("status").annotate(total=Count("id"))
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
            parent = serializer.validated_data.get("parent")
            if parent is None:
                if not request.user.is_superuser:
                    raise PermissionDenied()
            else:
                parent = get_accessible_business_or_404(request.user, parent.pk)
                _require_business_role(
                    request.user, parent, {BusinessRole.ADMIN}
                )
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data, status=status.HTTP_201_CREATED)


class BusinessDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, user, pk):
        return get_accessible_business_or_404(user, pk)

    def get(self, request, pk):
        business = self._get_object(request.user, pk)
        return Response(BusinessReadSerializer(business).data)

    def put(self, request, pk):
        business = self._get_object(request.user, pk)
        _require_business_role(request.user, business, WRITE_ROLES)
        serializer = BusinessWriteSerializer(business, data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self._authorize_hierarchy_change(request, business, serializer)
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data)

    def patch(self, request, pk):
        business = self._get_object(request.user, pk)
        _require_business_role(request.user, business, WRITE_ROLES)
        serializer = BusinessWriteSerializer(business, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            self._authorize_hierarchy_change(request, business, serializer)
            business = serializer.save()
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessReadSerializer(business).data)

    def delete(self, request, pk):
        business = self._get_object(request.user, pk)
        _require_business_role(request.user, business, {BusinessRole.ADMIN})
        try:
            business.delete()
        except ProtectedError:
            return Response(
                {"detail": "The business cannot be deleted while it has child businesses."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _authorize_hierarchy_change(request, business, serializer):
        new_type = serializer.validated_data.get("type", business.type)
        new_parent = serializer.validated_data.get("parent", business.parent)
        if new_type == business.type and new_parent == business.parent:
            return
        _require_business_role(request.user, business, {BusinessRole.ADMIN})
        if new_parent is None:
            if not request.user.is_superuser:
                raise PermissionDenied()
            return
        accessible_parent = get_accessible_business_or_404(request.user, new_parent.pk)
        _require_business_role(
            request.user, accessible_parent, {BusinessRole.ADMIN}
        )


class BusinessMembershipListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id):
        business = self._get_admin_business(request.user, business_id)
        memberships = business.memberships.select_related("user").order_by("id")
        return Response(BusinessMembershipReadSerializer(memberships, many=True).data)

    def post(self, request, business_id):
        business = self._get_admin_business(request.user, business_id)
        serializer = BusinessMembershipWriteSerializer(
            data=request.data, context={"business": business}
        )
        serializer.is_valid(raise_exception=True)
        membership = serializer.save(business=business)
        return Response(
            BusinessMembershipReadSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _get_admin_business(user, business_id):
        business = get_accessible_business_or_404(user, business_id)
        _require_business_role(user, business, {BusinessRole.ADMIN})
        return business


class BusinessMembershipDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, business_id, pk):
        business = BusinessMembershipListCreateView._get_admin_business(
            request.user, business_id
        )
        membership = self._get_membership(business, pk)
        serializer = BusinessMembershipWriteSerializer(
            membership,
            data=request.data,
            partial=True,
            context={"business": business},
        )
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data.get("role", membership.role)
        with transaction.atomic():
            self._protect_final_admin(membership, new_role)
            membership = serializer.save()
        return Response(BusinessMembershipReadSerializer(membership).data)

    def delete(self, request, business_id, pk):
        business = BusinessMembershipListCreateView._get_admin_business(
            request.user, business_id
        )
        membership = self._get_membership(business, pk)
        with transaction.atomic():
            self._protect_final_admin(membership, None)
            membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _get_membership(business, pk):
        try:
            return business.memberships.select_related(
                "business__parent__parent", "user"
            ).get(pk=pk)
        except BusinessMembership.DoesNotExist as exc:
            raise NotFound() from exc

    @staticmethod
    def _protect_final_admin(membership, new_role):
        if membership.role != BusinessRole.ADMIN or new_role == BusinessRole.ADMIN:
            return
        memberships = BusinessMembership.objects.select_for_update().filter(
            business=membership.business
        )
        has_other_admin = any(
            item.pk != membership.pk and item.role == BusinessRole.ADMIN
            for item in memberships
        )
        if not has_other_admin and not has_governing_ancestor_admin(
            membership.business
        ):
            raise ValidationError(
                {"role": "The final governing admin cannot be removed or demoted."}
            )


class BusinessDetailsListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        details = BusinessDetails.objects.select_related("business", "plan").filter(
            business__in=accessible_businesses(request.user)
        )
        if business_id := request.query_params.get("business"):
            details = details.filter(business_id=business_id)
        return Response(BusinessDetailsSerializer(details, many=True).data)

    def post(self, request):
        business_id = request.data.get("business")
        if business_id is not None:
            business = get_accessible_business_or_404(request.user, business_id)
            _require_business_role(request.user, business, WRITE_ROLES)
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
        details = self._get_object(request.user, pk)
        return Response(BusinessDetailsSerializer(details).data)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial=False):
        details = self._get_object(request.user, pk)
        _require_business_role(request.user, details.business, WRITE_ROLES)
        serializer = BusinessDetailsSerializer(details, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            target = serializer.validated_data.get("business", details.business)
            target = get_accessible_business_or_404(request.user, target.pk)
            _require_business_role(request.user, target, WRITE_ROLES)
        except BrasilApiError as exc:
            return _brasil_api_error_response(exc)
        return Response(BusinessDetailsSerializer(serializer.save()).data)

    def delete(self, request, pk):
        details = self._get_object(request.user, pk)
        _require_business_role(request.user, details.business, WRITE_ROLES)
        details.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _get_object(user, pk):
        try:
            return BusinessDetails.objects.select_related(
                "business", "business__parent"
            ).get(pk=pk, business__in=accessible_businesses(user))
        except BusinessDetails.DoesNotExist as exc:
            raise NotFound() from exc


class PosDeviceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = PosDevice.objects.select_related("model", "business").filter(
            business__in=accessible_businesses(request.user)
        )
        if business_id := request.query_params.get("business"):
            devices = devices.filter(business_id=business_id)
        return Response(PosDeviceSerializer(devices, many=True).data)

    def post(self, request):
        business_id = request.data.get("business")
        if business_id is not None:
            business = get_accessible_business_or_404(request.user, business_id)
            _require_business_role(request.user, business, WRITE_ROLES)
        serializer = PosDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(PosDeviceSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class PosDeviceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = self._get_object(request.user, pk)
        return Response(PosDeviceSerializer(device).data)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial=False):
        device = self._get_object(request.user, pk)
        _require_business_role(request.user, device.business, WRITE_ROLES)
        serializer = PosDeviceSerializer(device, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data.get("business", device.business)
        target = get_accessible_business_or_404(request.user, target.pk)
        _require_business_role(request.user, target, WRITE_ROLES)
        return Response(PosDeviceSerializer(serializer.save()).data)

    def delete(self, request, pk):
        device = self._get_object(request.user, pk)
        _require_business_role(request.user, device.business, WRITE_ROLES)
        device.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _get_object(user, pk):
        try:
            return PosDevice.objects.select_related(
                "business", "business__parent"
            ).get(pk=pk, business__in=accessible_businesses(user))
        except PosDevice.DoesNotExist as exc:
            raise NotFound() from exc
