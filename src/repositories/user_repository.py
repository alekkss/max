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
        
        Если пользователь существует - обновляет name, phone_number и last_contact.
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
    
    @abstractmethod
    def update_phone_number(self, user_id: int, phone_number: str) -> User:
        """Обновить номер телефона пользователя.
        
        Args:
            user_id: ID пользователя
            phone_number: Номер телефона
            
        Returns:
            Обновленный пользователь
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
            if user_data.phone_number is not None:
                # Если передан phone_number - обновляем его тоже
                cursor.execute('''
                    INSERT INTO users (user_id, name, phone_number, last_contact)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        name = excluded.name,
                        phone_number = excluded.phone_number,
                        last_contact = CURRENT_TIMESTAMP
                ''', (user_data.user_id, user_data.name, user_data.phone_number))
            else:
                # Если phone_number = None - НЕ обновляем его (сохраняем существующий)
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
                SELECT user_id, name, first_contact, last_contact, phone_number
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
                last_contact=datetime.fromisoformat(row["last_contact"]),
                phone_number=row["phone_number"]
            )
    
    def exists(self, user_id: int) -> bool:
        """Проверить существование пользователя."""
        with self._db.cursor() as cursor:
            cursor.execute(
                'SELECT 1 FROM users WHERE user_id = ? LIMIT 1',
                (user_id,)
            )
            return cursor.fetchone() is not None
    
    def update_phone_number(self, user_id: int, phone_number: str) -> User:
        """Обновить номер телефона пользователя."""
        with self._db.transaction() as cursor:
            cursor.execute('''
                UPDATE users 
                SET phone_number = ?, last_contact = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (phone_number, user_id))
        
        # Получаем обновленного пользователя
        result = self.get_by_id(user_id)
        if result is None:
            raise RuntimeError(f"User {user_id} not found after phone update")
        
        return result
