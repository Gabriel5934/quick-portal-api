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

## Management commands

The commands below are provided by the `quickportal` app. When the development
stack is running, execute them through the `web` container:

```bash
docker compose exec web python manage.py <command> [arguments]
```

If you are running Django directly from the host instead, run the equivalent
command from `app/`:

```bash
python manage.py <command> [arguments]
```

Use `python manage.py help <command>` to see Django's generated argument
reference for any command.

### `ensure_dev_user`

```text
ensure_dev_user <email> <password>
```

Creates a development user, or updates the first user whose email matches
case-insensitively. The email is trimmed and lowercased, the account is made
active, and its password is replaced with the supplied password. The
development Compose stack runs this command automatically for
`root@email.com`.

```bash
docker compose exec web python manage.py ensure_dev_user developer@example.com 'local-password'
```

### `populate_acquirers`

```text
populate_acquirers [--file PATH]
```

Loads acquirers from a JSON array containing objects with a `name` field. The
default file is `app/load_acquirers.json`. Records without a name are skipped.

This command deletes all existing acquirers before inserting the loaded data.

```bash
docker compose exec web python manage.py populate_acquirers
docker compose exec web python manage.py populate_acquirers --file /app/custom-acquirers.json
```

### `populate_cnaes`

```text
populate_cnaes <code_key> <description_key> <mcc_key> [--file PATH]
```

Loads CNAE records from a JSON array. The three positional arguments identify
the object keys containing the CNAE code, description, and MCC. Formatting is
removed from codes and MCCs, incomplete records are skipped, and duplicate CNAE
codes in the input are resolved in favor of the last record. The default file
is `app/load_cnaes.json`.

This command deletes all existing CNAEs before inserting the loaded data.

```bash
docker compose exec web python manage.py populate_cnaes codCnae descCnae codMcc
docker compose exec web python manage.py populate_cnaes code description mcc --file /app/custom-cnaes.json
```

### `populate_networks`

```text
populate_networks [--file PATH]
```

Creates or updates networks from a JSON array with `name` and optional `color`
fields. Colors must be empty or use six-digit hexadecimal notation such as
`#1b34cb`. Names are matched case-insensitively, and duplicate names in the
input are resolved in favor of the last record. The default file is
`app/load_networks.json`. Existing networks absent from the file are retained.

```bash
docker compose exec web python manage.py populate_networks
docker compose exec web python manage.py populate_networks --file /app/custom-networks.json
```

### `populate_pos_models`

```text
populate_pos_models [--file PATH]
```

Loads POS models from a JSON array whose objects contain `model` and `acquirer`
fields. The named acquirer must already exist; incomplete records and records
with unknown acquirers are skipped. The default file is
`app/load_pos_models.json`, so run `populate_acquirers` first when initializing
a database.

This command deletes all existing POS models before inserting the loaded data.

```bash
docker compose exec web python manage.py populate_pos_models
docker compose exec web python manage.py populate_pos_models --file /app/custom-pos-models.json
```

### `create_fees`

```text
create_fees <acquirer> <cnae>
```

Creates or updates randomized fees for an acquirer and CNAE. The acquirer may
be supplied by numeric ID or case-insensitive name. CNAE formatting is ignored,
so both `4711302` and `4711-3/02` address the same record. The command creates
missing Visa, Mastercard, Elo, Pix, and Acquirer networks, then writes fees for
installment values `0` through `21` on card networks, `-1` for Pix, and `-2`
for Acquirer. Existing matching fees receive new random values between 1.00%
and 5.00%.

The acquirer and CNAE must exist before running the command.

```bash
docker compose exec web python manage.py create_fees OWN 4711-3/02
docker compose exec web python manage.py create_fees 1 4711302
```

### `create_root_business`

```text
create_root_business {reseller,store} [--seed INTEGER]
```

Creates a root reseller or root store with randomized, valid demonstration
data. Pass `--seed` to reproduce the generated values.

```bash
docker compose exec web python manage.py create_root_business reseller --seed 42
docker compose exec web python manage.py create_root_business store
```

### `create_business`

```text
create_business [business_id] [--store] [--seed INTEGER]
```

Creates a root reseller when no parent ID is supplied. With a parent ID, it
creates the next valid child in the hierarchy:

- reseller parent: a re-reseller by default, or a store with `--store`;
- re-reseller parent: a store;
- store parent: rejected because stores cannot have children.

The `--store` option requires a reseller parent. Pass `--seed` to reproduce the
generated values.

```bash
# Create a root reseller.
docker compose exec web python manage.py create_business --seed 42

# Create a re-reseller under business 1.
docker compose exec web python manage.py create_business 1

# Create a store directly under reseller 1.
docker compose exec web python manage.py create_business 1 --store
```

### `generate_business_hierarchy`

```text
generate_business_hierarchy [--seed INTEGER] [--admin-email EMAIL]
```

Creates a complete reseller → re-reseller → store hierarchy, including business
details for the store. It uses the first plan linked to an acquirer when one is
available; otherwise it creates a demo acquirer, CNAE, and plan. Pass `--seed`
for reproducible data. Pass `--admin-email` to grant an existing user the ADMIN
role on the new reseller; the command fails if that email is not found.

```bash
docker compose exec web python manage.py generate_business_hierarchy --seed 42
docker compose exec web python manage.py generate_business_hierarchy \
  --seed 42 --admin-email root@email.com
```

### `list_businesses`

```text
list_businesses
```

Prints all businesses, ordered by ID, as a compact table that includes their
type, parent, document, CNAE, contact details, and status.

```bash
docker compose exec web python manage.py list_businesses
```

### Common Django and installed-app commands

These are not defined by `quickportal`, but are commonly used in this project:

```bash
# Apply database migrations.
docker compose exec web python manage.py migrate

# Create an interactive Django superuser.
docker compose exec web python manage.py createsuperuser

# Remove expired SimpleJWT blacklist records.
docker compose exec web python manage.py flushexpiredtokens

# List every command available in the current installation.
docker compose exec web python manage.py help
```

## Adding a new app

```bash
docker compose exec web python manage.py startapp myapp
```

Then add `'myapp'` to `INSTALLED_APPS` in `config/settings.py`.
