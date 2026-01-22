# Gepvi Users - User Management & Subscriptions Microservice

Микросервис для управления пользователями и подписками для GepCalories. Обрабатывает регистрацию пользователей, управление подписками и платежи через YooKassa.

## 🏗 Архитектура

Независимый микросервис с собственной базой данных, взаимодействующий с другими сервисами через HTTP API.

### Основные директории:

```
gepvi_users/
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
├── clients/                # Внешние интеграции (YooKassa)
├── settings/               # Конфигурация
├── alembic/                # Миграции БД
└── tests/                  # Pytest тесты
```

## 🛠 Технологический стек

- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL + SQLModel + Alembic
- **Payments**: YooKassa
- **Testing**: Pytest + AsyncPG
- **Deploy**: Docker

## ✨ Основные возможности

1. **Управление пользователями**
   - Получение или создание пользователя
   - Отслеживание бесплатных AI запросов
   - История создания/обновления

2. **Управление подписками**
   - 5 бесплатных AI запросов при регистрации
   - Платные подписки через YooKassa
   - Автоматическая активация после оплаты
   - Проверка активности подписки

3. **Интеграция с YooKassa**
   - Создание платежей
   - Обработка webhooks
   - Автоматическая активация подписок

## 📦 Быстрый старт

### 1. Установите зависимости

```bash
cd gepvi_users
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройте окружение

Создайте `.env` файл:

```env
# Database
DB_URL=postgresql+asyncpg://user:password@localhost:5432/gepvi_users
TEST_DB_URL=postgresql+asyncpg://user:password@localhost:5432/gepvi_users_test

# API
API_KEY=your_secure_api_key_here
PORT=8008

# YooKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
YOOKASSA_PROVIDER_ID=yookassa

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

### Пользователи

```bash
# Получить или создать пользователя (можно передать либо user_id, либо telegram_user_id)
POST /users/get_or_create
Body: {
  "telegram_user_id": "123456789"
}
# ИЛИ
POST /users/get_or_create
Body: {
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
# ИЛИ оба (приоритет у user_id)
POST /users/get_or_create
Body: {
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "telegram_user_id": "123456789"
}

Response: {
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "telegram_user_id": "123456789",
  "subscription_expires_at": null,
  "has_active_subscription": false,
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

### Платежи

```bash
# Создать платеж
POST /payments/create
Body: {
  "user_id": "550e8400-e29b-41d4-a716-446655440000",  // UUID (required)
  "telegram_user_id": "123456789",                    // optional
  "package_type": "monthly",
  "return_url": "https://t.me/your_bot"
}

# Webhook от YooKassa
POST /webhook/yookassa
```

## 📊 База данных

### Схема: `gepvi_users`

### Таблица `users`

| Поле | Тип | Описание |
|------|-----|----------|
| `user_id` | UUID | Unique User ID (PK) |
| `telegram_user_id` | VARCHAR | Telegram User ID (optional, unique) |
| `subscription_expires_at` | TIMESTAMP | Дата окончания подписки (NULL = нет подписки) |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата обновления |

### Таблица `webhooks`

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | ID (PK) |
| `provider_name` | VARCHAR | Имя провайдера (yookassa) |
| `webhook_payload` | JSON | Полезная нагрузка |
| `response_code` | INTEGER | HTTP код ответа |
| `created_at` | TIMESTAMP | Дата создания |

## 💎 Пакеты подписок

- **1 месяц - 249₽** (~8.3₽/день)
- **3 месяца - 599₽** (скидка 20%, ~6.7₽/день)
- **1 год - 1499₽** (скидка 50%, ~4.1₽/день)

## 🧪 Тестирование

```bash
pytest tests/ -v
```

## 🔐 Аутентификация

Все endpoints требуют API ключ в заголовке `X-API-Key`, кроме:
- `GET /` — health check
- `GET /health` — health check
- `GET /docs` — Swagger UI
- `POST /webhook/yookassa` — YooKassa webhook

## 🔄 Интеграция с GepCalories

GepCalories основной сервис обращается к gepvi_users через HTTP API:

```python
# В GepCalories
async def get_or_create_user(telegram_user_id: str) -> dict:
    """Получить существующего пользователя или создать нового по telegram_user_id"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{USERS_SERVICE_URL}/users/get_or_create",
            json={"telegram_user_id": telegram_user_id},
            headers={"X-API-Key": API_KEY}
        )
        return response.json()

async def get_or_create_user_by_uuid(user_id: str) -> dict:
    """Получить существующего пользователя по UUID"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{USERS_SERVICE_URL}/users/get_or_create",
            json={"user_id": user_id},
            headers={"X-API-Key": API_KEY}
        )
        return response.json()

async def create_payment_for_user(user_id: str, telegram_user_id: str = None) -> dict:
    """Создать платеж для пользователя"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{USERS_SERVICE_URL}/payments/create",
            json={
                "user_id": user_id,  # UUID обязателен
                "telegram_user_id": telegram_user_id,  # опционально
                "package_type": "monthly",
                "return_url": "https://t.me/your_bot"
            },
            headers={"X-API-Key": API_KEY}
        )
        return response.json()
```

## 📝 Примечания

- **Основной идентификатор**: UUID (автогенерируемый)
- **telegram_user_id**: Опциональный, используется только для Telegram ботов
- **Обратная совместимость**: `POST /users/get_or_create` поддерживает оба идентификатора
- **Приоритет поиска**: сначала по `user_id` (UUID), затем по `telegram_user_id`
- Используется схема `gepvi_users` для изоляции данных
- Все async I/O операции
- Type hints везде
- Custom NNNN формат миграций (0001)
- Полная изоляция от основного сервиса
- Сервис не зависит от Telegram и может использоваться любыми бэкендами

## 📄 Лицензия

MIT
