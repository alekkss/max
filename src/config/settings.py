"""Конфигурация приложения."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота LaVita.
    
    Все параметры загружаются из переменных окружения или .env файла.
    Pydantic автоматически валидирует типы и обязательные поля./а
    """
    
    # API конфигурация
    api_token: str
    base_url: str = "https://platform-api.max.ru"
    
    # Идентификаторы
    support_chat_id: int
    bot_id: int
    
    # База данных
    database_path: str = "lavita_bot.db"
    
    # Настройки long polling
    polling_timeout: int = 30
    polling_request_timeout: int = 35
    
    # Режим отладки
    debug: bool = False
    
    # Задержки между запросами (секунды)
    message_delay: float = 0.3
    error_retry_delay: int = 5
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def api_headers(self) -> dict[str, str]:
        """Заголовки для HTTP-запросов к API."""
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }


def get_settings() -> Settings:
    """Фабричная функция для получения экземпляра настроек.
    
    Позволяет легко переопределить источник конфигурации в тестах.
    """
    return Settings()
