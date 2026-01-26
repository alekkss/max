"""Репозиторий для работы с сообщениями."""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

from src.models.message import (
    Message,
    MessageCreate,
    MessageMapping,
    MessageMappingCreate,
    MessageDirection
)
from src.database.connection import DatabaseConnection


class IMessageRepository(ABC):
    """Интерфейс репозитория сообщений."""

    @abstractmethod
    def save_message(self, message_data: MessageCreate) -> Message:
        """Сохранить новое сообщение в истории.
        
        Args:
            message_data: Данные сообщения для сохранения
            
        Returns:
            Сохраненное сообщение с ID и timestamp из БД
        """
        pass

    @abstractmethod
    def get_user_messages(self, user_id: int, limit: int = 50) -> List[Message]:
        """Получить историю сообщений пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений, отсортированных по времени (новые первые)
        """
        pass

    @abstractmethod
    def count_operator_replies(self, user_id: int) -> int:
        """Подсчитать количество ответов оператора для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество сообщений от операторов (direction = TO_USER)
        """
        pass

    @abstractmethod
    def count_replies_since_last_user_message(self, user_id: int) -> int:
        """Подсчитать ответы оператора после последнего сообщения пользователя.
        
        Считает только те ответы, которые были отправлены после самого
        свежего сообщения FROM_USER. Это позволяет показывать количество
        ответов по текущему вопросу, а не за всё время.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество ответов по текущему вопросу (0 если вопрос новый)
        """
        pass

    @abstractmethod
    def save_mapping(self, mapping_data: MessageMappingCreate) -> MessageMapping:
        """Сохранить маппинг между message_id в чате и user_id.
        
        Args:
            mapping_data: Данные маппинга
            
        Returns:
            Сохраненный маппинг
        """
        pass

    @abstractmethod
    def get_mapping_by_message_id(self, message_id: str) -> Optional[MessageMapping]:
        """Получить маппинг по message_id из чата поддержки.
        
        Args:
            message_id: ID сообщения в групповом чате
            
        Returns:
            MessageMapping если найден, None если не существует
        """
        pass


class SQLiteMessageRepository(IMessageRepository):
    """Реализация репозитория сообщений для SQLite."""

    def __init__(self, db: DatabaseConnection) -> None:
        """Инициализация репозитория.
        
        Args:
            db: Подключение к базе данных
        """
        self._db = db

    def save_message(self, message_data: MessageCreate) -> Message:
        """Сохранить новое сообщение в истории."""
        with self._db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO messages (user_id, text, direction, operator_name)
                VALUES (?, ?, ?, ?)
            ''', (
                message_data.user_id,
                message_data.text,
                message_data.direction.value,
                message_data.operator_name
            ))
            message_id = cursor.lastrowid

        # Получаем сохраненное сообщение
        with self._db.cursor() as cursor:
            cursor.execute('''
                SELECT id, user_id, text, direction, operator_name, timestamp
                FROM messages
                WHERE id = ?
            ''', (message_id,))
            row = cursor.fetchone()
            
            if row is None:
                raise RuntimeError(f"Failed to retrieve saved message {message_id}")
            
            return self._row_to_message(row)

    def get_user_messages(self, user_id: int, limit: int = 50) -> List[Message]:
        """Получить историю сообщений пользователя."""
        with self._db.cursor() as cursor:
            cursor.execute('''
                SELECT id, user_id, text, direction, operator_name, timestamp
                FROM messages
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
            rows = cursor.fetchall()
            
            return [self._row_to_message(row) for row in rows]

    def count_operator_replies(self, user_id: int) -> int:
        """Подсчитать количество ответов оператора для пользователя."""
        with self._db.cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM messages
                WHERE user_id = ? AND direction = ?
            ''', (user_id, MessageDirection.TO_USER.value))
            row = cursor.fetchone()
            
            return row["count"] if row else 0

    def count_replies_since_last_user_message(self, user_id: int) -> int:
        """Подсчитать ответы оператора после последнего сообщения пользователя."""
        with self._db.cursor() as cursor:
            # Находим timestamp последнего сообщения от пользователя
            cursor.execute('''
                SELECT timestamp
                FROM messages
                WHERE user_id = ? AND direction = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (user_id, MessageDirection.FROM_USER.value))
            
            last_user_message = cursor.fetchone()
            
            # Если пользователь ещё не писал сообщений, возвращаем 0
            if last_user_message is None:
                return 0
            
            last_user_timestamp = last_user_message["timestamp"]
            
            # Считаем ответы оператора после этого timestamp
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM messages
                WHERE user_id = ? 
                  AND direction = ? 
                  AND timestamp > ?
            ''', (user_id, MessageDirection.TO_USER.value, last_user_timestamp))
            
            row = cursor.fetchone()
            return row["count"] if row else 0

    def save_mapping(self, mapping_data: MessageMappingCreate) -> MessageMapping:
        """Сохранить маппинг между message_id в чате и user_id."""
        with self._db.transaction() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO message_mapping 
                (message_id, user_id, user_name, question_text)
                VALUES (?, ?, ?, ?)
            ''', (
                mapping_data.message_id,
                mapping_data.user_id,
                mapping_data.user_name,
                mapping_data.question_text
            ))

        # Получаем сохраненный маппинг
        result = self.get_mapping_by_message_id(mapping_data.message_id)
        if result is None:
            raise RuntimeError(f"Failed to retrieve saved mapping {mapping_data.message_id}")
        
        return result

    def get_mapping_by_message_id(self, message_id: str) -> Optional[MessageMapping]:
        """Получить маппинг по message_id из чата поддержки."""
        with self._db.cursor() as cursor:
            cursor.execute('''
                SELECT message_id, user_id, user_name, question_text, created_at
                FROM message_mapping
                WHERE message_id = ?
            ''', (message_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return MessageMapping(
                message_id=row["message_id"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                question_text=row["question_text"],
                created_at=datetime.fromisoformat(row["created_at"])
            )

    def _row_to_message(self, row) -> Message:
        """Преобразовать строку БД в объект Message."""
        return Message(
            id=row["id"],
            user_id=row["user_id"],
            text=row["text"],
            direction=MessageDirection(row["direction"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            operator_name=row["operator_name"]
        )
