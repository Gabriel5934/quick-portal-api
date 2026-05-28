# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start all services (PostgreSQL + Django dev server)
docker compose up --build

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Run tests
docker compose exec web python manage.py test quickportal

# Lint
docker compose exec web ruff check

# Fix lint errors
docker compose exec web ruff check --fix

# Create a new Django app
docker compose exec web python manage.py startapp <appname>
```

The Django manage.py lives at `app/manage.py`. The Docker volume mounts `./app` to `/app` in the container, so code changes are reflected immediately.

## Architecture

This is a Django 5 + DRF API backend for "Quick Portal" — a portal that integrates with OWN Financial's acquiring platform. It runs in Docker with PostgreSQL 16.

**Django project structure:**

- `app/config/` — Django project settings, root URL conf, health endpoint
- `app/quickportal/` — Main app with user registration, JWT auth (email-based login), and OWN Financial API integration

**Authentication flow:**

- Users register/login with email+password (not Django's default username)
- `EmailTokenObtainPairSerializer` overrides SimpleJWT to accept email instead of username
- Usernames are auto-generated UUIDs (`user_{hex}`)
- JWT tokens (access + refresh) are issued via SimpleJWT

**OWN Financial integration (`quickportal/services/`):**

- `own_auth.py` — OAuth2 client_credentials flow to OWN's API; tokens are cached in Django's LocMemCache with TTL from the response
- `own_merchant.py` — Merchant registration against OWN's `/cadastrarConveniada` endpoint; requires a valid OWN token

**Key design decisions:**

- CORS is configured for a Vite frontend at localhost:5173
- OWN API credentials come from environment variables (OWN_CLIENT_ID, OWN_CLIENT_SECRET, OWN_SCOPE)
- OWN endpoints are protected with `IsAuthenticated` (require valid JWT)
- `owndocs/` contains reference documentation for OWN's API (not application code)
