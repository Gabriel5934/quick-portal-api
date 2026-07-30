# django-minimal

Minimal Django 5 project running in Docker with PostgreSQL.

## Quickstart

```bash
# 1. Copy env file
cp .env.example .env.dev

# 2. Build & start (migrations run automatically on first boot)
docker compose up --build

# 3. Create a superuser (optional)
docker compose exec web python manage.py createsuperuser
```

## Endpoints

| URL                             | Description                       |
| ------------------------------- | --------------------------------- |
| `http://localhost:8080/health/` | Health check → `{"status": "ok"}` |
| `http://localhost:8080/admin/`  | Django admin                      |

nginx is the only public service. It proxies application requests to Django and
serves files collected by Django under `/static/`.

For the production stack, copy `.env.example` to `.env`, then configure it
before starting:

- Replace `DJANGO_SECRET_KEY=dev-secret-key-change-in-prod` with a strong,
  unique secret.
- Replace `POSTGRES_PASSWORD=app` with a strong, unique database password.
- Set `DEBUG=0`.
- Set `ALLOWED_HOSTS` for the deployment.

After those production values are configured, run:

```bash
docker compose up --build
```

The production nginx port defaults to `80` and can be changed with `NGINX_PORT`.
Production enables HTTPS redirects, secure cookies, and HSTS by default, and
trusts nginx's `X-Forwarded-Proto` header.

For an HTTP-only QA environment, keep `DEBUG=0` and set `USE_HTTPS=0`. This
disables HTTPS enforcement without exposing Django debug pages:

```bash
eb setenv USE_HTTPS=0
```

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

| Variable            | Default               | Description              |
| ------------------- | --------------------- | ------------------------ |
| `DEBUG`             | `1`                   | Set to `0` in production |
| `USE_HTTPS`         | Inverse of `DEBUG`    | Set to `0` for HTTP-only QA |
| `DJANGO_SECRET_KEY` | insecure default      | **Change in production** |
| `ALLOWED_HOSTS`     | `localhost 127.0.0.1` | Space-separated list     |
| `POSTGRES_DB`       | `app`                 | Database name            |
| `POSTGRES_USER`     | `app`                 | Database user            |
| `POSTGRES_PASSWORD` | `app`                 | **Change in production** |

## Adding a new app

```bash
docker compose exec web python manage.py startapp myapp
```

Then add `'myapp'` to `INSTALLED_APPS` in `config/settings.py`.

## MCC Codes

Using cURL or any other tool fetch the list of MCC codes from the OWN api (agilli/parceiro/v2/consultarAtividades)
Save the raw output in a json file called "cnaemcc.json" inside /app
Then update the database with the populate_cnae_mcc management command

```bash
docker compose exec web python manage.py populate_cnae_mcc
```

## Flushing blacklisted tokens

```bash
python manage.py flushexpiredtokens
```
