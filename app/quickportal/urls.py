from django.urls import path

from quickportal.views import (
    AcquirerListView,
    BusinessDetailView,
    BusinessListCreateView,
    CnaeMccMappingListView,
    EmailTokenObtainPairView,
    MccFeeDetailView,
    MccListView,
    MerchantRegistrationView,
    OwnAuthTokenView,
    PosModelListView,
    UserRegistrationView,
)

urlpatterns = [
    path("users/register/", UserRegistrationView.as_view()),
    path("api/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("own/auth/", OwnAuthTokenView.as_view(), name="own_auth"),
    path(
        "own/merchants/register/",
        MerchantRegistrationView.as_view(),
        name="own_merchant_register",
    ),
    path("api/cnae-mcc/", CnaeMccMappingListView.as_view(), name="cnae_mcc_list"),
    path("api/acquirers/", AcquirerListView.as_view(), name="acquirer_list"),
    path("api/pos-models/", PosModelListView.as_view(), name="pos_model_list"),
    path("api/mccs/", MccListView.as_view(), name="mcc_list"),
    path("api/mccs/<int:pk>/fees/", MccFeeDetailView.as_view(), name="mcc_fee_detail"),
    path("api/businesses/", BusinessListCreateView.as_view(), name="business_list_create"),
    path("api/businesses/<int:pk>/", BusinessDetailView.as_view(), name="business_detail"),
]
