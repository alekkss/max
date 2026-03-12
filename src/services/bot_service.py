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
    - Устойчивость к сетевым сбоям с экспоненциальным backoff
    """

    # Максимальная задержка между повторами при серии ошибок (секунды)
    _MAX_RETRY_DELAY: int = 60

    # Порог последовательных ошибок для предупреждения о недоступности API
    _MAX_CONSECUTIVE_ERRORS_WARNING: int = 10

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
        self._consecutive_errors: int = 0

    def set_update_handler(self, handler) -> None:
        """Установить обработчик событий.

        Args:
            handler: UpdateHandler для обработки событий
        """
        self._update_handler = handler

    def start(self) -> None:
        """Запустить бота в режиме long polling.

        При сетевых ошибках применяется экспоненциальный backoff:
        первая ошибка — базовая задержка (error_retry_delay из настроек),
        каждая следующая ошибка подряд удваивает задержку до максимума
        (_MAX_RETRY_DELAY). При успешном получении обновлений счётчик
        ошибок сбрасывается.

        Raises:
            RuntimeError: Если не установлен update_handler
        """
        if self._update_handler is None:
            raise RuntimeError(
                "Обработчик событий не установлен. "
                "Вызовите set_update_handler() перед запуском."
            )

        self._is_running = True
        self._consecutive_errors = 0
        self._print_startup_info()

        while self._is_running:
            try:
                self._poll_updates()

                # Успешное получение обновлений — сбрасываем счётчик ошибок.
                # Если до этого были ошибки, логируем восстановление.
                if self._consecutive_errors > 0:
                    print(
                        f"✅ Соединение восстановлено "
                        f"(после {self._consecutive_errors} ошибок подряд)"
                    )
                    self._consecutive_errors = 0

            except KeyboardInterrupt:
                print("\n\n⛔ Получен сигнал остановки")
                self.stop()
                break

            except MaxApiTimeoutError:
                # Таймауты long polling — это нормально, просто продолжаем.
                # Не увеличиваем счётчик ошибок, так как это штатное поведение.
                continue

            except MaxApiError as e:
                self._consecutive_errors += 1
                delay = self._calculate_retry_delay()

                if self._consecutive_errors >= self._MAX_CONSECUTIVE_ERRORS_WARNING:
                    print(
                        f"🔴 {self._consecutive_errors} ошибок подряд! "
                        f"Возможно, API Max.ru недоступен."
                    )
                    print(f"   Последняя ошибка: {e}")
                    print(f"   ⏳ Следующая попытка через {delay} сек...")
                else:
                    print(f"❌ Ошибка API: {e}")
                    print(f"⏳ Повтор через {delay} сек... (ошибок подряд: {self._consecutive_errors})")

                time.sleep(delay)

            except Exception as e:
                self._consecutive_errors += 1
                delay = self._calculate_retry_delay()

                print(f"❌ Неожиданная ошибка: {e}")
                print(f"⏳ Повтор через {delay} сек... (ошибок подряд: {self._consecutive_errors})")

                if self._settings.debug:
                    import traceback
                    traceback.print_exc()

                time.sleep(delay)

    def stop(self) -> None:
        """Остановить бота."""
        self._is_running = False
        print("🛑 Бот остановлен")

    def _calculate_retry_delay(self) -> float:
        """Рассчитать задержку перед следующей попыткой.

        Использует экспоненциальный backoff: базовая задержка удваивается
        с каждой последовательной ошибкой, но не превышает _MAX_RETRY_DELAY.

        Формула: min(base_delay * 2^(errors - 1), max_delay)
        Пример при base_delay=5: 5с → 10с → 20с → 40с → 60с (максимум)

        Returns:
            Задержка в секундах
        """
        base_delay = self._settings.error_retry_delay
        exponent = self._consecutive_errors - 1
        delay = base_delay * (2 ** exponent)
        return min(delay, self._MAX_RETRY_DELAY)

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
