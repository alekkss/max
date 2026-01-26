"""Обработчик событий от Max.ru API."""

from typing import Any, Optional

from src.services.user_service import UserService
from src.services.message_service import MessageService
from src.config.settings import Settings
from src.models.update import UpdateType, LinkType


class UpdateHandler:
    """Обработчик входящих событий от API.
    
    Отвечает за:
    - Парсинг и валидацию событий
    - Маршрутизацию по типам событий
    - Делегирование обработки сервисам
    """
    
    def __init__(
        self,
        user_service: UserService,
        message_service: MessageService,
        settings: Settings
    ) -> None:
        """Инициализация обработчика.
        
        Args:
            user_service: Сервис для работы с пользователями
            message_service: Сервис для работы с сообщениями
            settings: Конфигурация приложения
        """
        self._user_service = user_service
        self._message_service = message_service
        self._settings = settings
    
    def handle_update(self, update: dict[str, Any]) -> None:
        """Обработать входящее событие.
        
        Args:
            update: Словарь с данными события от API
        """
        update_type = update.get("update_type")
        
        if update_type == UpdateType.MESSAGE_CREATED.value:
            self._handle_message_created(update)
        elif update_type == UpdateType.BOT_STARTED.value:
            self._handle_bot_started(update)
        else:
            if self._settings.debug:
                print(f"⚠️  Неизвестный тип события: {update_type}")
    
    def _handle_message_created(self, update: dict[str, Any]) -> None:
        """Обработать событие создания сообщения."""
        message = update.get("message", {})
        body = message.get("body", {})
        text = body.get("text", "")
        
        sender = message.get("sender", {})
        user_id = sender.get("user_id")
        name = sender.get("name") or sender.get("first_name", "Пользователь")
        is_bot = sender.get("is_bot", False)
        
        recipient = message.get("recipient", {})
        chat_id = recipient.get("chat_id")
        recipient_user_id = recipient.get("user_id")
        
        link = message.get("link")
        
        # Определяем, откуда пришло сообщение
        is_from_support_chat = (chat_id == self._settings.support_chat_id)
        is_private_to_bot = (recipient_user_id is not None)
        
        # СЦЕНАРИЙ 1: Ответ оператора через Reply в чате поддержки
        if is_from_support_chat and not is_bot and link:
            self._handle_operator_reply(link, name, text)
            return
        
        # Игнорируем другие сообщения из чата поддержки
        if is_from_support_chat:
            return
        
        # СЦЕНАРИЙ 2: Команда /start от клиента
        if is_private_to_bot and text.strip().lower() in ["/start", "/hello"]:
            self._handle_start_command(user_id, name)
            return
        
        # СЦЕНАРИЙ 3: Обычное сообщение от клиента
        if is_private_to_bot and not is_bot:
            self._handle_user_message(user_id, name, text)
            return
    
    def _handle_bot_started(self, update: dict[str, Any]) -> None:
        """Обработать событие запуска бота пользователем."""
        user = update.get("user", {})
        user_id = user.get("user_id")
        name = user.get("name") or user.get("first_name", "Пользователь")
        
        print(f"\n🎉 Новый пользователь: {name}")
        
        # Делегируем обработку сервису
        self._user_service.handle_bot_started(user_id, name)
    
    def _handle_start_command(self, user_id: int, name: str) -> None:
        """Обработать команду /start."""
        print(f"\n📨 /start от {name} (ID: {user_id})")
        
        # Делегируем обработку сервису
        self._user_service.handle_start_command(user_id, name)
    
    def _handle_user_message(self, user_id: int, name: str, text: str) -> None:
        """Обработать сообщение от клиента."""
        text_preview = text[:50] + "..." if len(text) > 50 else text
        print(f"\n📤 {name}: {text_preview}")
        
        # Регистрируем/обновляем пользователя
        self._user_service.register_or_update_user(user_id, name)
        
        # Сохраняем сообщение в историю
        self._message_service.save_user_message(user_id, text)
        
        # Пересылаем в чат поддержки
        message_id = self._message_service.forward_to_support(user_id, name, text)
        
        if message_id:
            print(f"  ✅ Переслано в поддержку")
        else:
            print(f"  ❌ Ошибка пересылки")
    
    def _handle_operator_reply(
        self,
        link: Optional[dict[str, Any]],
        operator_name: str,
        text: str
    ) -> None:
        """Обработать ответ оператора через Reply."""
        if link is None:
            return
        
        link_type = link.get("type")
        if link_type != LinkType.REPLY.value:
            return
        
        # Получаем ID сообщения, на которое ответили
        replied_message = link.get("message", {})
        replied_message_id = replied_message.get("mid")
        
        if not replied_message_id:
            return
        
        # Находим маппинг к какому пользователю это сообщение
        mapping = self._message_service.get_mapping_by_message_id(replied_message_id)
        
        if mapping is None:
            if self._settings.debug:
                print(f"⚠️  Маппинг не найден для message_id: {replied_message_id}")
            return
        
        target_user_id = mapping.user_id
        target_user_name = mapping.user_name
        
        text_preview = text[:80] + "..." if len(text) > 80 else text
        print(f"\n💬 Ответ от {operator_name} → {target_user_name}")
        print(f"   {text_preview}")
        
        # Сохраняем сообщение оператора в историю
        self._message_service.save_operator_message(
            target_user_id,
            text,
            operator_name
        )
        
        # Отправляем ответ пользователю
        success = self._message_service.send_operator_reply(
            target_user_id,
            target_user_name,
            operator_name,
            text
        )
        
        if success:
            print(f"   ✅ Отправлено!")
        else:
            print(f"   ❌ Ошибка отправки")
