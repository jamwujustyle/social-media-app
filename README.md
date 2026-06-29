# Social Network API

REST API backend for a mini social network. Users, posts, comments, likes, JWT auth, email verification, scheduled cleanup via Celery.

## Quick Start

```bash
just start        # builds images, starts all services
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

That's it. On first run, `just setup` auto-generates `.env` from the template with a cryptographically secure JWT secret (`openssl rand -hex 32`). No manual configuration needed.

```bash
just test         # runs the test suite inside Docker
just stop         # tears down containers and volumes
just logs         # tail all service logs
```

---

## Architecture

### 3-Layer Separation

```
Router (HTTP) → Service (Business Logic) → Model (Data)
```

Each domain (`auth/`, `user/`, `social/`) follows this pattern:

```
server/app/
├── auth/
│   ├── router.py          # endpoint definitions, request parsing
│   ├── service.py         # registration, login, verification logic
│   ├── dependencies.py    # get_current_user (JWT extraction)
│   └── schemas.py         # Pydantic request/response models
├── user/
│   ├── router.py          # /me endpoint
│   ├── service.py         # profile lookup, update
│   ├── models.py          # User ORM
│   └── schemas.py
├── social/
│   ├── router.py          # posts, comments, likes, feed
│   ├── service.py         # ownership checks, like constraints
│   ├── models.py          # Post, Comment, Like ORM
│   └── schemas.py
├── core/
│   ├── config.py          # pydantic-settings, all env vars
│   ├── database.py        # async engine, session factory
│   ├── security.py        # JWT creation/decode, bcrypt
│   └── exception_handlers.py
├── tasks.py               # Celery task: cleanup unverified users
└── worker.py              # Celery app + beat schedule
```

**Why this and not a monolith service file?** Each layer has one job. Routers don't know about SQL. Services don't know about HTTP status codes (they raise `HTTPException` but never construct `Response` objects). Models don't contain business rules. This means I can test business logic by calling service methods directly, without spinning up an HTTP client.

### Key Design Decisions

**Composite primary key on `Like` instead of a surrogate UUID.**
The spec requires uniqueness on `(user_id, post_id)`. A composite PK enforces this at the database level — no separate unique constraint needed, no wasted index on a UUID that nothing references.

**`selectin` loading on relationships.**
Async SQLAlchemy cannot do implicit lazy loads (raises `MissingGreenlet`). Instead of scattering `await` calls or using `run_sync`, all Post relationships (`comments`, `likes`) use `lazy="selectin"` — they're batch-loaded in a second query automatically within the same session.

**Global exception handlers instead of per-route try/except.**
`exception_handlers.py` registers handlers for `IntegrityError`, `OperationalError`, `ValidationError`, etc. This keeps routers clean and ensures consistent error response format across the entire API. Database constraint violations (duplicate email, FK issues) get parsed into human-readable messages automatically.

**DB connection retry on startup.**
Docker's `depends_on: service_healthy` doesn't guarantee the DB accepts connections by the time the app starts. `main.py` retries up to 10 times with exponential backoff instead of crashing.

**Verification codes printed to stdout, not emailed.**
The spec explicitly says "без реального SMTP". The code has a detailed comment block explaining exactly how this would scale to production (Celery task → SendGrid/SES, codes in Redis with TTL instead of DB column).

---

## Infrastructure

```yaml
# docker-compose.yml — 5 services
db             # PostgreSQL 16 (Alpine), health-checked
redis          # Redis 7 (Alpine), health-checked
app            # FastAPI + Uvicorn, hot-reload in dev
celery_worker  # Celery worker, processes cleanup tasks
celery_beat    # Celery beat, triggers cleanup every hour
```

**Multi-stage Docker build.** Builder stage compiles wheels with gcc/musl. Runtime stage copies only the wheels — no compiler, no build headers. Smaller image, faster deploys.

**`scripts/init_env.sh`** — Copies `.env.example` → `.env`, injects a random JWT secret. Idempotent (refuses to overwrite existing `.env`).

**`justfile`** — Command runner wrapping Docker Compose. `just start`, `just test`, `just stop`, `just logs`, `just shell`, `just db-shell`. No memorizing long commands.

---

## Background Tasks

Celery Beat triggers `cleanup_unverified_users` every hour. The task deletes users where `is_verified = false` AND (`created_at` or `verification_code_expires_at` is older than 24 hours).

The worker runs in its own container with the same image but a different entrypoint — `celery -A app.worker.celery_app worker`. Beat runs as a third container with `celery -A app.worker.celery_app beat`.

---

## Testing

19 integration tests covering:

- Registration (success + duplicate email rejection)
- Email verification flow (code generation → verification → account activation)
- Login via email and username
- Token refresh
- Unverified user cleanup (Celery task logic)
- Post CRUD with ownership enforcement
- Comment creation (verified-only) and deletion (author-only)
- Like constraints (no self-likes, no duplicates, unlike)
- Feed endpoint (posts grouped by author, likes as UUID arrays)

```bash
just test   # runs inside Docker against the same image as production
```

---

## API Overview

All endpoints are documented at `/docs` (Swagger UI). Key routes:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | — | Create account |
| POST | `/auth/verify-email` | — | Verify with 6-digit code |
| POST | `/auth/login` | — | Get JWT tokens (email or username) |
| POST | `/auth/refresh` | — | Refresh access token |
| GET | `/auth/me` | ✓ | Current user profile |
| PATCH | `/users/me` | ✓ | Update profile |
| GET | `/posts` | — | List posts (paginated, searchable, date-filterable) |
| POST | `/posts` | ✓ verified | Create post |
| GET | `/posts/{id}` | — | Post detail with comments |
| PATCH | `/posts/{id}` | ✓ author | Update post |
| DELETE | `/posts/{id}` | ✓ author | Delete post |
| POST | `/posts/{id}/comments` | ✓ verified | Add comment |
| DELETE | `/posts/{id}/comments/{cid}` | ✓ author | Delete comment |
| POST | `/posts/{id}/like` | ✓ | Like (not own post, once) |
| DELETE | `/posts/{id}/like` | ✓ | Unlike |
| GET | `/posts/all/feed` | — | All users + posts + likes (paginated) |
