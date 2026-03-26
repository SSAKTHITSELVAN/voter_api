# Voter Data Collection API

Production-grade FastAPI backend for political voter data collection with role-based access, PostGIS geo-queries, duplicate detection, and offline-sync support.

---

## Project Structure

```
voter_api/
├── app/
│   ├── main.py                  ← FastAPI app factory + lifespan
│   ├── core/
│   │   ├── config.py            ← Pydantic Settings (env vars)
│   │   ├── security.py          ← Password hashing + JWT
│   │   ├── dependencies.py      ← get_current_user, require_roles
│   │   └── logging.py           ← Structured logging setup
│   ├── db/
│   │   ├── session.py           ← Async SQLAlchemy engine + Base
│   │   └── init_db.py           ← Table creation + Super Admin seed
│   ├── models/
│   │   ├── mixins.py            ← UUIDMixin, TimestampMixin, SoftDeleteMixin
│   │   ├── user.py              ← User, UserRole enum
│   │   ├── building.py          ← Building, Unit
│   │   ├── household.py         ← Household (PostGIS), HouseholdImage, Person
│   │   └── record.py            ← CollectionRecord, VerificationRecord
│   ├── schemas/
│   │   ├── common.py            ← OrmBase, MessageResponse
│   │   ├── auth.py              ← LoginRequest, TokenResponse
│   │   ├── user.py              ← UserCreate, UserRead
│   │   ├── building.py          ← BuildingCreate/Read, UnitCreate/Read
│   │   └── household.py         ← All household/person/verification schemas
│   ├── services/
│   │   ├── auth_service.py      ← Login logic
│   │   ├── user_service.py      ← User CRUD + role policy
│   │   ├── building_service.py  ← Building + Unit CRUD
│   │   ├── household_service.py ← Household + geo + bulk upload
│   │   └── verification_service.py ← Verification + collection records
│   └── routers/
│       ├── auth.py              ← POST /auth/login
│       ├── users.py             ← POST/GET /users
│       ├── buildings.py         ← POST/GET /buildings, /buildings/units
│       ├── households.py        ← POST/GET /households + nearby + bulk
│       └── verification.py      ← POST /verification
├── alembic/
│   ├── env.py                   ← Async Alembic environment
│   ├── script.py.mako           ← Migration template
│   └── versions/
│       └── 0001_initial_schema.py ← Full initial migration
├── alembic.ini
├── docker-compose.yml           ← PostgreSQL/PostGIS + API
├── Dockerfile
├── requirements.txt
├── .env.example
└── curl_examples.sh             ← Runnable API demo
```

---

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env with your values
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

This will:
- Start **PostgreSQL 16 + PostGIS 3.4**
- Run **Alembic migrations** (`alembic upgrade head`)
- Seed the **Super Admin** user
- Start **Uvicorn** on port **8000**

### 3. Explore the API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

### 4. Run curl examples

```bash
chmod +x curl_examples.sh
./curl_examples.sh
```

---

## Manual Setup (without Docker)

```bash
# 1. Install PostgreSQL + PostGIS
#    Ubuntu: sudo apt install postgresql postgis postgresql-16-postgis-3

# 2. Create database
psql -U postgres -c "CREATE USER voter_user WITH PASSWORD 'strongpassword';"
psql -U postgres -c "CREATE DATABASE voter_db OWNER voter_user;"
psql -U voter_user -d voter_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 3. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env   # then edit DATABASE_URL

# 5. Run migrations
alembic upgrade head

# 6. Start server
uvicorn app.main:app --reload --port 8000
```

---

## Authentication

All endpoints (except `/auth/login` and `/health`) require a **Bearer JWT token**.

```
Authorization: Bearer <access_token>
```

Login returns a token valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 min).

---

## Role Hierarchy & Permissions

| Action                     | SUPER_ADMIN | ADMIN | FIELD_USER |
|----------------------------|:-----------:|:-----:|:----------:|
| Create ADMIN               | ✅          | ❌    | ❌         |
| Create FIELD_USER          | ❌          | ✅    | ❌         |
| List all users             | ✅          | own ↓ | ❌         |
| Create household           | ✅          | ✅    | ✅         |
| View/search households     | ✅          | ✅    | ✅         |
| Delete household           | ✅          | ✅    | ❌         |
| Submit verification        | ✅          | ✅    | ✅         |
| Create Building/Unit       | ✅          | ✅    | ❌         |

---

## API Endpoints

| Method | Path                                     | Description                        |
|--------|------------------------------------------|------------------------------------|
| POST   | `/auth/login`                            | Login → JWT token                  |
| GET    | `/health`                                | Liveness probe                     |
| POST   | `/users`                                 | Create Admin or Field User         |
| GET    | `/users`                                 | List users (scoped by role)        |
| GET    | `/users/me`                              | Get own profile                    |
| GET    | `/users/{id}`                            | Get user by ID                     |
| DELETE | `/users/{id}`                            | Soft-delete user                   |
| POST   | `/buildings`                             | Create building                    |
| GET    | `/buildings/{id}`                        | Get building                       |
| POST   | `/buildings/units`                       | Add unit to building               |
| GET    | `/buildings/{id}/units`                  | List units in building             |
| POST   | `/households`                            | Create household (+ dup check)     |
| POST   | `/households/bulk`                       | Bulk create (offline sync)         |
| GET    | `/households/nearby`                     | PostGIS radius search              |
| GET    | `/households/duplicate-check`            | Check for nearby duplicates        |
| GET    | `/households/{id}`                       | Full household + persons + images  |
| DELETE | `/households/{id}`                       | Soft-delete household              |
| GET    | `/households/{id}/collection-records`    | Collection audit trail             |
| GET    | `/households/{id}/verifications`         | Verification audit trail           |
| POST   | `/verification`                          | Submit MATCHED / MISMATCH          |

---

## Key Design Decisions

### Duplicate Detection
Before any household is created, `ST_DWithin` checks for existing households within **20 metres**. Returns `409 Conflict` with the conflicting IDs, allowing the client to handle it gracefully.

### Apartment Handling
- `Building` → one-to-many → `Unit` → one-to-one → `Household`
- `house_type = APARTMENT` requires `unit_id`; validated at schema level

### Soft Delete
All `User` and `Household` records carry a `deleted_at` timestamp. No `DELETE` SQL is ever issued; all queries filter `WHERE deleted_at IS NULL`.

### Offline Sync
`POST /households/bulk` accepts up to 500 households in one request. Each item passes through the same duplicate check; duplicates are skipped and reported in the response summary, not errored.

### PostGIS Spatial Index
A `GIST` index on `households.geog` makes `ST_DWithin` and `ST_Distance` queries fast even at scale.

---

## Environment Variables

| Variable                    | Default              | Description                        |
|-----------------------------|----------------------|------------------------------------|
| `DATABASE_URL`              | *(required)*         | asyncpg connection string          |
| `SECRET_KEY`                | `change-me`          | JWT signing secret                 |
| `ALGORITHM`                 | `HS256`              | JWT algorithm                      |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60`               | Token lifetime in minutes          |
| `APP_ENV`                   | `development`        | Environment name                   |
| `DEBUG`                     | `true`               | SQLAlchemy echo + CORS *           |
| `LOG_LEVEL`                 | `INFO`               | Python logging level               |
| `SUPER_ADMIN_PHONE`         | `9000000000`         | Seeded super admin phone           |
| `SUPER_ADMIN_PASSWORD`      | `SuperSecret@123`    | Seeded super admin password        |
| `SUPER_ADMIN_NAME`          | `Super Admin`        | Seeded super admin name            |
| `DUPLICATE_RADIUS_METRES`   | `20`                 | Duplicate detection radius         |

> ⚠️ In production: set `DEBUG=false`, use a strong `SECRET_KEY`, and restrict CORS `allow_origins`.
