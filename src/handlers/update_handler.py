"""Обработчик событий от Max.ru API."""

from typing import Any, Optional

from src.services.user_service import UserService
from src.services.message_service import MessageService
from src.services.export_service import ExportService
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
        export_service: ExportService,
        settings: Settings
    ) -> None:
        """Инициализация обработчика.
        
        Args:
            user_service: Сервис для работы с пользователями
            message_service: Сервис для работы с сообщениями
            export_service: Сервис для экспорта данных
            settings: Конфигурация приложения
        """
        self._user_service = user_service
        self._message_service = message_service
        self._export_service = export_service
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
                print(f"⚠️ Неизвестный тип события: {update_type}")

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
        
        # СЦЕНАРИЙ 1: Команда /export из чата поддержки
        if is_from_support_chat and not is_bot and text.strip().lower() == "/export":
            self._handle_export_command(name)
            return
        
        # СЦЕНАРИЙ 2: Ответ оператора через Reply в чате поддержки
        if is_from_support_chat and not is_bot and link:
            self._handle_operator_reply(link, name, text)
            return
        
        # Игнорируем другие сообщения из чата поддержки
        if is_from_support_chat:
            return
        
        # СЦЕНАРИЙ 3: Команда /start от клиента
        if is_private_to_bot and text.strip().lower() in ["/start", "/hello"]:
            self._handle_start_command(user_id, name)
            return
        
        # СЦЕНАРИЙ 4: Обычное сообщение от клиента
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
                print(f"⚠️ Маппинг не найден для message_id: {replied_message_id}")
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
            
            # Обновляем счётчик ответов в исходном сообщении
            self._update_reply_counter(replied_message_id, mapping)
        else:
            print(f"   ❌ Ошибка отправки")

    def _update_reply_counter(
        self,
        message_id: str,
        mapping: 'MessageMapping'
    ) -> None:
        """Обновить счётчик ответов в сообщении чата поддержки.
        
        Args:
            message_id: ID сообщения в чате для редактирования
            mapping: Маппинг с данными о вопросе пользователя
        """
        try:
            # Получаем актуальный счётчик ответов по текущему вопросу
            replies_count = self._message_service.count_replies_for_question(mapping.user_id)
            
            # Формируем обновлённый текст с ОРИГИНАЛЬНЫМ текстом вопроса
            updated_text = (
                f"📨 [{mapping.user_name}](max://user/{mapping.user_id}) (ID: {mapping.user_id})\n"
                f"_Вопрос пользователя:_\n\n"
                f"**{mapping.question_text}**\n\n"  # ← ИЗМЕНЕНО: используем сохранённый текст
                f"💬 Ответов: {replies_count}"
            )
            
            # Редактируем сообщение в чате
            api_client = self._user_service._api_client
            api_client.edit_message(
                chat_id=self._settings.support_chat_id,
                message_id=message_id,
                new_text=updated_text,
                format="markdown"
            )
            
            print(f"   🔄 Счётчик обновлён: {replies_count}")
            
        except Exception as e:
            # Не прерываем работу бота, если редактирование не удалось
            if self._settings.debug:
                print(f"   ⚠️ Ошибка обновления счётчика: {e}")

    def _handle_export_command(self, operator_name: str) -> None:
        """Обработать команду /export из чата поддержки."""
        print(f"\n📊 Команда /export от {operator_name}")
        
        try:
            # Генерируем Excel файл
            from datetime import datetime
            import time
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"users_export_{timestamp}.xlsx"
            
            file_path = self._export_service.export_all_users_to_excel(filename)
            print(f"   ✅ Excel файл создан: {file_path}")
            
            # Загружаем файл на сервер Max.ru
            print(f"   ⬆️ Загрузка файла на сервер...")
            api_client = self._user_service._api_client
            file_token = api_client.upload_file(file_path)
            print(f"   ✅ Файл загружен, token: {file_token[:20]}...")
            
            # ВАЖНО: Ждем пока сервер обработает файл
            print(f"   ⏳ Ожидание обработки файла на сервере (3 сек)...")
            time.sleep(3)
            
            # Отправляем файл в чат с описанием
            notification = (
                f"📊 Экспорт данных выполнен\n"
                f"👤 Инициатор: {operator_name}\n"
                f"📁 Файл: {filename}\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            
            api_client.send_file_to_chat(
                self._settings.support_chat_id,
                file_token,
                notification,
                filename
            )
            
            print(f"   ✅ Файл отправлен в чат поддержки!")
            
        except Exception as e:
            error_message = f"❌ Ошибка при экспорте данных: {e}"
            print(f"   {error_message}")
            
            # Отправляем сообщение об ошибке в чат
            try:
                self._user_service._api_client.send_message_to_chat(
                    self._settings.support_chat_id,
                    error_message
                )
            except Exception:
                pass  # Игнорируем ошибки при отправке сообщения об ошибке
