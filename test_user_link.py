"""Тест различных форматов ссылок на пользователя в MAX."""

import requests
import time
from src.config.settings import Settings


def test_user_link_formats():
    """Тестирует разные форматы ссылок на пользователя согласно документации MAX API."""
    
    # Загружаем настройки
    settings = Settings()
    
    # Данные для теста
    test_user_id = 2808020
    test_user_name = "VG"  # ⚠️ ВАЖНО: Здесь должно быть ПОЛНОЕ ИМЯ из профиля (Имя Фамилия)
    # Если у пользователя есть фамилия, укажите её: "Владимир Горбунов"
    # Если фамилии нет - только имя
    
    # API клиент
    session = requests.Session()
    session.headers.update(settings.api_headers)
    base_url = settings.base_url
    chat_id = settings.support_chat_id
    
    # Список тестов - ТОЛЬКО правильные форматы согласно документации
    tests = [
        {
            "name": "✅ Markdown (правильный формат max://user/)",
            "text": f"[{test_user_name}](max://user/{test_user_id}) - это правильная ссылка!",
            "format": "markdown",
            "is_correct": True
        },
        {
            "name": "✅ HTML (правильный формат max://user/)",
            "text": f'<a href="max://user/{test_user_id}">{test_user_name}</a> - это правильная ссылка!',
            "format": "html",
            "is_correct": True
        },
        {
            "name": "✅ Markdown с эмодзи",
            "text": f"👤 [{test_user_name}](max://user/{test_user_id}), проверьте сообщение!",
            "format": "markdown",
            "is_correct": True
        },
        {
            "name": "✅ HTML с эмодзи",
            "text": f'👤 <a href="max://user/{test_user_id}">{test_user_name}</a>, проверьте сообщение!',
            "format": "html",
            "is_correct": True
        },
        {
            "name": "✅ Markdown с дополнительным форматированием",
            "text": f"**Важно!** [{test_user_name}](max://user/{test_user_id}), _срочное_ сообщение",
            "format": "markdown",
            "is_correct": True
        },
        {
            "name": "✅ HTML с дополнительным форматированием",
            "text": f'<b>Важно!</b> <a href="max://user/{test_user_id}">{test_user_name}</a>, <i>срочное</i> сообщение',
            "format": "html",
            "is_correct": True
        },
        {
            "name": "❌ Неправильно: max:user: (для сравнения)",
            "text": f"[{test_user_name}](max:user:{test_user_id}) - неправильный формат",
            "format": "markdown",
            "is_correct": False
        },
        {
            "name": "❌ Неправильно: https://max.ru/im (для сравнения)",
            "text": f"[{test_user_name}](https://max.ru/im?sel={test_user_id}) - обычная веб-ссылка",
            "format": "markdown",
            "is_correct": False
        },
        {
            "name": "❌ Без форматирования (для сравнения)",
            "text": f"{test_user_name} (ID: {test_user_id}) - просто текст",
            "format": None,
            "is_correct": False
        }
    ]
    
    print(f"\n🧪 Тестирование ссылок на пользователя MAX API")
    print(f"📚 Согласно официальной документации MAX")
    print(f"{'='*70}\n")
    print(f"⚠️  ВАЖНО: В коде используйте ПОЛНОЕ ИМЯ пользователя из профиля!")
    print(f"    Формат: 'Имя Фамилия' (если фамилии нет - только 'Имя')")
    print(f"\n👤 Тестовый пользователь: {test_user_name} (ID: {test_user_id})")
    print(f"📨 Чат поддержки: {chat_id}")
    print(f"{'='*70}\n")
    
    correct_tests = [t for t in tests if t['is_correct']]
    incorrect_tests = [t for t in tests if not t['is_correct']]
    
    # Сначала отправляем правильные форматы
    print("✅ ПРАВИЛЬНЫЕ ФОРМАТЫ (согласно документации):\n")
    for i, test in enumerate(correct_tests, 1):
        print(f"Тест {i}/{len(correct_tests)}: {test['name']}")
        send_test_message(session, base_url, chat_id, test)
        if i < len(correct_tests):
            time.sleep(1)
    
    print(f"\n{'='*70}\n")
    
    # Затем неправильные для сравнения
    print("❌ НЕПРАВИЛЬНЫЕ ФОРМАТЫ (для сравнения):\n")
    for i, test in enumerate(incorrect_tests, 1):
        print(f"Тест {i}/{len(incorrect_tests)}: {test['name']}")
        send_test_message(session, base_url, chat_id, test)
        if i < len(incorrect_tests):
            time.sleep(1)
    
    print(f"\n{'='*70}")
    print(f"✅ Тестирование завершено!\n")
    print(f"📱 Проверьте чат поддержки:")
    print(f"   1. Первые 6 сообщений должны содержать КЛИКАБЕЛЬНЫЕ ссылки")
    print(f"   2. При клике должен открыться профиль/диалог с пользователем")
    print(f"   3. Последние 3 сообщения - примеры неправильных форматов\n")
    print(f"🔑 Правильный формат: max://user/USER_ID")
    print(f"📝 Форматы: markdown или html\n")


def send_test_message(session, base_url, chat_id, test):
    """Отправляет тестовое сообщение."""
    try:
        # Подготовка payload
        payload = {"text": test["text"]}
        if test["format"]:
            payload["format"] = test["format"]
        
        # Отправка сообщения
        response = session.post(
            f"{base_url}/messages",
            params={"chat_id": chat_id},
            json=payload,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Отправлено успешно")
            print(f"  📝 Текст: {test['text'][:80]}...")
            print(f"  🎨 Формат: {test['format'] or 'plain'}")
        else:
            print(f"  ❌ Ошибка: {response.status_code}")
            print(f"  📄 Ответ: {response.text[:200]}")
        
    except Exception as e:
        print(f"  ❌ Исключение: {e}")
    
    print()


if __name__ == "__main__":
    test_user_link_formats()
