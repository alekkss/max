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
        
        # Администраторы
        self.admin_user_ids: list[int] = self._parse_admin_ids(
            os.getenv("ADMIN_USER_IDS", "")
        )
        
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
        
        # Настройки массовых рассылок (НОВОЕ)
        self.notification_delay: float = float(os.getenv("NOTIFICATION_DELAY", "0.1"))
        self.notification_progress_interval: int = int(os.getenv("NOTIFICATION_PROGRESS_INTERVAL", "100"))
    
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
    
    def _parse_admin_ids(self, value: str) -> list[int]:
        """Парсинг списка ID администраторов из строки.
        
        Args:
            value: Строка с ID через запятую (например, "123,456,789")
            
        Returns:
            Список ID администраторов
        """
        if not value or not value.strip():
            return []
        
        try:
            # Разбиваем по запятой, убираем пробелы, конвертируем в int
            return [int(user_id.strip()) for user_id in value.split(",") if user_id.strip()]
        except ValueError as e:
            raise ValueError(
                f"Ошибка парсинга ADMIN_USER_IDS: '{value}'. "
                f"Ожидается формат: '123,456,789'. Ошибка: {e}"
            )


def get_settings() -> Settings:
    """Фабричная функция для получения экземпляра настроек.
    
    Позволяет легко переопределить источник конфигурации в тестах.
    """
    return Settings()