# Gepvi Reports - Reporting & Notifications Microservice

Микросервис для создания отчетов и управления уведомлениями с AI-анализом для GepCalories. Обрабатывает задачи отчетности, генерацию AI-анализа и отправку уведомлений.

## 🏗 Архитектура

Независимый микросервис с собственной базой данных, взаимодействующий с другими сервисами через HTTP API.

### Основные директории:

```
gepvi_reports/
├── app/                    # Бизнес-логика
│   ├── models/            # SQLModel модели
│   ├── services.py        # Бизнес-логика
│   ├── schemas.py         # Pydantic схемы
│   ├── database.py        # Подключение к БД
│   └── utils/             # Утилиты
├── web/                    # HTTP слой (FastAPI)
│   ├── main.py            # FastAPI приложение
│   ├── routes/            # API endpoints
│   └── middleware.py      # Middleware (auth)
├── clients/                # Внешние интеграции (OpenRouter AI)
├── settings/               # Конфигурация
├── alembic/                # Миграции БД
└── tests/                  # Pytest тесты
```

## 🛠 Технологический стек

- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL + SQLModel + Alembic
- **AI**: OpenRouter API
- **Testing**: Pytest + AsyncPG
- **Deploy**: Docker

## ✨ Основные возможности

1. **Управление отчетами**
   - Создание отчетов с AI-анализом
   - Хранение результатов анализа
   - Получение отчетов по пользователю
   - Поддержка различных типов отчетов (day/week/month)

2. **Управление задачами**
   - Планирование периодических задач
   - Отслеживание времени выполнения
   - Гибкая настройка периода (day/week/month)

3. **Система уведомлений**
   - Отправка уведомлений различными методами (telegram/email/push)
   - Хранение истории уведомлений
   - Дополнительные метаданные (JSONB)

## 📦 Быстрый старт

### 1. Установите зависимости

```bash
cd gepvi_reports
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройте окружение

Создайте `.env` файл:

```env
# Database
DB_URL=postgresql+asyncpg://user:password@localhost:5432/gepvi_reports
TEST_DB_URL=postgresql+asyncpg://user:password@localhost:5432/gepvi_reports_test

# API
API_KEY=your_secure_api_key_here
PORT=8008

# OpenRouter AI
OPENROUTER_API_KEY=your_openrouter_api_key

# Sentry (optional)
SENTRY_DSN=
```

### 3. Примените миграции

```bash
alembic upgrade head
```

### 4. Запустите сервис

```bash
uvicorn web.main:app --reload --port 8008
```

## 🔌 API Endpoints

### Отчеты

```bash
# Получить все отчеты пользователя
GET /reports/user/{user_id}
Headers: X-API-Key: your_api_key

Response: [
  {
    "id": 1,
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "report_type": "day",
    "result": "AI analysis result...",
    "task_id": 1,
    "created_at": "2026-01-22T00:00:00+00:00",
    "updated_at": "2026-01-22T00:00:00+00:00"
  }
]
```

### Задачи

```bash
# Получить все задачи пользователя
GET /tasks/user/{user_id}
Headers: X-API-Key: your_api_key

Response: [
  {
    "id": 1,
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "next_task_time": "2026-01-23T00:00:00+00:00",
    "period": "day",
    "created_at": "2026-01-22T00:00:00+00:00",
    "updated_at": "2026-01-22T00:00:00+00:00"
  }
]
```

### Уведомления

```bash
# Получить все уведомления пользователя
GET /notifications/user/{user_id}
Headers: X-API-Key: your_api_key

Response: [
  {
    "id": 1,
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Your daily report is ready!",
    "sender_method": "telegram",
    "meta": {"chat_id": "123456"},
    "created_at": "2026-01-22T00:00:00+00:00",
    "updated_at": "2026-01-22T00:00:00+00:00"
  }
]
```

## 📊 База данных

### Схема: `gepvi_reports`

### Таблица `reports`

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | ID (PK) |
| `user_id` | UUID | UUID пользователя |
| `report_type` | VARCHAR | Тип отчета (day/week/month) |
| `result` | TEXT | Результат AI-анализа |
| `task_id` | INTEGER | ID задачи (FK на tasks) |
| `created_at` | TIMESTAMPTZ | Дата создания |
| `updated_at` | TIMESTAMPTZ | Дата обновления |

### Таблица `tasks`

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | ID (PK) |
| `user_id` | UUID | UUID пользователя |
| `next_task_time` | TIMESTAMPTZ | Время следующего выполнения |
| `period` | VARCHAR | Период (day/week/month) |
| `created_at` | TIMESTAMPTZ | Дата создания |
| `updated_at` | TIMESTAMPTZ | Дата обновления |

### Таблица `notifications`

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | ID (PK) |
| `user_id` | UUID | UUID пользователя |
| `text` | VARCHAR | Текст уведомления (optional) |
| `sender_method` | VARCHAR | Метод отправки (telegram/email/push) |
| `meta` | JSONB | Дополнительные метаданные |
| `created_at` | TIMESTAMPTZ | Дата создания |
| `updated_at` | TIMESTAMPTZ | Дата обновления |

## 🧪 Тестирование

```bash
pytest tests/ -v
```

## 🔐 Аутентификация

Все endpoints требуют API ключ в заголовке `X-API-Key`, кроме:
- `GET /` — health check
- `GET /health` — health check
- `GET /docs` — Swagger UI

## 🔄 Интеграция с GepCalories

GepCalories основной сервис обращается к gepvi_reports через HTTP API:

```python
# В GepCalories
async def get_user_reports(user_id: str) -> list:
    """Получить отчеты пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REPORTS_SERVICE_URL}/reports/user/{user_id}",
            headers={"X-API-Key": API_KEY}
        )
        return response.json()

async def get_user_tasks(user_id: str) -> list:
    """Получить задачи пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REPORTS_SERVICE_URL}/tasks/user/{user_id}",
            headers={"X-API-Key": API_KEY}
        )
        return response.json()

async def get_user_notifications(user_id: str) -> list:
    """Получить уведомления пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REPORTS_SERVICE_URL}/notifications/user/{user_id}",
            headers={"X-API-Key": API_KEY}
        )
        return response.json()
```

## 📝 Примечания

- **Идентификатор**: UUID пользователя из сервиса gepvi_users
- **Периоды**: day, week, month (без enum для гибкости)
- **Временные метки**: Используется timestamptz для правильной работы с часовыми поясами
- Используется схема `gepvi_reports` для изоляции данных
- Все async I/O операции
- Type hints везде
- Custom NNNN формат миграций (0001)
- Полная изоляция от других сервисов

## 📄 Лицензия

MIT
