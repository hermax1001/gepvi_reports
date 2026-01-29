"""Конфигурация приложения из env переменных"""
from pathlib import Path

from environs import Env


# Load environment variables
env = Env()

STAND = env.str('STAND', default='local')
BASE_PATH = Path.cwd().absolute()

if STAND == 'local':
    env.read_env(path=str(BASE_PATH / '.env'))

class Settings:
    def __init__(self):
        self.PORT: int = env.int('PORT', default=8008)
        # Database
        self.DB_URL: str = env.str("DB_URL", "")
        self.TEST_DB_URL: str = env.str("TEST_DB_URL", "")

        # App
        self.DEBUG: bool = env.bool("DEBUG", True)

        # API Authentication
        self.API_KEY: str = env.str("API_KEY", "BigbigbigtestapikeybigBigbig!!!asjkdhfl")

        # SENTRY
        self.SENTRY_DSN: str = env.str("SENTRY_DSN", "")

        # Notification retry settings
        self.NOTIFICATION_RETRY_TIMEOUT_MINUTES: int = env.int("NOTIFICATION_RETRY_TIMEOUT_MINUTES", default=5)
        self.NOTIFICATION_MAX_RETRY_COUNT: int = env.int("NOTIFICATION_MAX_RETRY_COUNT", default=2)

AppConfig = Settings()
