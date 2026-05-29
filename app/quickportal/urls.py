from django.urls import path

from quickportal.views import (
    AcquirerListView,
    CnaeMccMappingListView,
    EmailTokenObtainPairView,
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
]
