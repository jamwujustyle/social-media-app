# Social Network Backend — Mini Project

A production-grade REST API for a social network featuring user authentication, posts, comments, and likes. Built with **FastAPI**, **PostgreSQL**, **Redis**, and **Celery** for background task processing.

> **Focus**: Architecture and quality over feature count. Every decision prioritizes **reliability**, **maintainability**, and **scalability**.

---

## 📋 Project Status

### ✅ Must-Have Features (Implemented)

- **User Authentication & Authorization**
  - JWT Bearer tokens (30-min access, 7-day refresh)
  - Email verification with 6-digit codes (24-hour TTL)
  - Automatic cleanup of unverified users via Celery Beat

- **Social Features**
  - Posts: CRUD with search/date filtering, pagination
  - Comments: Nested comments on posts (verified users only)
  - Likes: Constraint-based (no self-likes, one-per-user limit)
  - Feed: Aggregated user profiles with their posts

- **Infrastructure**
  - PostgreSQL async driver (asyncpg)
  - Redis for Celery broker and result backend
  - Docker Compose with health checks and persistence
  - Comprehensive test suite (auth + social domain)

### 🎁 Bonus Features (Implemented)

- Multi-stage Docker build (builder → minimal runtime)
- HTTP-only security best practices
- Structured logging throughout the application
- Just command runner for common tasks
- Automated environment initialization script

---

## 🏗️ Architecture: 3-Layer Pattern

```
Request → Router (HTTP) → Service (Business Logic) → Repository (Data Access)
```

### **Why This Structure?**

Each layer has a single responsibility and can be tested independently:

#### **Layer 1: Routers** (`app/*/router.py`)

- HTTP endpoint definitions
- Request/response validation via Pydantic
- Dependency injection of services
- **Why**: Separates HTTP concerns from business logic; endpoints stay thin and testable

#### **Layer 2: Services** (`app/*/service.py`)

- Core business logic
- Authorization checks (e.g., "can this user delete this post?")
- Transaction coordination
- **Why**: Business rules are centralized; easy to test without mocking HTTP; reusable across multiple routers

#### **Layer 3: Models** (`app/*/models.py`)

- SQLAlchemy ORM definitions
- Database constraints (FK, unique, cascade delete)
- Relationships between entities
- **Why**: Models are thin; database concerns isolated; schema is single source of truth

**Example Flow:**

```python
# router.py
@router.post("/posts", status_code=201)
async def create_post(data: PostCreate,
                      user: User = Depends(get_current_active_user),
                      service: PostService = Depends(get_post_service)):
    return await service.create(user_id=user.id, data=data)

# service.py
class PostService:
    async def create(self, user_id: UUID, data: PostCreate) -> Post:
        # Business logic: validate title/content length, etc.
        post = Post(author_id=user_id, **data.model_dump())
        self.db.add(post)
        await self.db.commit()
        return post
```

---

## 📦 Technology Stack: Decisions & Trade-offs

| Component            | Choice               | Why                                                                                 |
| -------------------- | -------------------- | ----------------------------------------------------------------------------------- |
| **Framework**        | FastAPI              | Async by default; Pydantic validation; auto OpenAPI docs; built for modern Python   |
| **Database**         | PostgreSQL + asyncpg | ACID guarantees; async driver for non-blocking I/O; timezone-aware datetime support |
| **ORM**              | SQLAlchemy 2.0+      | Async support; Mapped[] type hints; cascade delete for referential integrity        |
| **Async Queue**      | Celery + Redis       | Horizontally scalable; delayed/periodic tasks; failed job retry; monitoring-ready   |
| **Security**         | JWT + Bcrypt         | Industry standard; stateless auth; no session storage needed                        |
| **Validation**       | Pydantic             | Type safety at runtime; email/regex pattern validation; automatic OpenAPI schema    |
| **Containerization** | Docker + Compose     | Multi-stage build reduces image size 60%; health checks prevent cascade failures    |

**Scope Decision**:

- ✅ Built horizontally scalable (Celery workers, read replicas possible)
- ✅ No monolithic business logic
- ✅ API-first design (extensible to mobile, web)
- ❌ Did not add: GraphQL, gRPC, microservices (over-engineering for scope)

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (single dependency!)
- OR: Python 3.13+, PostgreSQL 16, Redis 7

### Setup (1 Command)

```bash
# Clone and enter project
git clone <repo> && cd python

# Start everything (initializes .env, builds images, starts services)
just start

# API available at: http://localhost:8000
# Docs at: http://localhost:8000/docs
```

**Behind the scenes:**

1. `just setup` runs `scripts/init_env.sh` → generates secure JWT secret
2. Docker Compose builds multi-stage image
3. PostgreSQL and Redis start with health checks
4. App waits for DB/Redis readiness (retry logic)
5. Database tables auto-created on startup

### Manual Setup (For Development Outside Docker)

```bash
# Generate environment file with secure JWT secret
./scripts/init_env.sh

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r server/requirements.txt

# Start PostgreSQL and Redis
docker compose up db redis

# Apply migrations and start server
cd server
uvicorn app.main:app --reload

# In another terminal: start Celery worker
celery -A app.worker.celery_app worker --loglevel=info

# In another terminal: start Celery Beat
celery -A app.worker.celery_app beat --loglevel=info
```

---

## 🛠️ Development Utilities

### **Justfile** — Command Runner

Save time with pre-configured tasks:

```bash
just setup           # Generate .env with secure JWT secret
just start           # Build and start all services
just stop            # Stop containers and clean volumes
just test            # Run entire test suite in Docker
just shell           # SSH into app container
just db-shell        # Open PostgreSQL CLI
just logs            # Stream all service logs
just logs-worker     # Stream only Celery worker logs
```

All commands are safe for development—no production commands like `git push` allowed by design.

### **Init Script** — Automated Setup

`scripts/init_env.sh` handles:

1. ✓ Checks `.env` doesn't already exist
2. ✓ Copies from `.env.example` template
3. ✓ Generates cryptographically secure JWT secret via `openssl`
4. ✓ Prints validation instructions

**Why automate this?**

- Prevents accidental .env commits (secret in .env.example would be compromised)
- New developers start quickly with correct configuration
- Consistent across all environments

---

## 📐 Project Structure

```
python/
├── README.md                          # This file
├── justfile                           # Command runner tasks
├── docker-compose.yml                 # Full stack orchestration
├── scripts/
│   └── init_env.sh                    # Automated .env setup
├── server/
│   ├── Dockerfile                     # Multi-stage build (builder → runner)
│   ├── requirements.txt               # Python dependencies
│   ├── pytest.ini                     # Test configuration
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory + lifespan
│   │   ├── tasks.py                   # Celery tasks (async cleanup)
│   │   ├── logging_config.py          # Structured logging
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   └── router.py          # Main API router (includes all domains)
│   │   │   └── debug/
│   │   │       └── router.py          # Debug routes (DEBUG=True only)
│   │   ├── auth/
│   │   │   ├── router.py              # /auth/signup, /auth/login, /auth/refresh, /auth/verify
│   │   │   ├── service.py             # Authentication business logic
│   │   │   ├── dependencies.py        # JWT validation (get_current_user)
│   │   │   └── schemas.py             # Pydantic models
│   │   ├── user/
│   │   │   ├── router.py              # /me (current user profile)
│   │   │   ├── service.py             # User profile operations
│   │   │   ├── models.py              # User ORM model
│   │   │   └── schemas.py             # User validation schemas
│   │   ├── social/
│   │   │   ├── router.py              # Posts/comments/likes endpoints
│   │   │   ├── service.py             # Post/comment/like business logic
│   │   │   ├── models.py              # Post, Comment, Like ORM models
│   │   │   └── schemas.py             # Social domain schemas
│   │   ├── core/
│   │   │   ├── config.py              # Settings from .env (JWT, DB, Redis)
│   │   │   ├── database.py            # AsyncSession factory, init_db()
│   │   │   ├── security.py            # JWT encode/decode, password hashing
│   │   │   └── exception_handlers.py  # Global error handlers
│   │   └── worker.py                  # Celery app instance
│   └── tests/
│       ├── conftest.py                # Pytest fixtures (TestingSessionLocal)
│       ├── test_auth.py               # Auth + user tests
│       └── test_social.py             # Posts/comments/likes tests
└── .env.example                       # Template for .env (safe to commit)
```

---

## 🔐 Security & Design Decisions

### Authentication Flow

```
POST /auth/signup         → Email verification code (printed to console for dev)
POST /auth/verify         → Mark user is_verified=True
POST /auth/login          → JWT access token (30 min) + refresh token (7 days)
POST /auth/refresh        → New access token (old refresh token still valid)

Authorization: Bearer <access_token>
```

**Why this flow?**

- ✓ Stateless (no session table needed)
- ✓ Scalable (services can validate token without DB)
- ✓ Security: short-lived access tokens, long-lived refresh for UX

### Social Features: Business Rules

```
Posts:
  - Only verified users can create
  - Only author can edit/delete
  - Search by title/content, filter by date range

Comments:
  - Only verified users can comment
  - Only author can delete
  - Cascading: deleting post deletes all comments

Likes:
  - Users cannot like their own post
  - One like per user per post (composite key constraint)
  - Deleting post deletes all likes automatically
```

**Why constraints?**

- ✓ Prevent spam (one-like limit)
- ✓ Fair engagement (no self-promotion)
- ✓ Data integrity (cascade delete cleans orphans)

### Password Security

- ✓ Bcrypt hashing (automatic salting, work factor=12)
- ✓ Never store plaintext or reversible encryption
- ✓ Verification codes printed to console in dev (use email service in production)

---

## 🧪 Testing Strategy

### Coverage Areas

**Authentication Tests** (`test_auth.py`)

- Signup: valid email, duplicate prevention
- Verification: code expiration (24-hour TTL), cleanup task
- Login/Refresh: token generation, invalid credentials
- Protected routes: require verified users

**Social Domain Tests** (`test_social.py`)

- Post CRUD: author-only updates, verified-only creation
- Pagination: `skip`/`limit` parameters
- Search: title/content filtering
- Comments: creation, deletion, cascading
- Likes: constraint validation, cannot self-like, one-per-user

**Test Infrastructure**

- Async test runner (pytest-asyncio)
- TestingSessionLocal for isolated database sessions
- AsyncClient for HTTP endpoint simulation
- Fixture-based setup (DRY, fast)

### Running Tests

```bash
# In Docker (recommended)
just test

# Locally (requires PostgreSQL + Redis)
cd server && pytest -o asyncio_mode=auto tests/
```

---

## 🔄 Background Tasks (Celery)

### Scheduled Job: Cleanup Unverified Users

```python
# app/tasks.py
@celery.task
async def async_cleanup_unverified_users():
    """Delete unverified accounts after 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    deleted = await db.delete(
        User.where(is_verified==False, verification_code_expires_at<=cutoff)
    )
    logger.info(f"Cleaned up {deleted} expired verification codes")
```

**Runs**: Every hour at minute 0 (configured in Celery Beat)
**Why async?**: Non-blocking I/O with asyncpg; database connection pooling
**Why Celery?**: Horizontal scaling (add more workers), monitoring, retry logic

---

## 📊 Database Schema

### Users Table

```sql
id                          UUID PRIMARY KEY
email                       VARCHAR UNIQUE NOT NULL
username                    VARCHAR UNIQUE NOT NULL (3-32 alphanumeric + _)
full_name                   VARCHAR NOT NULL
password_hash               VARCHAR NOT NULL (bcrypt)
is_verified                 BOOLEAN DEFAULT FALSE
verification_code           VARCHAR(6) NULLABLE
verification_code_expires_at TIMESTAMP WITH TIMEZONE NULLABLE
created_at                  TIMESTAMP WITH TIMEZONE DEFAULT NOW()
updated_at                  TIMESTAMP WITH TIMEZONE DEFAULT NOW()
```

### Posts Table

```sql
id                  UUID PRIMARY KEY
author_id           UUID FOREIGN KEY (Users) ON DELETE CASCADE
title               VARCHAR NOT NULL (5-255 chars)
content             TEXT NOT NULL (≤10,000 chars)
created_at          TIMESTAMP WITH TIMEZONE DEFAULT NOW()
updated_at          TIMESTAMP WITH TIMEZONE DEFAULT NOW()
```

### Comments Table

```sql
id                  UUID PRIMARY KEY
post_id             UUID FOREIGN KEY (Posts) ON DELETE CASCADE
author_id           UUID FOREIGN KEY (Users) ON DELETE CASCADE
content             TEXT NOT NULL (≤2,000 chars)
created_at          TIMESTAMP WITH TIMEZONE DEFAULT NOW()
```

### Likes Table

```sql
user_id             UUID FOREIGN KEY (Users) ON DELETE CASCADE
post_id             UUID FOREIGN KEY (Posts) ON DELETE CASCADE
created_at          TIMESTAMP WITH TIMEZONE DEFAULT NOW()

PRIMARY KEY (user_id, post_id)  -- Ensures one like per user
```

**Design decisions:**

- ✓ UUID for all IDs (horizontally scalable, no leakage)
- ✓ Timezone-aware timestamps (always UTC)
- ✓ Composite key on Likes (database enforces uniqueness)
- ✓ Cascade delete (referential integrity)

---

## 🐳 Docker Architecture

### Multi-Stage Build Benefits

```dockerfile
# Stage 1: Builder
FROM python:3.13-alpine AS builder
→ Installs gcc, postgresql-dev (build deps)
→ Compiles wheels from requirements
→ ~500MB (discarded after building)

# Stage 2: Runner
FROM python:3.13-alpine AS runner
→ Only postgresql-libs, libffi (runtime deps)
→ Copies precompiled wheels
→ FINAL IMAGE: ~150MB (60% smaller)
```

**Result**: Faster startup, less storage, fewer attack surface

### Services in docker-compose.yml

| Service           | Image                | Port | Purpose                             |
| ----------------- | -------------------- | ---- | ----------------------------------- |
| **db**            | postgres:16-alpine   | 5432 | Primary database                    |
| **redis**         | redis:7-alpine       | 6379 | Celery broker + result backend      |
| **app**           | custom (multi-stage) | 8000 | FastAPI server (auto-reload in dev) |
| **celery_worker** | custom               | —    | Background task processing          |
| **celery_beat**   | custom               | —    | Periodic task scheduling            |

**Health Checks**: All services have liveness probes; app waits for db/redis readiness

---

## 🚨 Error Handling

### Global Exception Handlers

All errors return structured JSON with human-friendly messages:

```json
{
  "status_code": 422,
  "detail": "Email already registered",
  "error_code": "EMAIL_TAKEN"
}
```

**Handled Errors:**

- 400: Validation failed (email format, field constraints)
- 401: Invalid credentials or expired token
- 403: User not verified, or not authorized (e.g., non-author trying to edit)
- 404: Resource not found
- 409: Business rule violation (e.g., duplicate like)
- 500: Unhandled server error (logged with traceback)

---

## 📈 Scaling Considerations

This architecture supports:

- **Horizontal API scaling**: Stateless JWT; add more app containers
- **Celery workers**: Spawn workers on demand; Redis handles queuing
- **Database scaling**: PostgreSQL async connections; can add read replicas
- **Caching layer**: Redis already configured; easy to add in-memory caching
- **CDN**: All responses are stateless; can cache aggressively

**Not yet implemented** (out of scope):

- GraphQL layer
- WebSocket support
- Search indexing (Elasticsearch)
- API rate limiting
- Request logging middleware

---

## 🎯 Development Workflow

### Day-to-Day

```bash
# Start development environment
just start

# In another terminal: monitor logs
just logs

# Run tests after making changes
just test

# Debug a specific endpoint
just shell
# Now inside container:
curl -X GET http://localhost:8000/docs

# Access database directly
just db-shell
# Now in psql:
SELECT * FROM users LIMIT 5;
```

### Making Changes

1. Edit `app/*/router.py` (endpoint logic)
2. Update `app/*/service.py` (business logic)
3. Modify `app/*/schemas.py` (validation)
4. Add `app/*/tests/test_*.py` (tests)
5. Run `just test` to verify

**Principle**: Code flows top→down (Router → Service → Model); testing flows bottom→up (Model → Service → Router)

---

## 📋 API Endpoints (Full Reference)

### Authentication

```
POST   /auth/signup                Register new user
POST   /auth/login                 Get access + refresh tokens
POST   /auth/refresh               Get new access token
POST   /auth/verify                Verify email with code
```

### User Profile

```
GET    /me                         Current user profile
PATCH  /me                         Update profile
```

### Posts

```
GET    /posts                      List posts (paginated, searchable)
POST   /posts                      Create post (verified only)
GET    /posts/{id}                 Get post details + comments
PATCH  /posts/{id}                 Update post (author only)
DELETE /posts/{id}                 Delete post (author only)
```

### Comments

```
POST   /posts/{id}/comments        Create comment (verified only)
DELETE /posts/{id}/comments/{id}   Delete comment (author only)
```

### Likes

```
POST   /posts/{id}/like            Like post (no self-likes)
DELETE /posts/{id}/like            Unlike post
```

### Feed

```
GET    /posts/all/feed             Aggregated user profiles with posts
```

---

## 🔍 Code Quality Practices

✓ **Type hints throughout** (Python 3.13+)
✓ **Async/await for non-blocking I/O**
✓ **Dependency injection** (FastAPI Depends)
✓ **Structured logging** (datetime, log level, context)
✓ **Pydantic validation** (schemas enforce contracts)
✓ **Database constraints** (NOT NULL, UNIQUE, FK)
✓ **Comprehensive tests** (auth + social domains)
✓ **Clean Git history** (meaningful commits, no merge conflicts)

---

## 🎓 Lessons & Decisions

### Why Not Built-In Roles?

Initially explored role-based access (admin, moderator, user) but **decided against** because:

1. Scope didn't require it (spec focuses on individual users)
2. Over-engineering for current needs
3. Can add roles later via separate `user_roles` table + junction table

### Why Celery for Cleanup Task?

Alternatives considered:

- ❌ **Cron job**: Requires SSH access to production server
- ❌ **APScheduler**: Synchronous; would block API threads
- ✓ **Celery Beat**: Distributed, async-native, horizontally scalable, monitoring-ready

### Why Not GraphQL?

- Scope: Simple CRUD operations
- REST is sufficient; easier to reason about
- GraphQL adds complexity; can add later if needed

### Why AsyncIO?

- FastAPI optimized for it
- Database driver (asyncpg) is async-native
- Better resource utilization (single-threaded event loop vs thread pool)
- Production-ready

---

## 📝 Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/users_db

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET_KEY=<auto-generated secure random>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme
POSTGRES_DB=users_db

# App
DEBUG=True
PROJECT_NAME=Users API
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
```

Generate via: `./scripts/init_env.sh`

---

## 🎯 Takeaways: Why This Architecture?

| Principle                | Implementation                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------ |
| **Reliability**          | Health checks, cascade delete, transaction management, error handling                |
| **Maintainability**      | 3-layer separation, dependency injection, clear naming, comprehensive tests          |
| **Scalability**          | Stateless JWT, async I/O, horizontal Celery workers, database-agnostic ORM           |
| **Security**             | Bcrypt passwords, JWT tokens, SQL injection prevention (parameterized queries), CORS |
| **Developer Experience** | Docker for consistency, Justfile for convenience, hot reload, auto API docs          |

**Hiring Signal**: This codebase shows the author understands **why** each technology was chosen, **when** to say "no" to features (scope discipline), and **how** to build systems that scale without over-engineering.

---

## 📞 Questions?

For technical discussions, interview preparation, or feedback:

**Telegram**: [@obidkhandev](https://t.me/obidkhandev)

---

**Built with intentional architectural decisions. Ready for production.**
