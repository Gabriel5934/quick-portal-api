# OWN Financial Auth Integration — Quick Portal API

## Overview

The Quick Portal API integrates with the OWN Financial Acquiring API using OAuth 2.0 Client Credentials flow. A service layer handles token acquisition and caching. An authenticated endpoint exposes this to portal users.

---

## Architecture

```
Portal User (JWT) --> POST /own/auth/ --> OwnAuthTokenView --> get_own_token()
                                                                  |
                                                             cache hit? --> return token
                                                             cache miss? --> POST OWN /auth --> cache --> return token
```

- **Token storage**: Django cache (LocMemCache in dev, Redis/Memcached in production)
- **Token TTL**: `expires_in - 10` seconds (buffer to prevent using near-expired tokens)
- **Minimum TTL floor**: 30 seconds
- **Credentials source**: Environment variables

---

## Endpoint

### `POST /own/auth/`

Triggers OWN Financial authentication. Returns cached token if available, otherwise fetches a new one.

**Authentication**: Required. JWT Bearer token in `Authorization` header.

**Request**: No body required.

**Success Response** (`200 OK`):

```json
{
  "status": "authenticated",
  "token_preview": "eyJhbGciO...",
  "message": "OWN Financial token acquired successfully."
}
```

**Failure Response** (`502 Bad Gateway`):

```json
{
  "error": "own_auth_failed",
  "detail": "OWN auth failed with status 401"
}
```

**Failure Response** (`401 Unauthorized`): Returned when no valid JWT is provided.

---

## Service Layer

### `quickportal.services.own_auth.get_own_token() -> str`

Returns a valid OWN Financial access token. Checks cache first, fetches from OWN API on miss.

**Usage in other views/services**:

```python
from quickportal.services.own_auth import get_own_token, OwnAuthError

try:
    token = get_own_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Use headers in requests to OWN API endpoints
except OwnAuthError as exc:
    # Handle authentication failure
    pass
```

**Raises**: `OwnAuthError` with attributes `status_code` and `response_body` when OWN API returns an error or is unreachable.

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OWN_AUTH_URL` | No | `https://acquirer-qa.own.financial/agilli/v2/auth` | OWN auth endpoint URL. Change to `https://acquirer.own.financial/agilli/v2/auth` for production. |
| `OWN_CLIENT_ID` | Yes | `""` | OAuth client identifier provided by OWN. |
| `OWN_CLIENT_SECRET` | Yes | `""` | OAuth client secret provided by OWN. |
| `OWN_SCOPE` | Yes | `""` | Integration scope allowed for the client. |

### Django Settings (in `app/config/settings.py`)

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'quickportal-cache',
    }
}

OWN_AUTH_URL = os.environ.get('OWN_AUTH_URL', 'https://acquirer-qa.own.financial/agilli/v2/auth')
OWN_CLIENT_ID = os.environ.get('OWN_CLIENT_ID', '')
OWN_CLIENT_SECRET = os.environ.get('OWN_CLIENT_SECRET', '')
OWN_SCOPE = os.environ.get('OWN_SCOPE', '')
```

---

## File Locations

| File | Purpose |
|------|---------|
| `app/quickportal/services/own_auth.py` | Service layer: `get_own_token()`, `OwnAuthError` |
| `app/quickportal/views.py` | `OwnAuthTokenView` class |
| `app/quickportal/urls.py` | Route: `own/auth/` |
| `app/config/settings.py` | Cache config, OWN env var bindings |

---

## OWN API Token Details

The OWN auth endpoint returns:

```json
{
  "access_token": "...",
  "expires_in": 300,
  "refresh_expires_in": 0,
  "token_type": "Bearer",
  "not-before-policy": 0,
  "scope": "own.api_wl.api"
}
```

- Token lifetime: 300 seconds (5 minutes)
- Token type: Bearer
- Grant type: `client_credentials` (app-level, not user-level)
- The token is shared across all portal users (single OWN account per deployment)

---

## Using the Token for OWN API Calls

All subsequent requests to OWN API endpoints must include:

```http
Authorization: Bearer <access_token>
```

Example in Python:

```python
from quickportal.services.own_auth import get_own_token

token = get_own_token()
response = requests.get(
    "https://acquirer-qa.own.financial/agilli/v2/some-endpoint",
    headers={"Authorization": f"Bearer {token}"},
)
```

If the token has expired (cache miss), `get_own_token()` automatically fetches a new one.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| OWN API returns non-200 | `OwnAuthError` raised with `status_code` and `response_body` |
| Network timeout (>10s) | `OwnAuthError` raised with connection error message |
| No `access_token` in response | `OwnAuthError` raised |
| Missing env vars (empty strings) | OWN API will reject the request; `OwnAuthError` raised with 401 |

---

## LLM Optimization Notes

- The integration endpoint is `POST /own/auth/` and requires JWT authentication.
- `get_own_token()` is the single entry point for obtaining a valid OWN token anywhere in the codebase.
- Tokens are cached automatically; callers never need to manage expiration logic.
- The cache key is `own_financial_access_token` in Django's default cache.
- To switch environments (sandbox to production), change `OWN_AUTH_URL` env var.
- For multi-worker deployments, replace `LocMemCache` with a shared cache backend (Redis).
- The service uses a 10-second buffer before expiry to avoid race conditions.
- `OwnAuthError` is the only exception type raised by the service layer.
