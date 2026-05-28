from django.urls import path

from quickportal.views import (
    CnaeMccMappingListView,
    EmailTokenObtainPairView,
    MerchantRegistrationView,
    OwnAuthTokenView,
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
]
