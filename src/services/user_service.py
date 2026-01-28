"""Сервис для работы с пользователями."""

from typing import Optional
import re

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
    - Валидацию и сохранение номеров телефонов
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
    
    def has_phone_number(self, user_id: int) -> bool:
        """Проверить, есть ли у пользователя номер телефона.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если номер есть, False если нет
        """
        user = self._user_repository.get_by_id(user_id)
        return user is not None and user.phone_number is not None and user.phone_number.strip() != ""
    
    def validate_phone_number(self, text: str) -> Optional[str]:
        """Валидировать номер телефона.
        
        Номер должен начинаться с + и содержать только цифры после него.
        
        Args:
            text: Текст для проверки
            
        Returns:
            Отформатированный номер телефона или None если не валиден
        """
        # Убираем пробелы
        text = text.strip()
        
        # Проверяем, что начинается с + и содержит хотя бы одну цифру
        if not text.startswith("+"):
            return None
        
        # Убираем все символы кроме + и цифр
        cleaned = re.sub(r'[^\d+]', '', text)
        
        # Проверяем что есть хотя бы 10 цифр после +
        if len(cleaned) < 11:  # + и минимум 10 цифр
            return None
        
        return cleaned
    
    def save_phone_number(self, user_id: int, phone_number: str) -> User:
        """Сохранить номер телефона пользователя.
        
        Args:
            user_id: ID пользователя
            phone_number: Номер телефона
            
        Returns:
            Обновленный пользователь
        """
        return self._user_repository.update_phone_number(user_id, phone_number)
    
    def request_phone_number(self, user_id: int) -> None:
        """Напомнить пользователю ввести номер телефона.
        
        Args:
            user_id: ID пользователя
        """
        message = (
            "📞 Пожалуйста, сначала укажите ваш номер телефона для связи.\n\n"
            "Формат: +79991234567"
        )
        self._api_client.send_message_to_user(user_id, message)
    
    def confirm_phone_saved(self, user_id: int, phone_number: str) -> None:
        """Подтвердить сохранение номера телефона.
        
        Args:
            user_id: ID пользователя
            phone_number: Сохраненный номер
        """
        message = (
            f"✅ Спасибо! Ваш номер телефона {phone_number} сохранен.\n\n"
            "Теперь вы можете задать ваш вопрос."
        )
        self._api_client.send_message_to_user(user_id, message)
    
    def send_welcome_message(self, user_id: int, name: str) -> None:
        """Отправить приветственное сообщение новому пользователю.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя для персонализации
        """
        welcome_text = (
            f"👋 Привет, {name}!\n\n"
            "Добро пожаловать! Я бот LaVita yarn.\n\n"
            "📞 Пожалуйста, укажите ваш номер телефона для связи.\n\n"
            "Формат: +79991234567\n\n"
            "Оставляя свои данные, вы соглашаетесь с [политикой обработки персональных данных](https://lavitayarn.ru/include/licenses_detail.php)"
        )
        
        self._api_client.send_message_to_user(user_id, welcome_text, format="markdown")

    def send_welcome_message_with_phone(self, user_id: int, name: str) -> None:
        """Отправить приветственное сообщение пользователю с уже сохраненным номером.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя для персонализации
        """
        welcome_text = (
            f"👋 Привет, {name}!\n\n"
            "Рад снова видеть вас! Я бот LaVita yarn.\n\n"
            "Напишите ваш вопрос, и первый освободившийся оператор ответит в ближайшее время."
        )
        
        self._api_client.send_message_to_user(user_id, welcome_text)
    
    def handle_start_command(self, user_id: int, name: str) -> None:
        """Обработать команду /start от пользователя.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
        """
        # Регистрируем или обновляем пользователя
        self.register_or_update_user(user_id, name)
        
        # Проверяем наличие номера телефона
        if self.has_phone_number(user_id):
            # У пользователя уже есть номер - приветствие без запроса номера
            self.send_welcome_message_with_phone(user_id, name)
        else:
            # Номера нет - просим ввести
            self.send_welcome_message(user_id, name)
    
    def handle_bot_started(self, user_id: int, name: str) -> None:
        """Обработать событие bot_started (пользователь запустил бота).
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
        """
        # Регистрируем нового пользователя
        self.register_or_update_user(user_id, name)
        
        # Проверяем наличие номера телефона
        if self.has_phone_number(user_id):
            # У пользователя уже есть номер - приветствие без запроса номера
            self.send_welcome_message_with_phone(user_id, name)
        else:
            # Номера нет - просим ввести
            self.send_welcome_message(user_id, name)
