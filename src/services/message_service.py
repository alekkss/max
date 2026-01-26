"""Сервис для работы с сообщениями."""

from typing import Optional, List

from src.repositories.message_repository import IMessageRepository
from src.clients.max_api_client import IMaxApiClient, MaxApiHttpError
from src.models.message import (
    Message,
    MessageCreate,
    MessageMapping,
    MessageMappingCreate,
    MessageDirection
)
from src.config.settings import Settings


class MessageService:
    """Сервис для бизнес-логики работы с сообщениями.
    
    Отвечает за:
    - Сохранение сообщений в историю
    - Пересылку сообщений клиентов в чат поддержки
    - Обработку ответов операторов
    - Управление маппингом сообщений
    """
    
    def __init__(
        self,
        message_repository: IMessageRepository,
        api_client: IMaxApiClient,
        settings: Settings
    ) -> None:
        """Инициализация сервиса.
        
        Args:
            message_repository: Репозиторий для работы с сообщениями
            api_client: API-клиент для отправки сообщений
            settings: Конфигурация приложения
        """
        self._message_repository = message_repository
        self._api_client = api_client
        self._settings = settings
    
    def save_user_message(self, user_id: int, text: str) -> Message:
        """Сохранить сообщение от пользователя в историю.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
            
        Returns:
            Сохраненное сообщение
        """
        message_data = MessageCreate(
            user_id=user_id,
            text=text,
            direction=MessageDirection.FROM_USER
        )
        return self._message_repository.save_message(message_data)
    
    def save_operator_message(
        self,
        user_id: int,
        text: str,
        operator_name: str
    ) -> Message:
        """Сохранить сообщение от оператора в историю.
        
        Args:
            user_id: ID пользователя-получателя
            text: Текст сообщения
            operator_name: Имя оператора
            
        Returns:
            Сохраненное сообщение
        """
        message_data = MessageCreate(
            user_id=user_id,
            text=text,
            direction=MessageDirection.TO_USER,
            operator_name=operator_name
        )
        return self._message_repository.save_message(message_data)
    
    def get_user_history(self, user_id: int, limit: int = 50) -> List[Message]:
        """Получить историю сообщений пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений
        """
        return self._message_repository.get_user_messages(user_id, limit)
    
    def forward_to_support(
        self,
        user_id: int,
        user_name: str,
        text: str
    ) -> Optional[str]:
        """Переслать сообщение клиента в чат поддержки.
        
        Args:
            user_id: ID пользователя
            user_name: Имя пользователя
            text: Текст сообщения
        
        Returns:
            Message ID отправленного сообщения в чате или None при ошибке
        """
        # Подсчитываем количество ответов оператора для этого пользователя
        replies_count = self._message_repository.count_operator_replies(user_id)
        
        forward_text = (
            f"📨 {user_name} (ID: {user_id})\n"
            f"👤 [{user_name}](max://user/{user_id})\n"  # ✅ ИЗМЕНЕНА ТОЛЬКО ЭТА СТРОКА
            f"_Вопрос пользователя:_\n\n"
            f"**{text}**\n\n"
            f"💬 Ответов предоставлено: {replies_count}"
        )
        
        try:
            response = self._api_client.send_message_to_chat(
                self._settings.support_chat_id,
                forward_text,
                format="markdown"  # ✅ Добавляем формат markdown
            )
            
            # Извлекаем message_id из ответа
            message = response.get("message", {})
            body = message.get("body", {})
            message_id = body.get("mid")
            
            if message_id:
                # Сохраняем маппинг
                mapping_data = MessageMappingCreate(
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name
                )
                self._message_repository.save_mapping(mapping_data)
            
            return message_id
        
        except MaxApiHttpError as e:
            # Логируем ошибку, но не прерываем работу бота
            print(f"❌ Ошибка пересылки в чат поддержки: {e}")
            return None
    
    def send_operator_reply(
        self,
        user_id: int,
        user_name: str,
        operator_name: str,
        text: str
    ) -> bool:
        """Отправить ответ оператора пользователю.
        
        Args:
            user_id: ID пользователя-получателя
            user_name: Имя пользователя
            operator_name: Имя оператора
            text: Текст ответа
            
        Returns:
            True если успешно отправлено, False при ошибке
        """
        full_reply = f"💬 {text}"
        
        try:
            self._api_client.send_message_to_user(user_id, full_reply)
            
            # # Уведомляем чат поддержки об успешной отправке
            # notification = f"✅ {operator_name} ответил пользователю {user_name}"
            # self._api_client.send_message_to_chat(
            #     self._settings.support_chat_id,
            #     notification
            # )
            
            return True
            
        except MaxApiHttpError as e:
            print(f"❌ Ошибка отправки ответа пользователю {user_id}: {e}")
            return False
    
    def get_mapping_by_message_id(self, message_id: str) -> Optional[MessageMapping]:
        """Получить маппинг по message_id из чата поддержки.
        
        Args:
            message_id: ID сообщения в чате
            
        Returns:
            MessageMapping если найден, None если не существует
        """
        return self._message_repository.get_mapping_by_message_id(message_id)
