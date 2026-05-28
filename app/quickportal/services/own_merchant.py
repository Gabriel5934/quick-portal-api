import logging

import requests
from django.conf import settings

from quickportal.services.own_auth import get_own_token

logger = logging.getLogger(__name__)


class MerchantRegistrationError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def register_merchant(payload: dict) -> dict:
    """
    Register a merchant in the OWN Acquiring platform.

    Returns dict with 'protocolo' and 'status' on success.
    Raises MerchantRegistrationError on API errors or OwnAuthError on auth failure.
    """
    token = get_own_token()
    url = f"{settings.OWN_BASE_URL}/cadastrarConveniada"

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise MerchantRegistrationError(f"Connection error: {exc}") from exc

    if response.status_code == 200:
        return response.json()

    raise MerchantRegistrationError(
        f"Merchant registration failed with status {response.status_code}",
        status_code=response.status_code,
        response_body=response.text,
    )
