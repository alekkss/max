"""Менеджер состояний для админ-панели."""

from typing import Optional
from enum import Enum
from dataclasses import dataclass


class AdminState(str, Enum):
    """Возможные состояния администратора."""
    
    IDLE = "idle"  # Обычное состояние
    WAITING_NOTIFICATION_TEXT = "waiting_notification_text"  # Ожидание текста уведомления
    CONFIRMING_NOTIFICATION = "confirming_notification"  # Подтверждение отправки


@dataclass
class AdminContext:
    """Контекст состояния администратора.
    
    Хранит текущее состояние и временные данные
    (например, текст уведомления для подтверждения).
    """
    
    state: AdminState
    notification_text: Optional[str] = None


class AdminStateManager:
    """Менеджер состояний администраторов.
    
    Отвечает за:
    - Отслеживание текущего состояния каждого админа
    - Сохранение временных данных (текст уведомления)
    - Переходы между состояниями
    
    Использует паттерн Singleton для единого источника состояний.
    """
    
    _instance: Optional['AdminStateManager'] = None
    
    def __new__(cls) -> 'AdminStateManager':
        """Реализация паттерна Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._states = {}
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация менеджера."""
        # Словарь состояний: user_id -> AdminContext
        if not hasattr(self, '_states'):
            self._states: dict[int, AdminContext] = {}
    
    def get_state(self, user_id: int) -> AdminState:
        """Получить текущее состояние администратора.
        
        Args:
            user_id: ID администратора
            
        Returns:
            Текущее состояние (по умолчанию IDLE)
        """
        context = self._states.get(user_id)
        return context.state if context else AdminState.IDLE
    
    def set_state(self, user_id: int, state: AdminState) -> None:
        """Установить состояние администратора.
        
        Args:
            user_id: ID администратора
            state: Новое состояние
        """
        if user_id not in self._states:
            self._states[user_id] = AdminContext(state=state)
        else:
            self._states[user_id].state = state
    
    def reset_state(self, user_id: int) -> None:
        """Сбросить состояние администратора в IDLE.
        
        Args:
            user_id: ID администратора
        """
        if user_id in self._states:
            del self._states[user_id]
    
    def save_notification_text(self, user_id: int, text: str) -> None:
        """Сохранить текст уведомления для подтверждения.
        
        Args:
            user_id: ID администратора
            text: Текст уведомления
        """
        if user_id not in self._states:
            self._states[user_id] = AdminContext(
                state=AdminState.CONFIRMING_NOTIFICATION,
                notification_text=text
            )
        else:
            self._states[user_id].notification_text = text
            self._states[user_id].state = AdminState.CONFIRMING_NOTIFICATION
    
    def get_notification_text(self, user_id: int) -> Optional[str]:
        """Получить сохранённый текст уведомления.
        
        Args:
            user_id: ID администратора
            
        Returns:
            Текст уведомления или None
        """
        context = self._states.get(user_id)
        return context.notification_text if context else None
    
    def is_waiting_notification_text(self, user_id: int) -> bool:
        """Проверить, ожидает ли админ ввода текста уведомления.
        
        Args:
            user_id: ID администратора
            
        Returns:
            True, если админ в состоянии ожидания текста
        """
        return self.get_state(user_id) == AdminState.WAITING_NOTIFICATION_TEXT
    
    def is_confirming_notification(self, user_id: int) -> bool:
        """Проверить, находится ли админ в состоянии подтверждения.
        
        Args:
            user_id: ID администратора
            
        Returns:
            True, если админ подтверждает отправку уведомления
        """
        return self.get_state(user_id) == AdminState.CONFIRMING_NOTIFICATION