"""Сервис для работы с админ-панелью бота."""

from typing import Optional
import threading
import time
from datetime import datetime

from src.clients.max_api_client import IMaxApiClient
from src.config.settings import Settings
from src.repositories.user_repository import IUserRepository
from src.utils.admin_constants import AdminCallback, AdminMessage, AdminButton
from src.services.admin_state_manager import AdminStateManager, AdminState, NotificationTarget


class AdminService:
    """Сервис управления админ-панелью.
    
    Отвечает за:
    - Проверку прав доступа к админ-панели
    - Отправку меню с inline-кнопками
    - Обработку callback-событий от кнопок
    - Выполнение административных действий
    - Управление процессом создания уведомлений
    - Рассылку уведомлений администраторам и всем пользователям
    """

    def __init__(
        self,
        api_client: IMaxApiClient,
        user_repository: IUserRepository,
        settings: Settings
    ) -> None:
        """Инициализация сервиса.
        
        Args:
            api_client: Клиент для работы с Max.ru API
            user_repository: Репозиторий пользователей
            settings: Конфигурация приложения
        """
        self._api_client = api_client
        self._user_repository = user_repository
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
            self._start_notification_creation(callback_id, user_id, NotificationTarget.ADMINS)
        
        elif payload == AdminCallback.NOTIFICATION_ALL.value:
            self._start_notification_creation(callback_id, user_id, NotificationTarget.ALL_USERS)
        
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

    def _start_notification_creation(
        self,
        callback_id: str,
        user_id: int,
        target_type: NotificationTarget
    ) -> None:
        """Начать процесс создания уведомления.
        
        Args:
            callback_id: ID callback события
            user_id: ID администратора
            target_type: Тип получателей (админы или все пользователи)
        """
        try:
            # Переводим админа в состояние ожидания текста с указанием типа получателей
            self._state_manager.set_state(
                user_id,
                AdminState.WAITING_NOTIFICATION_TEXT,
                target_type=target_type
            )
            
            # Формируем текст инструкции в зависимости от типа получателей
            if target_type == NotificationTarget.ADMINS:
                instruction_text = (
                    "📝 **Создание тестового уведомления**\n\n"
                    "Пожалуйста, отправьте текст уведомления. "
                    "Вы можете использовать форматирование (жирный, курсив, ссылки), смайлы и медиафайлы (фото, видео).\n\n"
                    "🎯 **Получатели:** все администраторы"
                )
            else:  # ALL_USERS
                instruction_text = (
                    "📝 **Создание массового уведомления**\n\n"
                    "Пожалуйста, отправьте текст уведомления. "
                    "Вы можете использовать форматирование (жирный, курсив, ссылки), смайлы и медиафайлы (фото, видео).\n\n"
                    "🎯 **Получатели:** все пользователи базы данных"
                )
            
            # Обновляем текущее сообщение (убираем кнопки, меняем текст)
            self._api_client.answer_callback(
                callback_id=callback_id,
                text=instruction_text,
                format="markdown"
            )
            
            target_name = "админам" if target_type == NotificationTarget.ADMINS else "всей базе"
            print(f"   ✅ Админ переведён в режим ввода текста (рассылка: {target_name})")
            
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
            # Получаем тип получателей из состояния
            target_type = self._state_manager.get_target_type(user_id)
            
            # Формируем информацию о получателях
            if target_type == NotificationTarget.ADMINS:
                recipients_count = len(self._settings.admin_user_ids)
                recipients_info = f"🎯 **Получатели:** {recipients_count} администратор(ов)"
            else:  # ALL_USERS
                recipients_count = len(self._user_repository.get_all_user_ids())
                recipients_info = f"🎯 **Получатели:** {recipients_count} пользователь(ей)"
            
            # Формируем текст предпросмотра
            preview_text = (
                f"👁 **Предпросмотр уведомления:**\n\n"
                f"{text}\n\n"
                f"───────────────────\n"
                f"{recipients_info}\n\n"
                f"❓ Отправить это уведомление?"
            )
            
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
            
            print(f"   ✅ Предпросмотр отправлен admin_id={user_id} (получателей: {recipients_count})")
            
        except Exception as e:
            print(f"   ❌ Ошибка отправки предпросмотра: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _confirm_and_send_notification(self, callback_id: str, user_id: int) -> None:
        """Подтвердить отправку и запустить асинхронную рассылку.
        
        Немедленно отвечает на callback и запускает рассылку в фоновом потоке.
        
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
            
            # Получаем тип получателей
            target_type = self._state_manager.get_target_type(user_id)
            
            # Определяем список получателей в зависимости от типа
            if target_type == NotificationTarget.ADMINS:
                recipients = self._settings.admin_user_ids
                target_name = "администраторам"
            else:  # ALL_USERS
                recipients = self._user_repository.get_all_user_ids()
                target_name = "пользователям базы"
            
            # ВАЖНО: Немедленно отвечаем на callback (чтобы избежать timeout)
            self._api_client.answer_callback(
                callback_id=callback_id,
                notification=f"📤 Рассылка начата!\nПолучателей: {len(recipients)}"
            )
            
            # Сбрасываем состояние сразу
            self._state_manager.reset_state(user_id)
            
            print(f"\n📤 Запуск асинхронной рассылки {target_name} (получателей: {len(recipients)})")
            
            # Запускаем рассылку в отдельном потоке
            thread = threading.Thread(
                target=self._send_notifications_async,
                args=(user_id, notification_text, recipients, target_name),
                daemon=True
            )
            thread.start()
            
            print(f"   ✅ Фоновый поток рассылки запущен")
            
        except Exception as e:
            print(f"   ❌ Критическая ошибка подтверждения отправки: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def _send_notifications_async(
        self,
        initiator_id: int,
        notification_text: str,
        recipients: list[int],
        target_name: str
    ) -> None:
        """Асинхронная рассылка уведомлений в фоновом потоке.
        
        Выполняется в отдельном потоке, не блокирует основную работу бота.
        Отправляет прогресс-уведомления и финальную статистику.
        
        Args:
            initiator_id: ID администратора, инициировавшего рассылку
            notification_text: Текст уведомления
            recipients: Список ID получателей
            target_name: Название типа получателей (для логов)
        """
        start_time = time.time()
        
        # Счётчики для статистики
        sent_count = 0
        not_activated_ids = []
        not_found_ids = []
        
        total_recipients = len(recipients)
        progress_interval = self._settings.notification_progress_interval
        
        try:
            # Отправляем уведомления с задержками
            for index, recipient_id in enumerate(recipients, start=1):
                try:
                    self._api_client.send_message_to_user(
                        user_id=recipient_id,
                        text=notification_text,
                        format="markdown"
                    )
                    sent_count += 1
                    
                except Exception as e:
                    error_message = str(e)
                    
                    # Классифицируем ошибку
                    if "dialog.not.found" in error_message or "chat.not.found" in error_message:
                        not_activated_ids.append(recipient_id)
                    elif "user.not.found" in error_message:
                        not_found_ids.append(recipient_id)
                    else:
                        if self._settings.debug:
                            print(f"   ⚠️ Неизвестная ошибка recipient_id={recipient_id}: {e}")
                
                # Задержка между сообщениями для обхода rate limiting
                if index < total_recipients:  # Не ждём после последнего
                    time.sleep(self._settings.notification_delay)
                
                # Отправляем прогресс каждые N сообщений
                if index % progress_interval == 0 or index == total_recipients:
                    self._send_progress_notification(
                        initiator_id,
                        sent_count,
                        total_recipients,
                        not_activated_ids,
                        not_found_ids,
                        is_final=(index == total_recipients)
                    )
            
            # Вычисляем затраченное время
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            time_str = f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"
            
            # Отправляем финальную статистику
            self._send_final_statistics(
                initiator_id,
                sent_count,
                total_recipients,
                not_activated_ids,
                not_found_ids,
                time_str
            )
            
            print(f"   ✅ Рассылка завершена: {sent_count}/{total_recipients} за {time_str}")
            
        except Exception as e:
            print(f"   ❌ Критическая ошибка в фоновой рассылке: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()
            
            # Уведомляем админа об ошибке
            try:
                self._api_client.send_message_to_user(
                    user_id=initiator_id,
                    text=f"❌ Критическая ошибка рассылки: {e}"
                )
            except Exception:
                pass

    def _send_progress_notification(
        self,
        admin_id: int,
        sent_count: int,
        total_count: int,
        not_activated: list[int],
        not_found: list[int],
        is_final: bool = False
    ) -> None:
        """Отправить прогресс-уведомление администратору.
        
        Args:
            admin_id: ID администратора
            sent_count: Количество успешно отправленных
            total_count: Общее количество получателей
            not_activated: Список ID не активировавших бота
            not_found: Список ID не найденных пользователей
            is_final: Финальное уведомление или промежуточное
        """
        try:
            percentage = int((sent_count + len(not_activated) + len(not_found)) / total_count * 100)
            
            if is_final:
                icon = "✅"
                status = "Завершено"
            else:
                icon = "📊"
                status = "Прогресс"
            
            progress_text = (
                f"{icon} **{status}: {percentage}%**\n"
                f"✅ Доставлено: {sent_count}/{total_count}\n"
            )
            
            if not_activated:
                progress_text += f"⚠️ Не активировали: {len(not_activated)}\n"
            
            if not_found:
                progress_text += f"❌ Не найдены: {len(not_found)}\n"
            
            self._api_client.send_message_to_user(
                user_id=admin_id,
                text=progress_text.strip(),
                format="markdown"
            )
            
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки прогресса: {e}")

    def _send_final_statistics(
        self,
        admin_id: int,
        sent_count: int,
        total_count: int,
        not_activated: list[int],
        not_found: list[int],
        time_str: str
    ) -> None:
        """Отправить финальную статистику рассылки.
        
        Args:
            admin_id: ID администратора
            sent_count: Количество успешно отправленных
            total_count: Общее количество получателей
            not_activated: Список ID не активировавших бота
            not_found: Список ID не найденных пользователей
            time_str: Строка с затраченным временем
        """
        try:
            final_text = (
                f"🎉 **Рассылка завершена!**\n\n"
                f"📊 Доставлено: {sent_count}/{total_count}\n"
            )
            
            if not_activated:
                ids_preview = not_activated[:5]
                ids_text = ', '.join(map(str, ids_preview))
                if len(not_activated) > 5:
                    ids_text += f" ... (+{len(not_activated) - 5})"
                final_text += f"⚠️ Не активировали бота: {len(not_activated)}\n"
            
            if not_found:
                ids_preview = not_found[:5]
                ids_text = ', '.join(map(str, ids_preview))
                if len(not_found) > 5:
                    ids_text += f" ... (+{len(not_found) - 5})"
                final_text += f"❌ Не найдены: {len(not_found)}\n"
            
            final_text += f"\n⏱ Время выполнения: {time_str}"
            
            self._api_client.send_message_to_user(
                user_id=admin_id,
                text=final_text,
                format="markdown"
            )
            
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки финальной статистики: {e}")

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

    def is_waiting_notification_text(self, user_id: int) -> bool:
        """Проверить, ожидает ли админ ввода текста уведомления.
        
        Args:
            user_id: ID администратора
            
        Returns:
            True, если админ в состоянии ожидания текста
        """
        return self._state_manager.is_waiting_notification_text(user_id)