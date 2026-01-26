"""Модели событий от Max.ru API."""

from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum


class UpdateType(str, Enum):
    """Типы событий от API."""
    
    MESSAGE_CREATED = "message_created"
    BOT_STARTED = "bot_started"


class LinkType(str, Enum):
    """Типы связей сообщений."""
    
    REPLY = "reply"
    FORWARD = "forward"


@dataclass(frozen=True)
class Sender:
    """Отправитель сообщения.
    
    Attributes:
        user_id: ID отправителя
        name: Полное имя
        first_name: Имя
        is_bot: Является ли отправитель ботом
    """
    
    user_id: int
    name: Optional[str] = None
    first_name: Optional[str] = None
    is_bot: bool = False


@dataclass(frozen=True)
class Recipient:
    """Получатель сообщения.
    
    Attributes:
        chat_id: ID группового чата (если есть)
        user_id: ID пользователя (если личное сообщение)
    """
    
    chat_id: Optional[int] = None
    user_id: Optional[int] = None


@dataclass(frozen=True)
class MessageBody:
    """Тело сообщения.
    
    Attributes:
        text: Текст сообщения
        mid: Message ID в системе Max.ru
    """
    
    text: str
    mid: Optional[str] = None


@dataclass(frozen=True)
class LinkedMessage:
    """Сообщение, на которое ссылаются (reply/forward).
    
    Attributes:
        mid: Message ID связанного сообщения
    """
    
    mid: str


@dataclass(frozen=True)
class MessageLink:
    """Связь сообщения с другим сообщением.
    
    Attributes:
        type: Тип связи (reply, forward)
        message: Связанное сообщение
    """
    
    type: LinkType
    message: LinkedMessage


@dataclass(frozen=True)
class Message:
    """Модель сообщения от API.
    
    Attributes:
        body: Тело сообщения (текст и mid)
        sender: Отправитель
        recipient: Получатель
        link: Связь с другим сообщением (опционально)
    """
    
    body: MessageBody
    sender: Sender
    recipient: Recipient
    link: Optional[MessageLink] = None


@dataclass(frozen=True)
class MessageCreatedUpdate:
    """Событие создания нового сообщения.
    
    Attributes:
        update_type: Тип события (всегда MESSAGE_CREATED)
        message: Данные сообщения
    """
    
    update_type: Literal[UpdateType.MESSAGE_CREATED]
    message: Message


@dataclass(frozen=True)
class User:
    """Пользователь для события bot_started.
    
    Attributes:
        user_id: ID пользователя
        name: Полное имя
        first_name: Имя
    """
    
    user_id: int
    name: Optional[str] = None
    first_name: Optional[str] = None


@dataclass(frozen=True)
class BotStartedUpdate:
    """Событие запуска бота пользователем.
    
    Attributes:
        update_type: Тип события (всегда BOT_STARTED)
        user: Данные пользователя
    """
    
    update_type: Literal[UpdateType.BOT_STARTED]
    user: User


# Union type для всех возможных типов событий
Update = MessageCreatedUpdate | BotStartedUpdate
