"""Обработчик событий от Max.ru API."""

from typing import Any, Optional

from src.services.user_service import UserService
from src.services.message_service import MessageService
from src.services.export_service import ExportService
from src.services.admin_service import AdminService
from src.config.settings import Settings
from src.models.update import UpdateType, LinkType


# Типы вложений, которые являются медиаконтентом (фото, видео, файлы).
# Используется для фильтрации служебных вложений (inline_keyboard и т.д.)
_MEDIA_ATTACHMENT_TYPES: set[str] = {"image", "video", "audio", "file"}


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
        admin_service: AdminService,
        settings: Settings
    ) -> None:
        """Инициализация обработчика.
        
        Args:
            user_service: Сервис для работы с пользователями
            message_service: Сервис для работы с сообщениями
            export_service: Сервис для экспорта данных
            admin_service: Сервис для работы с админ-панелью
            settings: Конфигурация приложения
        """
        self._user_service = user_service
        self._message_service = message_service
        self._export_service = export_service
        self._admin_service = admin_service
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
        elif update_type == "message_callback":
            self._handle_message_callback(update)
        else:
            if self._settings.debug:
                print(f"⚠️ Неизвестный тип события: {update_type}")

    def _handle_message_created(self, update: dict[str, Any]) -> None:
        """Обработать событие создания сообщения."""

        message = update.get("message", {})
        body = message.get("body", {})
        text = body.get("text", "")
        message_id = body.get("mid")  # Извлекаем message_id для reply
        
        # Извлекаем вложения из body сообщения (фото, видео, файлы и т.д.)
        raw_attachments = body.get("attachments", [])
        
        # Фильтруем только медиа-вложения, исключая служебные (inline_keyboard и т.д.)
        media_attachments = self._extract_media_attachments(raw_attachments)
        
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
        
        # СЦЕНАРИЙ 2.5: Сообщение от админа в режиме создания уведомления
        if is_private_to_bot and not is_bot:
            # Проверяем, является ли пользователь админом
            if self._admin_service.is_admin(user_id):
                # Проверяем, ожидает ли админ ввода текста уведомления
                if self._admin_service.is_waiting_notification_text(user_id):
                    print(f"\n📝 Текст уведомления от admin_id={user_id}")
                    # Передаём текст И медиа-вложения (фото, видео и т.д.)
                    self._admin_service.handle_notification_text(
                        user_id,
                        text,
                        attachments=media_attachments if media_attachments else None
                    )
                    return
        
        # СЦЕНАРИЙ 3: Команда /admin от клиента
        if is_private_to_bot and text.strip().lower() == "/admin":
            self._handle_admin_command(user_id, name)
            return
        
        # СЦЕНАРИЙ 4: Команда /start или кнопка "Начать" от клиента
        if is_private_to_bot and text.strip().lower() in ["/start", "/hello", "начать", "start"]:
            self._handle_start_command(user_id, name)
            return
        
        # СЦЕНАРИЙ 5: Игнорируем автоматические приветственные сообщения
        if is_private_to_bot and text.startswith("Добро пожаловать в LaVita yarn!"):
            print(f"\n⚠️ Автоматическое приветствие от {name} проигнорировано")
            return
        
        # СЦЕНАРИЙ 6: Обычное сообщение от клиента
        if is_private_to_bot and not is_bot:
            self._handle_user_message(user_id, name, text, message_id)
            return

    def _extract_media_attachments(
        self,
        raw_attachments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Извлечь медиа-вложения из списка вложений сообщения.
        
        Фильтрует служебные вложения (inline_keyboard, share и т.д.),
        оставляя только медиаконтент (image, video, audio, file).
        Для каждого вложения формирует объект в формате, пригодном
        для отправки через POST /messages (type + payload с token).
        
        Args:
            raw_attachments: Сырой список вложений из body сообщения API
            
        Returns:
            Список медиа-вложений в формате для отправки через API.
            Пустой список, если медиа-вложений нет.
        """
        media_attachments: list[dict[str, Any]] = []
        
        for attachment in raw_attachments:
            attachment_type = attachment.get("type", "")
            
            # Пропускаем не-медиа вложения (inline_keyboard, share и т.д.)
            if attachment_type not in _MEDIA_ATTACHMENT_TYPES:
                continue
            
            payload = attachment.get("payload", {})
            
            # Для отправки через API нужен token в payload.
            # При получении сообщения API возвращает payload с token и другими полями
            # (url, width, height и т.д.). Для отправки достаточно token.
            token = payload.get("token")
            
            if token:
                # Формируем вложение в формате для POST /messages
                media_attachments.append({
                    "type": attachment_type,
                    "payload": {
                        "token": token
                    }
                })
            elif self._settings.debug:
                print(f"   ⚠️ Вложение типа '{attachment_type}' без token, пропущено")
        
        return media_attachments

    def _handle_bot_started(self, update: dict[str, Any]) -> None:
        """Обработать событие запуска бота пользователем."""
        user = update.get("user", {})
        user_id = user.get("user_id")
        name = user.get("name") or user.get("first_name", "Пользователь")
        
        print(f"\n🎉 Новый пользователь: {name}")
        
        # Делегируем обработку сервису
        self._user_service.handle_bot_started(user_id, name)

    def _handle_message_callback(self, update: dict[str, Any]) -> None:
        """Обработать событие нажатия на inline-кнопку.
        
        Args:
            update: Событие с типом message_callback
        """
        callback = update.get("callback", {})
        callback_id = callback.get("callback_id")
        payload = callback.get("payload")
        
        # Получаем информацию о пользователе
        user = callback.get("user", {})
        user_id = user.get("user_id")
        
        if not callback_id or not payload or not user_id:
            if self._settings.debug:
                print(f"⚠️ Некорректное callback событие: {update}")
            return
        
        # Делегируем обработку админ-сервису
        self._admin_service.handle_callback(user_id, callback_id, payload)

    def _handle_admin_command(self, user_id: int, name: str) -> None:
        """Обработать команду /admin.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
        """
        print(f"\n🔧 /admin от {name} (ID: {user_id})")
        
        # Проверяем права доступа
        if not self._admin_service.is_admin(user_id):
            print(f"   ❌ Доступ запрещен")
            self._admin_service.send_access_denied(user_id)
            return
        
        # Отправляем главное меню админ-панели
        print(f"   ✅ Доступ разрешен")
        self._admin_service.send_main_menu(user_id)

    def _handle_start_command(self, user_id: int, name: str) -> None:
        """Обработать команду /start."""
        print(f"\n📨 /start от {name} (ID: {user_id})")
        
        # Делегируем обработку сервису
        self._user_service.handle_start_command(user_id, name)

    def _handle_user_message(
        self,
        user_id: int,
        name: str,
        text: str,
        message_id: Optional[str]
    ) -> None:
        """Обработать сообщение от клиента.
        
        Args:
            user_id: ID пользователя
            name: Имя пользователя
            text: Текст сообщения
            message_id: ID сообщения из Max.ru API (для reply)
        """
        text_preview = text[:50] + "..." if len(text) > 50 else text
        print(f"\n📤 {name}: {text_preview}")
        
        # Регистрируем/обновляем пользователя
        self._user_service.register_or_update_user(user_id, name)
        
        # ПРОВЕРКА: Есть ли у пользователя номер телефона?
        if not self._user_service.has_phone_number(user_id):
            # Пользователь ещё не ввёл номер телефона
            
            # Пытаемся валидировать текущее сообщение как номер
            phone_number = self._user_service.validate_phone_number(text)
            
            if phone_number:
                # Валидный номер - сохраняем
                self._user_service.save_phone_number(user_id, phone_number)
                self._user_service.confirm_phone_saved(user_id, phone_number)
                print(f"  📞 Номер телефона сохранен: {phone_number}")
            else:
                # Не валидный номер - напоминаем ввести
                self._user_service.request_phone_number(user_id)
                print(f"  ⚠️ Пользователь не указал номер телефона")
            
            # НЕ пересылаем в чат поддержки
            return
        
        # Пользователь УЖЕ ввёл номер - работаем как обычно
        
        # Сохраняем сообщение в историю с message_id
        self._message_service.save_user_message(user_id, text, message_id)
        
        # Пересылаем в чат поддержки
        support_message_id = self._message_service.forward_to_support(user_id, name, text)
        
        if support_message_id:
            print(f"  ✅ Переслано в поддержку")
            
            # Отправляем подтверждение получения сообщения пользователю
            self._message_service.send_message_received_confirmation(user_id, name)
            print(f"  📬 Подтверждение отправлено")
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
                f"📨 [{mapping.user_name}](max://user/{mapping.user_id}) (ID: #{mapping.user_id})\n"
                f"_Вопрос пользователя:_\n\n"
                f"{mapping.question_text}\n\n"
                f"💬 Ответов: ✅ {replies_count}"
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
