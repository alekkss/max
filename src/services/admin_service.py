"""Сервис для работы с админ-панелью бота."""

from typing import Optional

from src.clients.max_api_client import IMaxApiClient
from src.config.settings import Settings
from src.utils.admin_constants import AdminCallback, AdminMessage, AdminButton


class AdminService:
    """Сервис управления админ-панелью.
    
    Отвечает за:
    - Проверку прав доступа к админ-панели
    - Отправку меню с inline-кнопками
    - Обработку callback-событий от кнопок
    - Выполнение административных действий
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

    def send_notification_menu(self, user_id: int) -> None:
        """Отправить меню выбора получателей уведомления.
        
        Args:
            user_id: ID администратора
        """
        try:
            # Формируем кнопки меню уведомлений
            buttons = [
                [
                    (AdminButton.TEST, AdminCallback.NOTIFICATION_TEST.value),
                    (AdminButton.ALL_DATABASE, AdminCallback.NOTIFICATION_ALL.value)
                ],
                [
                    (AdminButton.BACK, AdminCallback.BACK_TO_MAIN.value)
                ]
            ]
            
            self._api_client.send_message_with_keyboard(
                text=AdminMessage.NOTIFICATION_MENU_TEXT,
                buttons=buttons,
                user_id=user_id,
                format="markdown"
            )
            
            print(f"   ✅ Меню уведомлений отправлено admin_id={user_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка отправки меню уведомлений: {e}")
            if self._settings.debug:
                import traceback
                traceback.print_exc()

    def handle_callback(self, user_id: int, callback_data: str) -> None:
        """Обработать callback-событие от inline-кнопки.
        
        Args:
            user_id: ID пользователя, нажавшего кнопку
            callback_data: Данные callback (payload кнопки)
        """
        # Проверяем права доступа
        if not self.is_admin(user_id):
            self.send_access_denied(user_id)
            return
        
        print(f"\n🔘 Callback от admin_id={user_id}: {callback_data}")
        
        # Маршрутизация по callback_data
        if callback_data == AdminCallback.SEND_NOTIFICATION.value:
            self.send_notification_menu(user_id)
        
        elif callback_data == AdminCallback.BACK_TO_MAIN.value:
            self.send_main_menu(user_id)
        
        elif callback_data == AdminCallback.NOTIFICATION_TEST.value:
            self._send_test_notification_stub(user_id)
        
        elif callback_data == AdminCallback.NOTIFICATION_ALL.value:
            self._send_all_notification_stub(user_id)
        
        else:
            # Неизвестный callback
            if self._settings.debug:
                print(f"   ⚠️ Неизвестный callback: {callback_data}")

    def _send_test_notification_stub(self, user_id: int) -> None:
        """Заглушка для отправки тестового уведомления.
        
        Args:
            user_id: ID администратора
        """
        try:
            self._api_client.send_message_to_user(
                user_id=user_id,
                text=AdminMessage.TEST_NOTIFICATION_STUB
            )
            print(f"   🧪 Заглушка: тестовое уведомление")
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки заглушки: {e}")

    def _send_all_notification_stub(self, user_id: int) -> None:
        """Заглушка для рассылки по всей базе.
        
        Args:
            user_id: ID администратора
        """
        try:
            self._api_client.send_message_to_user(
                user_id=user_id,
                text=AdminMessage.ALL_NOTIFICATION_STUB
            )
            print(f"   📢 Заглушка: рассылка по базе")
        except Exception as e:
            if self._settings.debug:
                print(f"   ⚠️ Ошибка отправки заглушки: {e}")