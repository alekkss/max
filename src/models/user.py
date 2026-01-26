"""Доменная модель пользователя."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class User:
    """Модель пользователя бота.
    
    Attributes:
        user_id: Уникальный идентификатор пользователя в системе Max.ru
        name: Имя пользователя
        first_contact: Дата и время первого контакта с ботом
        last_contact: Дата и время последнего контакта с ботом
    """
    
    user_id: int
    name: str
    first_contact: datetime
    last_contact: datetime
    
    def __repr__(self) -> str:
        """Удобное строковое представление для логирования."""
        return f"User(id={self.user_id}, name='{self.name}')"


@dataclass(frozen=True)
class UserCreate:
    """DTO для создания нового пользователя.
    
    Используется когда у нас еще нет временных меток из БД.
    
    Attributes:
        user_id: Уникальный идентификатор пользователя
        name: Имя пользователя
    """
    
    user_id: int
    name: str


@dataclass(frozen=True)
class UserUpdate:
    """DTO для обновления данных пользователя.
    
    Attributes:
        user_id: Идентификатор пользователя для обновления
        name: Новое имя пользователя (если изменилось)
    """
    
    user_id: int
    name: str
