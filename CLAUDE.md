# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GepviReports** — Reporting and notification with AI-powered analysis for personal tracking applications. FastAPI backend. Stack: FastAPI, SQLModel, Alembic (custom NNNN versioning), AsyncPG, Pytest, OpenRouter AI.

## Python Environment

Always use: `/Users/herman_max/envs/gepvi_reports/bin/python`

## Essential Commands

```bash
# Migrations (NNNN format) - NEVER modify alembic/env.py
alembic revision --autogenerate -m "description"
alembic upgrade head

# Tests
pytest tests/ -v

# Run services
uvicorn web.main:app --reload --port 8008

# Docker
docker-compose up -d
```

## Architecture: Strict Layer Separation

**CRITICAL**: Never mix layers!
- **`app/`** — Pure business logic, no FastAPI/HTTP dependencies
- **`web/`** — HTTP layer only, delegates to `app/services.py`
- **`settings/`** — Centralized config
- **`clients/`** — External integrations (AI, payments, etc.)

### Business Logic Rule (CRITICAL):
**ALL business logic MUST be in `app/services.py` ONLY!**
- ❌ NEVER put business logic in `web/routes/` (views are thin, only HTTP handling)
- ❌ NEVER create separate business logic files outside `app/services.py`
- ✅ Routes in `web/routes/` should only: validate input, call `app/services.py`, return response
- ✅ All domain logic (generation, calculations, state changes) goes in `app/services.py`
- ✅ If `services.py` grows large, convert to `app/services/` directory with modules

Key files:
wise_tests_bot/
├── alembic/                    # Миграции базы данных
│   ├── env.py                 # Настройка Alembic (кастомная система версионирования)
│   ├── script.py.mako         # Шаблон миграций
│   └── versions/              # Файлы миграций (формат: NNNN_description.py)
│
├── app/                        # Бизнес-логика приложения
│   ├── models/                # SQLModel модели
│   │   ├── base.py           # Базовая настройка metadata (schema: gepvi_reports)
│   ├── database.py           # Async database engine и сессии
│   ├── schemas.py            # Pydantic схемы для API
│   ├── services.py           # Бизнес-логика (CRUD операции)
│   └── utils/                # Утилитные функции
│       └── error_handler.py  # Базовые ошибки для всего app, web модулей
│
├── web/                        # FastAPI web-слой (REST API)
│   ├── main.py               # Инициализация FastAPI app
│   └── routes/               # API endpoints
│
├── clients/                    # Shared HTTP clients (used by bot and backend)
│   └── gepvi_users_client.py   # HTTP client for gepvi_reports API
│
├── settings/                   # Конфигурация приложения
│   ├── config.py             # AppConfig с настройками из env
│   └── logs.py               # Настройки логирования
│
├── tests/                      # Тесты
│   ├── conftest.py           # Pytest fixtures (apply_migrations и др.)
│   ├── test_migrations.py    # Тесты миграций
│   └── api_tests/            # Тесты API endpoints
│
├── docker-compose.yml          # Оркестрация: PostgreSQL, FastAPI, Bot
├── Dockerfile.api             # Dockerfile для FastAPI
├── Dockerfile.bot             # Dockerfile для Telegram бота
├── alembic.ini                # Конфигурация Alembic
├── pytest.ini                 # Конфигурация pytest
└── requirements.txt           # Python зависимости

**Available Routes** (always check before adding new):
{add new routes here}
**Rule**: Before creating new route file, verify no existing route covers the feature. Prefer extending existing routes.

## Database

**Schema**: `gepvi_reports` (all tables in dedicated PostgreSQL schema)

**Key tables**:
{add new tables here}

**Pattern**: All DB operations async via `AsyncSession`, use `Depends(get_session)` in FastAPI endpoints

### Database Query Best Practices (CRITICAL)

**NEVER do N+1 queries!** This is the most common performance killer.

❌ **BAD - N+1 Problem**:
```python
# DON'T DO THIS!
daily_breakdown = []
current_date = start_date
while current_date <= end_date:
    daily_stats = await get_daily_stats(session, user_id, current_date)  # Query in loop!
    daily_breakdown.append(daily_stats)
    current_date += timedelta(days=1)
```

✅ **GOOD - Single Query with GROUP BY**:
```python
# Get all data in ONE query using GROUP BY
stmt = select(
    func.date(Meal.created_at).label('date'),
    func.sum(Meal.calories).label('total_calories'),
    func.count(Meal.id).label('meals_count')
).where(
    Meal.user_id == user_id,
    Meal.created_at >= start_date,
    Meal.created_at <= end_date
).group_by(func.date(Meal.created_at))

result = await session.execute(stmt)
daily_breakdown = [process_row(row) for row in result.all()]
```

**Rules**:
- ❌ NEVER use loops with database queries inside (while/for with await query)
- ❌ NEVER make multiple queries when one query with aggregation can do the job
- ✅ Use GROUP BY, JOIN, subqueries to get all data in one query
- ✅ Aggregate data in Python if SQL aggregation is complex
- ✅ If you need counts from the same table, combine into one query with multiple COUNT(DISTINCT ...)


## Code Patterns

1. **Async/await** — All I/O operations async
2. **Type hints** — Required everywhere
3. **Dependency injection** — Use FastAPI `Depends()`
4. **Minimal docstrings** — One-line only, no Args/Returns/Raises
5. **Custom exceptions** — `app/utils/error_handler.py`: NotFoundError, ValidationError
6. **Self-documenting code** — Code should be readable without comments. Use comments only when explaining non-obvious business logic or important context that cannot be expressed in code
7. **Imports at module top (CRITICAL)** — ALWAYS place ALL imports at the top of the file
   - ❌ NEVER use imports inside functions (e.g., `from module import func` inside a function body)
   - ❌ NEVER use lazy imports unless absolutely required for circular dependency resolution
   - ✅ All imports must be at module level (top of file)
   - ✅ Group imports: stdlib → third-party → local modules
   - **Exception**: Only for genuine circular dependency issues (extremely rare)
8. **Error handling** — NEVER return None on errors in client/service functions. Always raise appropriate exceptions (HTTPError, NotFoundError, etc.) and let callers handle them explicitly
9. **Datetime handling with arrow (CRITICAL)** — ALWAYS use `arrow` library for all datetime operations

## Code Quality Principles (CRITICAL)

**DRY (Don't Repeat Yourself)**:
- ❌ NEVER duplicate logic in separate functions
- ❌ NEVER create multiple functions that do essentially the same thing with minor variations
- ✅ Write ONE function that handles all cases
- ✅ Use parameters/flags to handle variations
- ✅ If you need to ignore return values, use `_` unpacking (e.g., `value, _ = func()`)

**KISS (Keep It Simple, Stupid)**:
- ❌ NEVER overcomplicate with excessive try-except blocks for the same pattern
- ❌ NEVER create verbose code when simple iteration suffices
- ✅ Use loops and data structures to eliminate repetition
- ✅ Prefer dict iteration over multiple if-elif chains for parsing
- ✅ Simple, readable code > clever but complex code

**Before writing code, ask yourself**:
1. Does similar functionality already exist?
2. Can I modify existing code instead of duplicating?
3. Is this the simplest solution?
4. Am I repeating the same pattern multiple times?

## Git Workflow

**CRITICAL**: NEVER create git commits automatically!
- ❌ NEVER run `git add`, `git commit`, or `git push` without explicit user request
- ✅ Only create commits when user explicitly asks (e.g., "create a commit", "commit these changes")
- ✅ Always run tests BEFORE committing
- ✅ Show `git diff` to user if they want to review changes

## Testing

**CRITICAL**: Always write API tests (HTTP-based), not unit tests for service functions!

- **API tests** (preferred): Test through HTTP endpoints using `async_client` fixture
  - Example: `response = await async_client.post("/users/get_or_create", params={"user_id": "test"})`
  - Use `tests/api_tests/test_webhook.py` as reference
  - Tests should use real HTTP calls to FastAPI endpoints

- **Unit tests** (only for internal helpers): For pure functions without HTTP endpoints
  - Example: `reset_daily_limits_if_needed()`, `add_to_context_history()`
  - These functions are not exposed via API, so test them directly

**Rule**: If a feature has an API endpoint, test it through the API, not by calling service functions directly.

## Adding Features

**Backend**: Model → Schema → Service → Route → Migration → Tests
**Bot**: Handler → Keyboard → gepvi_reports_client method (if new API endpoint needed)

## Critical Notes

- **Custom Alembic**: NNNN versioning (0001, 0002...). **NEVER modify `alembic/env.py`**
- **Schema**: All tables in `gepvi_reports` PostgreSQL schema
- **Bot isolation**: Never import app/database in bot code, HTTP only
- **API auth**: All endpoints require `X-API-Key` header (except /, /health, /docs, /webhook/*)
- **Environment**: See `.env` for DB_URL, TELEGRAM_BOT_TOKEN, API_URL, OPENROUTER_API_KEY, etc.