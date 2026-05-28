import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

OWN_TOKEN_CACHE_KEY = "own_financial_access_token"


class OwnAuthError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def get_own_token() -> str:
    cached_token = cache.get(OWN_TOKEN_CACHE_KEY)
    if cached_token:
        return cached_token

    payload = {
        "client_id": settings.OWN_CLIENT_ID,
        "client_secret": settings.OWN_CLIENT_SECRET,
        "scope": settings.OWN_SCOPE,
        "grant_type": "client_credentials",
    }

    try:
        response = requests.post(
            settings.OWN_AUTH_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OwnAuthError(f"Connection error: {exc}") from exc

    if response.status_code != 200:
        raise OwnAuthError(
            f"OWN auth failed with status {response.status_code}",
            status_code=response.status_code,
            response_body=response.text,
        )

    data = response.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in", 300)

    if not access_token:
        raise OwnAuthError("No access_token in OWN response.")

    ttl = max(expires_in - 10, 30)
    cache.set(OWN_TOKEN_CACHE_KEY, access_token, timeout=ttl)

    return access_token
