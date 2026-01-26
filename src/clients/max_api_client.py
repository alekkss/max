"""Клиент для работы с Max.ru Platform API."""

from abc import ABC, abstractmethod
from typing import Optional, Any
import requests
from requests.exceptions import RequestException, Timeout
from pathlib import Path

from src.config.settings import Settings


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
    def send_message_to_user(self, user_id: int, text: str) -> dict[str, Any]:
        """Отправить сообщение пользователю.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
            
        Returns:
            Response от API с данными отправленного сообщения
            
        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        pass
    
    @abstractmethod
    def send_message_to_chat(self, chat_id: int, text: str) -> dict[str, Any]:
        """Отправить сообщение в групповой чат.
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            
        Returns:
            Response от API с данными отправленного сообщения
            
        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        pass


class MaxApiClient(IMaxApiClient):
    """Реализация клиента для Max.ru Platform API."""
    
    def __init__(self, settings: Settings) -> None:
        """Инициализация клиента.
        
        Args:
            settings: Конфигурация приложения
        """
        self._settings = settings
        self._session = requests.Session()
        self._session.headers.update(settings.api_headers)
    
    def get_updates(self, marker: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
        """Получить обновления через long polling."""
        params: dict[str, Any] = {"timeout": timeout}
        if marker:
            params["marker"] = marker
        
        try:
            response = self._session.get(
                f"{self._settings.base_url}/updates",
                params=params,
                timeout=self._settings.polling_request_timeout
            )
            
            if response.status_code != 200:
                raise MaxApiHttpError(
                    f"Failed to get updates: {response.text}",
                    response.status_code
                )
            
            return response.json()
        
        except Timeout as e:
            raise MaxApiTimeoutError(f"Request timeout: {e}") from e
        except RequestException as e:
            raise MaxApiError(f"Request failed: {e}") from e
    
    def send_message_to_user(self, user_id: int, text: str) -> dict[str, Any]:
        """Отправить сообщение пользователю."""
        return self._send_message(params={"user_id": user_id}, text=text)
    
    def send_message_to_chat(self, chat_id: int, text: str) -> dict[str, Any]:
        """Отправить сообщение в групповой чат."""
        return self._send_message(params={"chat_id": chat_id}, text=text)
    
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
        
        try:
            # Шаг 1: Получаем URL для загрузки
            response = self._session.post(
                f"{self._settings.base_url}/uploads",
                params={"type": "file"},
                timeout=10
            )
            
            if response.status_code != 200:
                raise MaxApiHttpError(
                    f"Failed to get upload URL: {response.text}",
                    response.status_code
                )
            
            upload_data = response.json()
            upload_url = upload_data.get("url")
            file_token = upload_data.get("token")
            
            if not upload_url or not file_token:
                raise MaxApiError("Invalid upload response: missing url or token")
            
            # Шаг 2: Загружаем файл на полученный URL
            with open(file_path, "rb") as file:
                files = {"data": (path.name, file, "application/octet-stream")}
                
                upload_response = requests.post(
                    upload_url,
                    files=files,
                    timeout=60  # Больше таймаут для загрузки файла
                )
                
                if upload_response.status_code not in [200, 201]:
                    raise MaxApiHttpError(
                        f"Failed to upload file: {upload_response.text}",
                        upload_response.status_code
                    )
            
            return file_token
        
        except Timeout as e:
            raise MaxApiTimeoutError(f"File upload timeout: {e}") from e
        except RequestException as e:
            raise MaxApiError(f"File upload failed: {e}") from e
    
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
        try:
            payload = {
                "text": text,
                "attachments": [
                    {
                        "type": "file",
                        "payload": {
                            "token": file_token
                        }
                    }
                ]
            }
            
            response = self._session.post(
                f"{self._settings.base_url}/messages",
                params={"chat_id": chat_id},
                json=payload,
                timeout=10
            )
            
            if response.status_code not in [200, 201]:
                raise MaxApiHttpError(
                    f"Failed to send file: {response.text}",
                    response.status_code
                )
            
            return response.json()
        
        except Timeout as e:
            raise MaxApiTimeoutError(f"File send timeout: {e}") from e
        except RequestException as e:
            raise MaxApiError(f"File send failed: {e}") from e
    
    def _send_message(self, params: dict[str, int], text: str) -> dict[str, Any]:
        """Внутренний метод для отправки сообщений.
        
        Args:
            params: Параметры запроса (user_id или chat_id)
            text: Текст сообщения
            
        Returns:
            Response от API
            
        Raises:
            MaxApiHttpError: При ошибке отправки
        """
        try:
            response = self._session.post(
                f"{self._settings.base_url}/messages",
                params=params,
                json={"text": text},
                timeout=10
            )
            
            if response.status_code not in [200, 201]:
                raise MaxApiHttpError(
                    f"Failed to send message: {response.text}",
                    response.status_code
                )
            
            return response.json()
        
        except Timeout as e:
            raise MaxApiTimeoutError(f"Message send timeout: {e}") from e
        except RequestException as e:
            raise MaxApiError(f"Message send failed: {e}") from e
    
    def close(self) -> None:
        """Закрыть сессию."""
        self._session.close()
