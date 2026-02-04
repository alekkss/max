"""Сервис для работы с админ-панелью бота."""

from typing import Optional

from src.clients.max_api_client import IMaxApiClient
from src.config.settings import Settings
from src.utils.admin_constants import AdminCallback, AdminMessage, AdminButton
from src.services.admin_state_manager import AdminStateManager, AdminState


class AdminService:
    """Сервис управления админ-панелью.
    
    Отвечает за:
    - Проверку прав доступа к админ-панели
    - Отправку меню с inline-кнопками
    - Обработку callback-событий от кнопок
    - Выполнение административных действий
    - Управление процессом создания уведомлений
    """

    def __init__(
        self,
        api_client: IMaxApiClient,
        settings: Settings
    ) -> None:
        """Инициализация сервиса.
        
        Args:
            api_client: Клиент для работы с Max.ru API
            settings: Конфигурация приложения
        """
        self._api_client = api_client
        self._settings = settings
        self._state_manager = AdminStateManager()

    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором.
        
        Args:
            user_id: ID пользователя для проверки
            
        Returns:
            True, если пользователь в списке администраторов, иначе False
        """
        return user_id in self._settings.admin_user_ids

    def send_access_denied(self, user_id: int) -> None:
        """Отправить сообщение об отказе в доступе.
        
        Args:
            user_id: ID пользователя
        """
        try:
            self._api_client.send_message_to_user(
                user_id=user_id,
                text=AdminMessage.ACCESS_DENIED
            )
            print(f"   ❌ Отказ в доступе для user_id={user_id}")
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки сообщения об отказе: {e}")

    def send_main_menu(self, user_id: int) -> None:
        """Отправить главное меню админ-панели.
        
        Args:
            user_id: ID администратора
        """
        try:
            # Формируем кнопки главного меню
            buttons = [
                [
                    (AdminButton.SEND_NOTIFICATION, AdminCallback.SEND_NOTIFICATION.value)
                ]
            ]
            
            self._api_client.send_message_with_keyboard(
                text=AdminMessage.MAIN_MENU_TEXT,
                buttons=buttons,
                user_id=user_id,
                format="markdown"
            )
            
            print(f"   ✅ Главное меню отправлено admin_id={user_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка отправки главного меню: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def handle_callback(self, user_id: int, callback_id: str, payload: str) -> None:
        """Обработать callback-событие от inline-кнопки.
        
        Args:
            user_id: ID пользователя, нажавшего кнопку
            callback_id: ID callback события (для ответа)
            payload: Данные callback (payload кнопки)
        """
        # Проверяем права доступа
        if not self.is_admin(user_id):
            try:
                self._api_client.answer_callback(
                    callback_id=callback_id,
                    notification=AdminMessage.ACCESS_DENIED
                )
            except Exception as e:
                if self._settings.debug:
                    print(f"   ⚠️ Ошибка отправки уведомления: {e}")
            return
        
        print(f"\n🔘 Callback от admin_id={user_id}: {payload}")
        
        # Маршрутизация по payload
        if payload == AdminCallback.SEND_NOTIFICATION.value:
            self._update_to_notification_menu(callback_id)
        
        elif payload == AdminCallback.BACK_TO_MAIN.value:
            self._update_to_main_menu(callback_id)
            # Сбрасываем состояние при возврате в главное меню
            self._state_manager.reset_state(user_id)
        
        elif payload == AdminCallback.NOTIFICATION_TEST.value:
            self._start_notification_creation(callback_id, user_id)
        
        elif payload == AdminCallback.NOTIFICATION_ALL.value:
            self._send_all_notification_stub(callback_id)
        
        elif payload == AdminCallback.CONFIRM_SEND.value:
            self._confirm_and_send_notification(callback_id, user_id)
        
        elif payload == AdminCallback.CANCEL_SEND.value:
            self._cancel_notification(callback_id, user_id)
        
        else:
            # Неизвестный callback
            if self._settings.debug:
                print(f"   ⚠️ Неизвестный callback: {payload}")

    def handle_notification_text(self, user_id: int, text: str) -> None:
        """Обработать текст уведомления от администратора.
        
        Вызывается из UpdateHandler когда админ отправляет текстовое сообщение
        и находится в состоянии WAITING_NOTIFICATION_TEXT.
        
        Args:
            user_id: ID администратора
            text: Текст уведомления
        """
        print(f"\n📝 Получен текст уведомления от admin_id={user_id}")
        
        # Сохраняем текст и переводим в состояние подтверждения
        self._state_manager.save_notification_text(user_id, text)
        
        # Отправляем предпросмотр с кнопками подтверждения
        self._send_notification_preview(user_id, text)

    def _update_to_main_menu(self, callback_id: str) -> None:
        """Обновить сообщение на главное меню.
        
        Args:
            callback_id: ID callback события
        """
        try:
            buttons = [
                [
                    (AdminButton.SEND_NOTIFICATION, AdminCallback.SEND_NOTIFICATION.value)
                ]
            ]
            
            self._api_client.answer_callback(
                callback_id=callback_id,
                text=AdminMessage.MAIN_MENU_TEXT,
                buttons=buttons,
                format="markdown"
            )
            
            print(f"   ✅ Главное меню обновлено")
            
        except Exception as e:
            print(f"   ❌ Ошибка обновления главного меню: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _update_to_notification_menu(self, callback_id: str) -> None:
        """Обновить сообщение на меню уведомлений.
        
        Args:
            callback_id: ID callback события
        """
        try:
            buttons = [
                [
                    (AdminButton.TEST, AdminCallback.NOTIFICATION_TEST.value),
                    (AdminButton.ALL_DATABASE, AdminCallback.NOTIFICATION_ALL.value)
                ],
                [
                    (AdminButton.BACK, AdminCallback.BACK_TO_MAIN.value)
                ]
            ]
            
            self._api_client.answer_callback(
                callback_id=callback_id,
                text=AdminMessage.NOTIFICATION_MENU_TEXT,
                buttons=buttons,
                format="markdown"
            )
            
            print(f"   ✅ Меню уведомлений обновлено")
            
        except Exception as e:
            print(f"   ❌ Ошибка обновления меню: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _start_notification_creation(self, callback_id: str, user_id: int) -> None:
        """Начать процесс создания уведомления.
        
        Args:
            callback_id: ID callback события
            user_id: ID администратора
        """
        try:
            # Переводим админа в состояние ожидания текста
            self._state_manager.set_state(user_id, AdminState.WAITING_NOTIFICATION_TEXT)
            
            # Обновляем текущее сообщение (убираем кнопки, меняем текст)
            self._api_client.answer_callback(
                callback_id=callback_id,
                text=AdminMessage.REQUEST_NOTIFICATION_TEXT,
                format="markdown"
            )
            
            print(f"   ✅ Админ переведён в режим ввода текста")
            
        except Exception as e:
            print(f"   ❌ Ошибка начала создания уведомления: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _send_notification_preview(self, user_id: int, text: str) -> None:
        """Отправить предпросмотр уведомления с кнопками подтверждения.
        
        Args:
            user_id: ID администратора
            text: Текст уведомления для предпросмотра
        """
        try:
            # Формируем текст предпросмотра
            preview_text = f"{AdminMessage.PREVIEW_HEADER}{text}{AdminMessage.PREVIEW_FOOTER}"
            
            # Формируем кнопки подтверждения
            buttons = [
                [
                    (AdminButton.CONFIRM_YES, AdminCallback.CONFIRM_SEND.value),
                    (AdminButton.CONFIRM_NO, AdminCallback.CANCEL_SEND.value)
                ]
            ]
            
            self._api_client.send_message_with_keyboard(
                text=preview_text,
                buttons=buttons,
                user_id=user_id,
                format="markdown"
            )
            
            print(f"   ✅ Предпросмотр отправлен admin_id={user_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка отправки предпросмотра: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _confirm_and_send_notification(self, callback_id: str, user_id: int) -> None:
        """Подтвердить и отправить уведомление всем администраторам.
        
        Args:
            callback_id: ID callback события
            user_id: ID администратора, подтвердившего отправку
        """
        try:
            # Получаем сохранённый текст уведомления
            notification_text = self._state_manager.get_notification_text(user_id)
            
            if not notification_text:
                print(f"   ⚠️ Текст уведомления не найден для admin_id={user_id}")
                self._api_client.answer_callback(
                    callback_id=callback_id,
                    notification="❌ Ошибка: текст уведомления не найден"
                )
                return
            
            # Счётчики для статистики
            sent_count = 0
            not_activated_ids = []  # Не активировали бота
            not_found_ids = []      # Несуществующие ID
            
            # Отправляем уведомление всем администраторам
            for admin_id in self._settings.admin_user_ids:
                try:
                    self._api_client.send_message_to_user(
                        user_id=admin_id,
                        text=notification_text,
                        format="markdown"
                    )
                    sent_count += 1
                    print(f"   ✉️ Отправлено admin_id={admin_id}")
                    
                except Exception as e:
                    error_message = str(e)
                    
                    # Классифицируем ошибку
                    if "dialog.not.found" in error_message or "chat.not.found" in error_message:
                        # Пользователь не активировал бота
                        not_activated_ids.append(admin_id)
                        print(f"   ⚠️ Бот не активирован admin_id={admin_id}")
                        
                    elif "user.not.found" in error_message:
                        # Несуществующий пользователь
                        not_found_ids.append(admin_id)
                        print(f"   ❌ Пользователь не найден admin_id={admin_id}")
                        
                    else:
                        # Неизвестная ошибка
                        print(f"   ⚠️ Неизвестная ошибка admin_id={admin_id}: {e}")
            
            # Формируем детальный отчёт
            report_lines = [f"✅ Доставлено: {sent_count}/{len(self._settings.admin_user_ids)}"]
            
            if not_activated_ids:
                report_lines.append(f"\n⚠️ Не активировали бота ({len(not_activated_ids)}): {', '.join(map(str, not_activated_ids))}")
            
            if not_found_ids:
                report_lines.append(f"\n❌ Не найдены ({len(not_found_ids)}): {', '.join(map(str, not_found_ids))}")
            
            notification_report = "\n".join(report_lines)
            
            # Отправляем подтверждение инициатору
            self._api_client.answer_callback(
                callback_id=callback_id,
                notification=notification_report
            )
            
            # Сбрасываем состояние
            self._state_manager.reset_state(user_id)
            
            print(f"   📊 Итого: {sent_count} успешно, {len(not_activated_ids)} не активировали, {len(not_found_ids)} не найдены")
            
        except Exception as e:
            print(f"   ❌ Критическая ошибка подтверждения отправки: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _cancel_notification(self, callback_id: str, user_id: int) -> None:
        """Отменить отправку уведомления и вернуться в меню.
        
        Args:
            callback_id: ID callback события
            user_id: ID администратора
        """
        try:
            # Сбрасываем состояние
            self._state_manager.reset_state(user_id)
            
            # Обновляем сообщение на меню уведомлений
            self._update_to_notification_menu(callback_id)
            
            print(f"   ❌ Отправка уведомления отменена admin_id={user_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка отмены уведомления: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _send_all_notification_stub(self, callback_id: str) -> None:
        """Заглушка для рассылки по всей базе.
        
        Args:
            callback_id: ID callback события
        """
        try:
            self._api_client.answer_callback(
                callback_id=callback_id,
                notification=AdminMessage.ALL_NOTIFICATION_STUB
            )
            print(f"   📢 Заглушка: рассылка по базе")
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки заглушки: {e}")

    def is_waiting_notification_text(self, user_id: int) -> bool:
        """Проверить, ожидает ли админ ввода текста уведомления.
        
        Args:
            user_id: ID администратора
            
        Returns:
            True, если админ в состоянии ожидания текста
        """
        return self._state_manager.is_waiting_notification_text(user_id)