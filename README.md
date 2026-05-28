# django-minimal

Minimal Django 5 project running in Docker with PostgreSQL.

## Quickstart

```bash
# 1. Copy env file
cp .env.example .env

# 2. Build & start (migrations run automatically on first boot)
docker compose up --build

# 3. Create a superuser (optional)
docker compose exec web python manage.py createsuperuser
```

## Endpoints

| URL | Description |
|-----|-------------|
| `http://localhost:8000/health/` | Health check → `{"status": "ok"}` |
| `http://localhost:8000/admin/` | Django admin |

## Project layout

```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
├── README.md
└── app/
    ├── manage.py
    └── config/
        ├── settings.py
        ├── urls.py
        ├── views.py
        ├── wsgi.py
        └── asgi.py
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `1` | Set to `0` in production |
| `DJANGO_SECRET_KEY` | insecure default | **Change in production** |
| `ALLOWED_HOSTS` | `localhost 127.0.0.1` | Space-separated list |
| `POSTGRES_DB` | `app` | Database name |
| `POSTGRES_USER` | `app` | Database user |
| `POSTGRES_PASSWORD` | `app` | **Change in production** |

## Adding a new app

```bash
docker compose exec web python manage.py startapp myapp
```

Then add `'myapp'` to `INSTALLED_APPS` in `config/settings.py`.
