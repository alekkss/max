"""Клиент для работы с Max.ru Platform API."""

from abc import ABC, abstractmethod
from typing import Optional, Any
import time

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException, Timeout
from urllib3.util.retry import Retry
from pathlib import Path

from src.config.settings import Settings
from src.models.update import UpdateType


class MaxApiError(Exception):
    """Базовое исключение для ошибок Max API."""
    pass


class MaxApiTimeoutError(MaxApiError):
    """Ошибка таймаута при запросе к API."""
    pass


class MaxApiHttpError(MaxApiError):
    """Ошибка HTTP при запросе к API."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class IMaxApiClient(ABC):
    """Интерфейс клиента для Max.ru API."""

    @abstractmethod
    def get_updates(self, marker: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
        """Получить обновления через long polling.

        Args:
            marker: Маркер для получения новых обновлений
            timeout: Таймаут long polling в секундах

        Returns:
            Словарь с ключами 'updates' и 'marker'

        Raises:
            MaxApiTimeoutError: При таймауте запроса
            MaxApiHttpError: При HTTP ошибке
        """
        pass

    @abstractmethod
    def send_message_to_user(
        self,
        user_id: int,
        text: str,
        format: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Отправить сообщение пользователю.

        Args:
            user_id: ID пользователя
            text: Текст сообщения
            format: Формат текста ('markdown' или 'html'), optional
            reply_to: ID сообщения для reply-ответа, optional
            attachments: Вложения (фото, видео, файлы и т.д.), optional

        Returns:
            Response от API с данными отправленного сообщения

        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        pass

    @abstractmethod
    def send_message_to_chat(
        self,
        chat_id: int,
        text: str,
        format: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Отправить сообщение в групповой чат.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            format: Формат текста ('markdown' или 'html'), optional
            attachments: Вложения (фото, видео, файлы и т.д.), optional

        Returns:
            Response от API с данными отправленного сообщения

        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        pass

    @abstractmethod
    def send_message_with_keyboard(
        self,
        text: str,
        buttons: list[list[tuple[str, str]]],
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Отправить сообщение с inline-клавиатурой.

        Args:
            text: Текст сообщения
            buttons: Список строк кнопок. Каждая строка - список кортежей (текст, callback_data)
                     Например: [[("Кнопка 1", "callback_1"), ("Кнопка 2", "callback_2")]]
            user_id: ID пользователя (если отправляем пользователю)
            chat_id: ID чата (если отправляем в чат)
            format: Формат текста ('markdown' или 'html'), optional

        Returns:
            Response от API с данными отправленного сообщения

        Raises:
            ValueError: Если не указан ни user_id, ни chat_id
            MaxApiHttpError: При ошибке отправки
        """
        pass

    @abstractmethod
    def answer_callback(
        self,
        callback_id: str,
        text: Optional[str] = None,
        buttons: Optional[list[list[tuple[str, str]]]] = None,
        notification: Optional[str] = None,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Ответить на callback от inline-кнопки.

        Args:
            callback_id: ID callback события
            text: Новый текст сообщения (для обновления)
            buttons: Новые кнопки (для обновления)
            notification: Текст одноразового уведомления
            format: Формат текста ('markdown' или 'html'), optional

        Returns:
            Response от API

        Raises:
            MaxApiHttpError: При ошибке ответа
        """
        pass

    @abstractmethod
    def edit_message(
        self,
        chat_id: int,
        message_id: str,
        new_text: str,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Редактировать существующее сообщение в чате.

        Args:
            chat_id: ID чата, где находится сообщение
            message_id: ID сообщения для редактирования
            new_text: Новый текст сообщения
            format: Формат текста ('markdown' или 'html'), optional

        Returns:
            Response от API с данными обновлённого сообщения

        Raises:
            MaxApiHttpError: При ошибке редактирования
        """
        pass


class MaxApiClient(IMaxApiClient):
    """Реализация клиента для Max.ru Platform API.

    Включает автоматическую retry-логику на уровне транспорта (urllib3.Retry)
    и пересоздание сессии при обрыве TCP-соединения (RemoteDisconnected).
    """

    # Максимальное количество попыток при обрыве соединения
    _MAX_CONNECTION_RETRIES: int = 3

    # Задержки между попытками (секунды): попытка 1 → 2с, попытка 2 → 4с
    _RETRY_BACKOFF_FACTOR: int = 2

    # Типы событий, на которые подписывается бот.
    # Формируется из enum UpdateType — единый источник истины.
    _SUBSCRIPTION_TYPES: str = ",".join(
        update_type.value for update_type in UpdateType
    )

    def __init__(self, settings: Settings) -> None:
        """Инициализация клиента.

        Args:
            settings: Конфигурация приложения
        """
        self._settings = settings
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Создать HTTP-сессию с retry-стратегией.

        Настраивает:
        - urllib3.Retry для автоматических повторов при 502/503/504
        - Заголовок Connection: close для отключения keep-alive
        - HTTPAdapter с ограниченным пулом соединений

        Returns:
            Настроенная сессия requests.Session
        """
        session = requests.Session()

        # Стратегия автоматических retry на уровне транспорта (urllib3).
        # Обрабатывает серверные ошибки ДО того, как они дойдут до нашего кода.
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=1,
            pool_maxsize=5,
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Копируем заголовки из настроек и добавляем Connection: close.
        # Connection: close отключает keep-alive — каждый запрос идёт через
        # новое TCP-соединение. Это устраняет корневую причину RemoteDisconnected:
        # сервер Max.ru закрывает idle-соединение по своему таймауту, а клиент
        # пытается отправить запрос в уже закрытый сокет.
        headers = dict(self._settings.api_headers)
        headers["Connection"] = "close"
        session.headers.update(headers)

        return session

    def _reset_session(self) -> None:
        """Пересоздать HTTP-сессию после критического сбоя соединения.

        Закрывает старую сессию (освобождает сокеты) и создаёт новую
        с чистым пулом соединений. Вызывается при RemoteDisconnected.
        """
        try:
            self._session.close()
        except Exception:
            pass
        self._session = self._create_session()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        request_timeout: Optional[float] = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Единая точка для всех HTTP-запросов с обработкой обрывов соединения.

        При ошибке RemoteDisconnected пересоздаёт сессию и повторяет запрос
        до _MAX_CONNECTION_RETRIES раз с экспоненциальным backoff.

        Args:
            method: HTTP метод ('GET', 'POST', 'PUT')
            endpoint: Путь API (например, '/messages')
            request_timeout: Таймаут HTTP-запроса в секундах.
                             Если не указан, используется polling_request_timeout из настроек.
            **kwargs: Дополнительные аргументы для requests (params, json и т.д.)

        Returns:
            Распарсенный JSON-ответ от API

        Raises:
            MaxApiTimeoutError: При таймауте запроса
            MaxApiHttpError: При HTTP ошибке (4xx/5xx)
            MaxApiError: При сетевой ошибке после исчерпания попыток
        """
        url = f"{self._settings.base_url}{endpoint}"
        timeout = request_timeout if request_timeout is not None else self._settings.polling_request_timeout

        for attempt in range(1, self._MAX_CONNECTION_RETRIES + 1):
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    timeout=timeout,
                    **kwargs,
                )

                if response.status_code not in [200, 201]:
                    raise MaxApiHttpError(
                        f"Ошибка HTTP {response.status_code}: {response.text}",
                        response.status_code,
                    )

                return response.json() if response.content else {}

            except RequestsConnectionError as e:
                error_str = str(e)

                # RemoteDisconnected — сервер закрыл TCP-соединение.
                # ConnectionResetError — соединение сброшено на уровне ОС.
                # Оба случая решаются пересозданием сессии.
                is_connection_reset = (
                    "RemoteDisconnected" in error_str
                    or "Connection aborted" in error_str
                    or "ConnectionResetError" in error_str
                )

                if is_connection_reset:
                    print(
                        f"⚠️ Соединение сброшено сервером "
                        f"(попытка {attempt}/{self._MAX_CONNECTION_RETRIES})"
                    )
                    self._reset_session()

                    if attempt < self._MAX_CONNECTION_RETRIES:
                        delay = attempt * self._RETRY_BACKOFF_FACTOR
                        print(f"⏳ Пересоздание сессии, повтор через {delay} сек...")
                        time.sleep(delay)
                        continue

                    # Исчерпали все попытки
                    raise MaxApiError(
                        f"Соединение сброшено сервером после "
                        f"{self._MAX_CONNECTION_RETRIES} попыток: {e}"
                    ) from e

                # Другие виды ConnectionError — пробрасываем сразу
                raise MaxApiError(f"Ошибка соединения: {e}") from e

            except Timeout as e:
                raise MaxApiTimeoutError(f"Таймаут запроса: {e}") from e

            except RequestException as e:
                raise MaxApiError(f"Ошибка запроса: {e}") from e

        # Сюда не должны попасть, но для безопасности типов
        raise MaxApiError("Исчерпаны все попытки выполнения запроса")

    def get_updates(self, marker: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
        """Получить обновления через long polling.

        Подписывается на все типы событий из enum UpdateType:
        bot_started, message_created, message_callback.
        Без параметра types API не возвращает события.
        """
        params: dict[str, Any] = {
            "timeout": timeout,
            "types": self._SUBSCRIPTION_TYPES,
        }
        if marker:
            params["marker"] = marker

        return self._make_request(
            method="GET",
            endpoint="/updates",
            params=params,
            request_timeout=self._settings.polling_request_timeout,
        )

    def send_message_to_user(
        self,
        user_id: int,
        text: str,
        format: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Отправить сообщение пользователю."""
        return self._send_message(
            params={"user_id": user_id},
            text=text,
            format=format,
            reply_to=reply_to,
            attachments=attachments,
        )

    def send_message_to_chat(
        self,
        chat_id: int,
        text: str,
        format: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Отправить сообщение в групповой чат."""
        return self._send_message(
            params={"chat_id": chat_id},
            text=text,
            format=format,
            attachments=attachments,
        )

    def send_message_with_keyboard(
        self,
        text: str,
        buttons: list[list[tuple[str, str]]],
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Отправить сообщение с inline-клавиатурой."""
        # Валидация: должен быть указан либо user_id, либо chat_id
        if user_id is None and chat_id is None:
            raise ValueError("Необходимо указать либо user_id, либо chat_id")

        if user_id is not None and chat_id is not None:
            raise ValueError("Нельзя указывать одновременно user_id и chat_id")

        # Формируем параметры запроса
        params: dict[str, int] = {}
        if user_id is not None:
            params["user_id"] = user_id
        else:
            params["chat_id"] = chat_id  # type: ignore

        # Формируем структуру inline_keyboard согласно документации Max.ru API
        keyboard_buttons = [
            [
                {
                    "type": "callback",
                    "text": button_text,
                    "payload": callback_data,
                }
                for button_text, callback_data in row
            ]
            for row in buttons
        ]

        # Формируем payload с attachments
        payload: dict[str, Any] = {
            "text": text,
            "attachments": [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": keyboard_buttons
                    },
                }
            ],
        }

        # Добавляем формат, если указан
        if format in ["markdown", "html"]:
            payload["format"] = format

        return self._make_request(
            method="POST",
            endpoint="/messages",
            params=params,
            json=payload,
            request_timeout=10,
        )

    def answer_callback(
        self,
        callback_id: str,
        text: Optional[str] = None,
        buttons: Optional[list[list[tuple[str, str]]]] = None,
        notification: Optional[str] = None,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Ответить на callback от inline-кнопки."""
        payload: dict[str, Any] = {}

        # Либо обновляем сообщение, либо отправляем уведомление
        if text is not None or buttons is not None:
            # Обновляем сообщение
            message_body: dict[str, Any] = {}

            if text is not None:
                message_body["text"] = text

            if buttons is not None:
                # Формируем клавиатуру
                keyboard_buttons = [
                    [
                        {
                            "type": "callback",
                            "text": button_text,
                            "payload": callback_data,
                        }
                        for button_text, callback_data in row
                    ]
                    for row in buttons
                ]

                message_body["attachments"] = [
                    {
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": keyboard_buttons
                        },
                    }
                ]

            if format in ["markdown", "html"]:
                message_body["format"] = format

            payload["message"] = message_body

        elif notification is not None:
            # Отправляем одноразовое уведомление
            payload["notification"] = notification

        return self._make_request(
            method="POST",
            endpoint="/answers",
            params={"callback_id": callback_id},
            json=payload,
            request_timeout=10,
        )

    def edit_message(
        self,
        chat_id: int,
        message_id: str,
        new_text: str,
        format: Optional[str] = None
    ) -> dict[str, Any]:
        """Редактировать существующее сообщение в чате."""
        payload: dict[str, Any] = {"text": new_text}

        # Добавляем формат, если указан
        if format in ["markdown", "html"]:
            payload["format"] = format

        return self._make_request(
            method="PUT",
            endpoint="/messages",
            params={"chat_id": chat_id, "message_id": message_id},
            json=payload,
            request_timeout=10,
        )

    def upload_file(self, file_path: str) -> str:
        """Загрузить файл на сервер Max.ru.

        Args:
            file_path: Путь к файлу для загрузки

        Returns:
            Token загруженного файла для использования в attachments

        Raises:
            MaxApiHttpError: При ошибке загрузки
            FileNotFoundError: Если файл не найден
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        # Шаг 1: Получаем URL для загрузки
        upload_data = self._make_request(
            method="POST",
            endpoint="/uploads",
            params={"type": "file"},
            request_timeout=10,
        )

        print(f"🔍 DEBUG: Ответ от /uploads: {upload_data}")

        upload_url = upload_data.get("url")
        if not upload_url:
            raise MaxApiError(
                f"Некорректный ответ от /uploads: отсутствует url. Ответ: {upload_data}"
            )

        # Шаг 2: Загружаем файл на полученный URL.
        # Используем отдельный запрос (не через _make_request),
        # так как URL внешний и не относится к base_url API.
        try:
            with open(file_path, "rb") as file:
                files = {"data": (path.name, file, "application/octet-stream")}
                upload_response = requests.post(
                    upload_url,
                    files=files,
                    timeout=60,
                )

            if upload_response.status_code not in [200, 201]:
                raise MaxApiHttpError(
                    f"Ошибка загрузки файла: {upload_response.text}",
                    upload_response.status_code,
                )

            # Проверяем, есть ли token в ответе после загрузки
            try:
                upload_result = upload_response.json()
                print(f"🔍 DEBUG: Ответ после загрузки файла: {upload_result}")

                file_token = upload_result.get("token")
                if file_token:
                    return file_token
            except ValueError:
                print("🔍 DEBUG: Ответ не JSON, используем id из первого запроса")

            # Если token не пришёл после загрузки, используем id из первого запроса
            file_id = upload_data.get("id")
            if file_id:
                return str(file_id)

            raise MaxApiError(
                f"Не удалось извлечь token из ответа. "
                f"Шаг 1: {upload_data}, Шаг 2: статус {upload_response.status_code}"
            )

        except Timeout as e:
            raise MaxApiTimeoutError(f"Таймаут загрузки файла: {e}") from e
        except RequestException as e:
            raise MaxApiError(f"Ошибка загрузки файла: {e}") from e

    def send_file_to_chat(
        self,
        chat_id: int,
        file_token: str,
        text: str,
        filename: str
    ) -> dict[str, Any]:
        """Отправить файл в групповой чат.

        Args:
            chat_id: ID чата
            file_token: Token загруженного файла (из upload_file)
            text: Текст сообщения (описание файла)
            filename: Имя файла для отображения

        Returns:
            Response от API с данными отправленного сообщения

        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        payload: dict[str, Any] = {
            "text": text,
            "attachments": [
                {
                    "type": "file",
                    "payload": {
                        "token": file_token,
                    },
                }
            ],
        }

        return self._make_request(
            method="POST",
            endpoint="/messages",
            params={"chat_id": chat_id},
            json=payload,
            request_timeout=10,
        )

    def _send_message(
        self,
        params: dict[str, int],
        text: str,
        format: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, Any]:
        """Внутренний метод для отправки сообщений.

        Поддерживает отправку текста с вложениями (фото, видео, файлы).
        Вложения передаются как есть — это объекты из API Max.ru,
        содержащие type и payload с token.

        Args:
            params: Параметры запроса (user_id или chat_id)
            text: Текст сообщения
            format: Формат текста ('markdown' или 'html'), optional
            reply_to: ID сообщения для reply-ответа, optional
            attachments: Список вложений в формате Max.ru API, optional.
                         Каждый элемент — словарь с ключами 'type' и 'payload'.
                         Например: [{"type": "image", "payload": {"token": "abc123"}}]

        Returns:
            Response от API

        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        payload: dict[str, Any] = {"text": text}

        # Добавляем формат, если указан
        if format in ["markdown", "html"]:
            payload["format"] = format

        # Добавляем reply_to, если указан
        if reply_to:
            payload["link"] = {
                "type": "reply",
                "mid": reply_to,
            }

        # Добавляем вложения, если переданы.
        # Вложения приходят из API в готовом формате (type + payload с token),
        # поэтому передаём их напрямую без преобразования.
        if attachments:
            payload["attachments"] = attachments

        return self._make_request(
            method="POST",
            endpoint="/messages",
            params=params,
            json=payload,
            request_timeout=10,
        )

    def close(self) -> None:
        """Закрыть сессию."""
        self._session.close()
