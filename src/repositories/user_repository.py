"""Репозиторий для работы с пользователями."""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from src.models.user import User, UserCreate, UserUpdate
from src.database.connection import DatabaseConnection


class IUserRepository(ABC):
    """Интерфейс репозитория пользователей.
    
    Определяет контракт для всех реализаций хранилища пользователей.
    """
    
    @abstractmethod
    def save(self, user_data: UserCreate | UserUpdate) -> User:
        """Сохранить или обновить пользователя.
        
        Если пользователь существует - обновляет name и last_contact.
        Если не существует - создает нового.
        
        Args:
            user_data: Данные для создания/обновления
            
        Returns:
            Сохраненный пользователь с актуальными данными из БД
        """
        pass
    
    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID.
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            User если найден, None если не существует
        """
        pass
    
    @abstractmethod
    def exists(self, user_id: int) -> bool:
        """Проверить существование пользователя.
        
        Args:
            user_id: Идентификатор пользователя
            
        Returns:
            True если пользователь существует
        """
        pass


class SQLiteUserRepository(IUserRepository):
    """Реализация репозитория пользователей для SQLite."""
    
    def __init__(self, db: DatabaseConnection) -> None:
        """Инициализация репозитория.
        
        Args:
            db: Подключение к базе данных
        """
        self._db = db
    
    def save(self, user_data: UserCreate | UserUpdate) -> User:
        """Сохранить или обновить пользователя."""
        with self._db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO users (user_id, name, last_contact)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    name = excluded.name,
                    last_contact = CURRENT_TIMESTAMP
            ''', (user_data.user_id, user_data.name))
        
        # Получаем актуальные данные из БД
        result = self.get_by_id(user_data.user_id)
        if result is None:
            raise RuntimeError(f"Failed to retrieve saved user {user_data.user_id}")
        
        return result
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        with self._db.cursor() as cursor:
            cursor.execute('''
                SELECT user_id, name, first_contact, last_contact
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            if row is None:
                return None
            
            return User(
                user_id=row["user_id"],
                name=row["name"],
                first_contact=datetime.fromisoformat(row["first_contact"]),
                last_contact=datetime.fromisoformat(row["last_contact"])
            )
    
    def exists(self, user_id: int) -> bool:
        """Проверить существование пользователя."""
        with self._db.cursor() as cursor:
            cursor.execute(
                'SELECT 1 FROM users WHERE user_id = ? LIMIT 1',
                (user_id,)
            )
            return cursor.fetchone() is not None
