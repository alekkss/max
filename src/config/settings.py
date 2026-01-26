"""Конфигурация приложения."""

import os
from typing import Optional
from dotenv import load_dotenv


class Settings:
    """Настройки бота LaVita.
    
    Все параметры загружаются из переменных окружения или .env файла.
    """
    
    def __init__(self) -> None:
        """Инициализация настроек из переменных окружения."""
        # Загружаем .env файл
        load_dotenv()
        
        # API конфигурация
        self.api_token: str = self._get_required_env("API_TOKEN")
        self.base_url: str = os.getenv("BASE_URL", "https://platform-api.max.ru")
        
        # Идентификаторы
        self.support_chat_id: int = int(self._get_required_env("SUPPORT_CHAT_ID"))
        self.bot_id: int = int(self._get_required_env("BOT_ID"))
        
        # База данных
        self.database_path: str = os.getenv("DATABASE_PATH", "lavita_bot.db")
        
        # Настройки long polling
        self.polling_timeout: int = int(os.getenv("POLLING_TIMEOUT", "30"))
        self.polling_request_timeout: int = int(os.getenv("POLLING_REQUEST_TIMEOUT", "35"))
        
        # Режим отладки
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        # Задержки между запросами (секунды)
        self.message_delay: float = float(os.getenv("MESSAGE_DELAY", "0.3"))
        self.error_retry_delay: int = int(os.getenv("ERROR_RETRY_DELAY", "5"))
    
    @property
    def api_headers(self) -> dict[str, str]:
        """Заголовки для HTTP-запросов к API."""
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
    
    def _get_required_env(self, key: str) -> str:
        """Получить обязательную переменную окружения.
        
        Args:
            key: Название переменной
            
        Returns:
            Значение переменной
            
        Raises:
            ValueError: Если переменная не найдена
        """
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Обязательная переменная окружения '{key}' не установлена. Проверьте .env файл.")
        return value


def get_settings() -> Settings:
    """Фабричная функция для получения экземпляра настроек.
    
    Позволяет легко переопределить источник конфигурации в тестах.
    """
    return Settings()
