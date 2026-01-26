"""Доменные модели сообщений."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class MessageDirection(str, Enum):
    """Направление сообщения."""
    
    FROM_USER = "from_user"  # От клиента к боту
    TO_USER = "to_user"      # От оператора к клиенту


@dataclass(frozen=True)
class Message:
    """Модель сообщения в истории переписки.
    
    Attributes:
        id: Уникальный идентификатор сообщения в БД
        user_id: ID пользователя, связанного с сообщением
        text: Текст сообщения
        direction: Направление сообщения (от/к пользователю)
        operator_name: Имя оператора (если сообщение от оператора)
        timestamp: Дата и время отправки сообщения
    """
    
    id: int
    user_id: int
    text: str
    direction: MessageDirection
    timestamp: datetime
    operator_name: Optional[str] = None
    
    def __repr__(self) -> str:
        """Удобное строковое представление для логирования."""
        direction_arrow = "←" if self.direction == MessageDirection.FROM_USER else "→"
        text_preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"Message({direction_arrow} user_id={self.user_id}, text='{text_preview}')"


@dataclass(frozen=True)
class MessageCreate:
    """DTO для создания нового сообщения.
    
    Attributes:
        user_id: ID пользователя
        text: Текст сообщения
        direction: Направление сообщения
        operator_name: Имя оператора (опционально)
    """
    
    user_id: int
    text: str
    direction: MessageDirection
    operator_name: Optional[str] = None


@dataclass(frozen=True)
class MessageMapping:
    """Модель маппинга между message_id в чате поддержки и user_id клиента.
    
    Позволяет операторам отвечать через Reply, и бот понимает, какому клиенту
    переслать ответ.
    
    Attributes:
        message_id: ID сообщения в групповом чате поддержки
        user_id: ID пользователя-клиента
        user_name: Имя пользователя для удобства
        created_at: Дата создания маппинга
    """
    
    message_id: str
    user_id: int
    user_name: str
    created_at: datetime
    
    def __repr__(self) -> str:
        """Удобное строковое представление для логирования."""
        return f"MessageMapping(msg_id={self.message_id}, user={self.user_name})"


@dataclass(frozen=True)
class MessageMappingCreate:
    """DTO для создания маппинга сообщений.
    
    Attributes:
        message_id: ID сообщения в чате поддержки
        user_id: ID клиента
        user_name: Имя клиента
    """
    
    message_id: str
    user_id: int
    user_name: str
