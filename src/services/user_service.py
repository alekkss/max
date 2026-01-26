"""Сервис для работы с пользователями."""

from typing import Optional

from src.repositories.user_repository import IUserRepository
from src.clients.max_api_client import IMaxApiClient
from src.models.user import User, UserCreate, UserUpdate
from src.config.settings import Settings


class UserService:
    """Сервис для бизнес-логики работы с пользователями.
    
    Отвечает за:
    - Регистрацию новых пользователей
    - Обновление данных существующих пользователей
    - Отправку приветственных сообщений
    """
    
    def __init__(
        self,
        user_repository: IUserRepository,
        api_client: IMaxApiClient,
        settings: Settings
    ) -> None:
        """Инициализация сервиса.
        
        Args:
            user_repository: Репозиторий для работы с пользователями
            api_client: API-клиент для отправки сообщений
            settings: Конфигурация приложения
        """
        self._user_repository = user_repository
        self._api_client = api_client
        self._settings = settings
    
    def register_or_update_user(self, user_id: int, name: str) -> User:
        """Зарегистрировать нового пользователя или обновить существующего.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
            
        Returns:
            Сохраненный объект пользователя
        """
        user_data = UserCreate(user_id=user_id, name=name)
        return self._user_repository.save(user_data)
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            User если найден, None если не существует
        """
        return self._user_repository.get_by_id(user_id)
    
    def send_welcome_message(self, user_id: int, name: str) -> None:
        """Отправить приветственное сообщение новому пользователю.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя для персонализации
        """
        welcome_text = (
            f"👋 Привет, {name}!\n\n"
            "Добро пожаловать! Я бот LaVita yarn.\n\n"
            "Пришлите ваш номер телефона для связи"
        )
        
        self._api_client.send_message_to_user(user_id, welcome_text)
        
        # Отправляем второе сообщение с просьбой задать вопрос
        prompt_text = "Напишите ваш вопрос."
        self._api_client.send_message_to_user(user_id, prompt_text)
    
    def handle_start_command(self, user_id: int, name: str) -> None:
        """Обработать команду /start от пользователя.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
        """
        # Регистрируем или обновляем пользователя
        self.register_or_update_user(user_id, name)
        
        # Отправляем приветствие
        self.send_welcome_message(user_id, name)
    
    def handle_bot_started(self, user_id: int, name: str) -> None:
        """Обработать событие bot_started (пользователь запустил бота).
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
        """
        # Регистрируем нового пользователя
        self.register_or_update_user(user_id, name)
        
        # Отправляем приветствие
        self.send_welcome_message(user_id, name)
