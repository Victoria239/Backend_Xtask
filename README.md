# XTask Backend API

Backend API for XTask built with **Python + FastAPI** using a **microservices architecture**.

## Tech Stack

- **Python 3.11+**
- **FastAPI** - Web framework
- **SQLAlchemy 2.0** - ORM (async)
- **PostgreSQL 16** - Database
- **Redis 7** - Cache & sessions
- **Alembic** - Database migrations
- **Pydantic v2** - Data validation
- **JWT** - Authentication
- **Docker Compose** - Local development
- **Structlog** - Structured logging

## Project Structure

```
Backend/
├── gateway/                    # API Gateway (entry point)
│   ├── main.py                # FastAPI app, CORS, router registration
│   └── Dockerfile
├── services/                   # Microservices
│   ├── auth/                  # Authentication & Users
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas (API contracts)
│   │   ├── repository.py     # Database queries
│   │   ├── service.py        # Business logic
│   │   └── router.py         # API endpoints
│   ├── projects/              # Project management
│   ├── employees/             # Employee management
│   ├── finance/               # Budgets, invoices, reports, audits
│   ├── payroll/               # Payroll & nominations
│   ├── kpis/                  # KPIs & bonuses
│   ├── skills/                # Skills management
│   └── dashboard/             # Dashboard layouts & widgets
├── shared/                     # Shared code
│   ├── config.py              # Settings (env vars)
│   ├── database.py            # DB engine & session
│   ├── dependencies.py        # FastAPI dependencies (auth, etc.)
│   ├── exceptions.py          # Custom exceptions
│   ├── logging.py             # Structured logging
│   └── schemas.py             # Base response schemas
├── tests/                      # Test suite
├── docker-compose.yml          # Local dev infrastructure
├── pyproject.toml              # Dependencies & tooling config
└── .env.example                # Environment variables template
```

## Architecture

Each microservice follows **Clean Architecture**:

```
router.py    → HTTP layer (endpoints, request/response)
service.py   → Business logic (use cases, rules)
repository.py → Data access (DB queries)
models.py    → SQLAlchemy ORM models
schemas.py   → Pydantic schemas (API contracts with frontend)
```

## Quick Start

### 1. Clone & setup
```bash
git clone https://github.com/Victoria239/Backend_Xtask.git
cd Backend_Xtask
git checkout develop
cp .env.example .env
```

### 2. Start infrastructure (Docker)
```bash
docker-compose up -d postgres redis
```

### 3. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

### 4. Run the API
```bash
uvicorn gateway.main:app --reload --port 8000
```

### 5. Open API docs
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Branching Strategy

See [BRANCHING_STRATEGY.md](BRANCHING_STRATEGY.md) for details.

- `main` → Production
- `develop` → Integration
- `feature/*` → New features
- `fix/*` → Bug fixes

## Running Tests

```bash
pytest
pytest --cov=services --cov=shared
```