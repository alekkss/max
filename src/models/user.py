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
        phone_number: Номер телефона пользователя (опционально)
    """
    
    user_id: int
    name: str
    first_contact: datetime
    last_contact: datetime
    phone_number: Optional[str] = None
    
    def __repr__(self) -> str:
        """Удобное строковое представление для логирования."""
        phone_display = f", phone={self.phone_number}" if self.phone_number else ""
        return f"User(id={self.user_id}, name='{self.name}'{phone_display})"


@dataclass(frozen=True)
class UserCreate:
    """DTO для создания нового пользователя.
    
    Используется когда у нас еще нет временных меток из БД.
    
    Attributes:
        user_id: Уникальный идентификатор пользователя
        name: Имя пользователя
        phone_number: Номер телефона пользователя (опционально)
    """
    
    user_id: int
    name: str
    phone_number: Optional[str] = None


@dataclass(frozen=True)
class UserUpdate:
    """DTO для обновления данных пользователя.
    
    Attributes:
        user_id: Идентификатор пользователя для обновления
        name: Новое имя пользователя (если изменилось)
        phone_number: Номер телефона пользователя (опционально)
    """
    
    user_id: int
    name: str
    phone_number: Optional[str] = None
