# XTask Backend API

Backend API for XTask built with **Python + FastAPI** using a **microservices architecture** with **database-per-schema** isolation.

## Tech Stack

- **Python 3.13+**
- **FastAPI** — Web framework
- **SQLAlchemy 2.0** — Async ORM
- **PostgreSQL 18** — Database (schema-per-service isolation)
- **Alembic** — Database migrations
- **Pydantic v2** — Data validation
- **JWT (PyJWT)** — Authentication & RBAC
- **Docker Compose** — Local development
- **Structlog** — Structured logging
- **Pytest** — Test suite (48 tests)

## Project Structure

```
Backend/
├── gateway/                        # API Gateway (entry point)
│   └── main.py                    # FastAPI app, CORS, proxy, health checks
├── services/                       # Microservices (8 services)
│   ├── auth/                      # Authentication & Users
│   │   ├── models.py             # SQLAlchemy models (schema: svc_auth)
│   │   ├── schemas.py            # Pydantic schemas (API contracts)
│   │   ├── repository.py         # Database queries
│   │   ├── service.py            # Business logic
│   │   └── router.py             # API endpoints
│   ├── projects/                  # Project management (svc_projects)
│   ├── employees/                 # Employee management (svc_employees)
│   ├── finance/                   # Budgets & invoices (svc_finance)
│   ├── payroll/                   # Payroll & nominations (svc_payroll)
│   ├── kpis/                      # KPIs & evaluation (svc_kpis)
│   ├── skills/                    # Skills management (svc_skills)
│   └── dashboard/                 # Dashboard layouts & widgets (svc_dashboard)
├── shared/                         # Shared infrastructure & patterns
│   ├── config.py                  # Settings (env vars, per-service DB URLs)
│   ├── database.py                # DB engines & sessions (schema-aware)
│   ├── dependencies.py            # FastAPI dependencies (auth, RBAC)
│   ├── exceptions.py              # Custom HTTP exceptions
│   ├── logging.py                 # Structured logging (structlog)
│   ├── middleware.py              # Request ID, logging, error handling
│   ├── schemas.py                 # Base response schemas (PaginatedResponse)
│   ├── repository.py             # Generic BaseRepository (CRUD + pagination)
│   ├── unit_of_work.py           # UnitOfWork (atomic multi-repo transactions)
│   ├── service_app.py            # Service app factory
│   ├── events.py                 # Observer — EventBus (inter-service events)
│   ├── strategies.py             # Strategy — Salary & execution calculations
│   ├── validators.py             # Chain of Responsibility — Validation pipelines
│   ├── state_machine.py          # State — Entity lifecycle state machines
│   ├── repository_decorators.py  # Decorator — AuditedRepository, CachedRepository
│   └── builders.py               # Builder — Fluent response builder
├── alembic/                        # Database migrations
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_salary_varchar_to_numeric.py
│       └── 003_move_tables_to_service_schemas.py
├── tests/                          # Test suite (48 tests)
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Architecture

### Clean Architecture per Service

Each microservice follows a layered architecture:

```
router.py      → HTTP layer (endpoints, request/response)
service.py     → Business logic (use cases, rules, strategies)
repository.py  → Data access (DB queries, filters)
models.py      → SQLAlchemy ORM models (schema-bound)
schemas.py     → Pydantic schemas (API contracts with frontend)
```

### Database-per-Schema

Each service owns its data in an isolated PostgreSQL schema within the same database. Cross-service foreign keys are removed — references are maintained at the application level.

| Schema | Tables | Service |
|--------|--------|---------|
| `svc_auth` | `users` | Auth |
| `svc_projects` | `projects` | Projects |
| `svc_employees` | `employees`, `employee_projects` | Employees |
| `svc_finance` | `budgets`, `invoices` | Finance |
| `svc_payroll` | `payrolls` | Payroll |
| `svc_kpis` | `kpis` | KPIs |
| `svc_skills` | `skills` | Skills |
| `svc_dashboard` | `dashboard_layouts`, `dashboard_widgets` | Dashboard |

Each router uses `get_service_db("service_name")` which creates an async session with the correct `search_path`. To migrate to fully separate databases, only environment variables need to change — zero code modifications.

## Design Patterns

### Pre-existing (foundational)

| Pattern | Location | Usage |
|---------|----------|-------|
| **Singleton** | `shared/config.py` | `get_settings()` with `@lru_cache`; engine/session caching in `database.py` |
| **Factory Method** | `shared/database.py`, `shared/service_app.py` | `get_service_db()` creates per-schema sessions; `create_service_app()` builds FastAPI apps |
| **Template Method** | `shared/repository.py` | `BaseRepository._apply_filters()` hook overridden by subclasses for custom query logic |
| **Proxy** | `gateway/main.py` | `ProxyClient` intercepts and forwards requests to microservices |
| **Facade** | `services/*/service.py` | Each `Service` class simplifies interaction with repositories and business rules |

### Newly implemented

| Pattern | Module | Usage |
|---------|--------|-------|
| **Observer** | `shared/events.py` | `EventBus` — async event bus with `@event_bus.on("event")` decorator and `await event_bus.emit()`. Enables inter-service communication without coupling. |
| **Strategy** | `shared/strategies.py` | `SalaryStrategy` (Standard, Colombian, Contractor) for payroll net salary calculation. `ExecutionStrategy` (Standard, Alert) for budget execution metrics. Strategies are injected into services via constructor. |
| **Chain of Responsibility** | `shared/validators.py` | Composable validation pipelines: `RequiredFieldsValidator → PositiveAmountValidator → StatusTransitionValidator → EntityExistsValidator`. Validators chain via `.then()` and raise `ValidationException` on failure. |
| **State** | `shared/state_machine.py` | Declarative state machines (`PROJECT_STATES`, `PAYROLL_STATES`, `INVOICE_STATES`, `BUDGET_STATES`, `KPI_STATES`) that enforce valid transitions and reject invalid ones with descriptive errors. |
| **Decorator** | `shared/repository_decorators.py` | `AuditedRepository` wraps any repository to add structured logging + event emission on create/update/delete. `CachedRepository` adds in-memory read caching with automatic invalidation on writes. Decorators stack: `AuditedRepository(CachedRepository(repo))`. |
| **Builder** | `shared/builders.py` | `ResponseBuilder` — fluent API for constructing paginated responses: `.with_items().with_pagination().with_filters().build()`. Used across all service list endpoints. |

### Pattern integration by service

| Service | Patterns applied |
|---------|-----------------|
| **PayrollService** | Strategy (salary calc), Chain (create validation), State (status transitions), Builder (pagination), Decorator (audit) |
| **ProjectService** | State (status transitions), Builder (pagination), Decorator (audit) |
| **BudgetService** | Strategy (execution calc), Builder (pagination) |
| **InvoiceService** | State (status transitions), Builder (pagination) |
| **EmployeeService** | Builder (pagination) |
| **KpiService** | Builder (pagination) |
| **SkillService** | Builder (pagination) |

## Quick Start

### 1. Clone & setup
```bash
git clone https://github.com/Victoria239/Backend_Xtask.git
cd Backend_Xtask
cp .env.example .env
```

### 2. Start infrastructure (Docker)
```bash
docker-compose up -d postgres
```

### 3. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

### 4. Run migrations
```bash
python -m alembic upgrade head
```

### 5. Run the API
```bash
uvicorn gateway.main:app --reload --port 8000
```

### 6. Open API docs
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

## Running Tests

```bash
pytest                                    # Run all 48 tests
pytest -v                                 # Verbose output
pytest --cov=services --cov=shared        # With coverage
```

## Branching Strategy

See [BRANCHING_STRATEGY.md](BRANCHING_STRATEGY.md) for details.

- `main` → Production
- `develop` → Integration
- `feature/*` → New features
- `fix/*` → Bug fixes