"""Точка входа приложения."""

import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.config.settings import get_settings
from src.database.connection import DatabaseConnection
from src.repositories.user_repository import SQLiteUserRepository
from src.repositories.message_repository import SQLiteMessageRepository
from src.clients.max_api_client import MaxApiClient
from src.services.user_service import UserService
from src.services.message_service import MessageService
from src.services.export_service import ExportService
from src.services.bot_service import BotService
from src.handlers.update_handler import UpdateHandler


def main() -> None:
    """Главная функция приложения.
    
    Инициализирует все компоненты и запускает бота.
    """
    # Загружаем конфигурацию
    settings = get_settings()
    
    # Инициализируем подключение к БД
    db_connection = DatabaseConnection(settings.database_path)
    db_connection.connect()
    db_connection.initialize_schema()
    
    print("✅ База данных инициализирована")
    
    try:
        # Создаем репозитории
        user_repository = SQLiteUserRepository(db_connection)
        message_repository = SQLiteMessageRepository(db_connection)
        
        # Создаем API-клиент
        api_client = MaxApiClient(settings)
        
        # Создаем сервисы с внедрением зависимостей
        user_service = UserService(
            user_repository=user_repository,
            api_client=api_client,
            settings=settings
        )
        
        message_service = MessageService(
            message_repository=message_repository,
            api_client=api_client,
            settings=settings
        )
        
        # Создаем сервис экспорта
        export_service = ExportService(
            user_repository=user_repository,
            message_repository=message_repository
        )
        
        # Создаем обработчик событий
        update_handler = UpdateHandler(
            user_service=user_service,
            message_service=message_service,
            export_service=export_service,
            settings=settings
        )
        
        # Создаем главный сервис бота
        bot_service = BotService(
            api_client=api_client,
            settings=settings
        )
        
        # Связываем обработчик с ботом
        bot_service.set_update_handler(update_handler)
        
        # Запускаем бота
        bot_service.start()
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        if settings.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
        
    finally:
        # Закрываем ресурсы
        print("\n🔌 Закрытие соединений...")
        db_connection.close()
        api_client.close()
        print("✅ Ресурсы освобождены")


if __name__ == "__main__":
    main()
