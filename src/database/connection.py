"""Управление подключением к базе данных. ававваа"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional
from pathlib import Path


class DatabaseConnection:
    """Менеджер подключения к SQLite базе данных.
    
    Отвечает за:
    - Создание и управление соединением с БД
    - Инициализацию схемы таблиц
    - Предоставление контекстных менеджеров для транзакций
    """
    
    def __init__(self, database_path: str) -> None:
        """Инициализация менеджера БД.
        
        Args:
            database_path: Путь к файлу SQLite базы данных
        """
        self._database_path = database_path
        self._connection: Optional[sqlite3.Connection] = None
    
    def connect(self) -> None:
        """Создать соединение с базой данных."""
        if self._connection is not None:
            return
        
        db_path = Path(self._database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
    
    def close(self) -> None:
        """Закрыть соединение с базой данных."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
    
    def initialize_schema(self) -> None:
        """Создать таблицы базы данных, если они не существуют."""
        if self._connection is None:
            raise RuntimeError("Database connection is not established")
        
        cursor = self._connection.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                first_contact TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_contact TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                direction TEXT NOT NULL,
                operator_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица маппинга сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_mapping (
                message_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self._connection.commit()
    
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Контекстный менеджер для выполнения транзакций.
        
        Автоматически выполняет commit при успехе или rollback при ошибке.
        
        Yields:
            Cursor для выполнения SQL-запросов
            
        Example:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO users ...")
        """
        if self._connection is None:
            raise RuntimeError("Database connection is not established")
        
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()
    
    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        """Контекстный менеджер для выполнения readonly запросов.
        
        Yields:
            Cursor для выполнения SQL-запросов
        """
        if self._connection is None:
            raise RuntimeError("Database connection is not established")
        
        cursor = self._connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def __enter__(self) -> "DatabaseConnection":
        """Поддержка контекстного менеджера."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Автоматическое закрытие соединения при выходе из контекста."""
        self.close()
