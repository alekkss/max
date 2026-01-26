"""Главный сервис бота."""

import time
from typing import Optional

from src.clients.max_api_client import IMaxApiClient, MaxApiError, MaxApiTimeoutError
from src.config.settings import Settings


class BotService:
    """Главный сервис для управления ботом.
    
    Отвечает за:
    - Запуск и остановку long polling
    - Получение обновлений от API
    - Делегирование обработки событий хендлерам
    - Управление жизненным циклом приложения
    """
    
    def __init__(
        self,
        api_client: IMaxApiClient,
        settings: Settings
    ) -> None:
        """Инициализация сервиса.
        
        Args:
            api_client: API-клиент для получения обновлений
            settings: Конфигурация приложения
        """
        self._api_client = api_client
        self._settings = settings
        self._last_marker: Optional[str] = None
        self._is_running = False
        self._update_handler = None
    
    def set_update_handler(self, handler) -> None:
        """Установить обработчик событий.
        
        Args:
            handler: UpdateHandler для обработки событий
        """
        self._update_handler = handler
    
    def start(self) -> None:
        """Запустить бота в режиме long polling."""
        if self._update_handler is None:
            raise RuntimeError("Update handler is not set. Call set_update_handler() first.")
        
        self._is_running = True
        self._print_startup_info()
        
        while self._is_running:
            try:
                self._poll_updates()
                
            except KeyboardInterrupt:
                print("\n\n⛔ Получен сигнал остановки")
                self.stop()
                break
                
            except MaxApiTimeoutError:
                # Таймауты long polling - это нормально, просто продолжаем
                continue
                
            except MaxApiError as e:
                print(f"❌ Ошибка API: {e}")
                print(f"⏳ Повтор через {self._settings.error_retry_delay} секунд...")
                time.sleep(self._settings.error_retry_delay)
                
            except Exception as e:
                print(f"❌ Неожиданная ошибка: {e}")
                print(f"⏳ Повтор через {self._settings.error_retry_delay} секунд...")
                time.sleep(self._settings.error_retry_delay)
    
    def stop(self) -> None:
        """Остановить бота."""
        self._is_running = False
        print("🛑 Бот остановлен")
    
    def _poll_updates(self) -> None:
        """Получить и обработать обновления от API."""
        response = self._api_client.get_updates(
            marker=self._last_marker,
            timeout=self._settings.polling_timeout
        )
        
        updates = response.get("updates", [])
        self._last_marker = response.get("marker")
        
        # Обрабатываем каждое событие
        for update in updates:
            try:
                self._update_handler.handle_update(update)
                
                # Небольшая задержка между обработкой событий
                if self._settings.message_delay > 0:
                    time.sleep(self._settings.message_delay)
                    
            except Exception as e:
                print(f"❌ Ошибка обработки события: {e}")
                if self._settings.debug:
                    import traceback
                    traceback.print_exc()
                # Продолжаем обработку следующих событий
                continue
    
    def _print_startup_info(self) -> None:
        """Вывести информацию о запуске бота."""
        print("🤖 Бот LaVita yarn запущен!")
        print(f"📡 Подключение к {self._settings.base_url}")
        print(f"💬 Чат поддержки: {self._settings.support_chat_id}")
        print(f"🤖 ID бота: {self._settings.bot_id}")
        print("-" * 70)
        print("✨ Операторы могут просто нажать 'Ответить' на сообщение клиента!")
        print("-" * 70)
        
        if self._settings.debug:
            print("⚠️  DEBUG режим включен")
            print("-" * 70)
