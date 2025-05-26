from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Optional

from config import CATEGORIES, CHANNEL_ID, logger

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создание основной клавиатуры для пользователей
    
    Returns:
        ReplyKeyboardMarkup: Основная клавиатура
    """
    keyboard = [
        ["📝 Задати питання"],
        ["📋 Мої питання", "✉️ Мої відповіді"],
        ["❓ Допомога"],
        [f"📢 Канал з відповідями"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Создание клавиатуры главного меню для админов
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура для админов
    """
    keyboard = [
        ["📥 Нові питання", "⭐️ Важливі питання"],
        ["✅ Опрацьовані", "❌ Відхилені"],
        ["🔄 Змінити відповідь", "📊 Статистика"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_category_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры с категориями вопросов
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с категориями
    """
    keyboard = []
    
    # Создаем кнопки для каждой категории
    for cat_id, name in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"cat_{cat_id}")])
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard(question_id: str) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для администраторов для управления вопросом
    
    Args:
        question_id: ID вопроса
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для админов
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Відповісти", callback_data=f"answer_{question_id}"),
            InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{question_id}")
        ],
        [
            InlineKeyboardButton("⭐️ Важливе", callback_data=f"important_{question_id}"),
            InlineKeyboardButton("📌 Закріпити", callback_data=f"pin_{question_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_questions_list_keyboard(questions: List[dict], page: int = 0, items_per_page: int = 5) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры со списком вопросов с пагинацией
    
    Args:
        questions: Список вопросов
        page: Номер страницы (начиная с 0)
        items_per_page: Количество вопросов на странице
        
    Returns:
        InlineKeyboardMarkup: Клавиатура со списком вопросов
    """
    keyboard = []
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    
    # Добавляем кнопки с вопросами
    for q in questions[start_idx:end_idx]:
        # Добавляем статус к тексту вопроса
        status_emoji = {
            'pending': '⏳',
            'answered': '✅',
            'rejected': '❌'
        }.get(q['status'], '⏳')
        
        # Обрезаем текст вопроса до 30 символов
        short_text = q['text'][:30] + '...' if len(q['text']) > 30 else q['text']
        keyboard.append([InlineKeyboardButton(
            f"{status_emoji} {CATEGORIES[q['category']]}: {short_text}",
            callback_data=f"view_q_{q['id']}"
        )])
        
        # Если вопрос отклонен, добавляем кнопку восстановления
        if q['status'] == 'rejected':
            keyboard.append([InlineKeyboardButton(
                "↩️ Відновити",
                callback_data=f"restore_{q['id']}"
            )])
    
    # Добавляем навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    if end_idx < len(questions):
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Добавляем кнопку возврата в админское меню
    keyboard.append([InlineKeyboardButton("🔙 В меню админа", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_channel_button() -> InlineKeyboardMarkup:
    """
    Создание кнопки для перехода в канал с ответами
    
    Returns:
        InlineKeyboardMarkup: Кнопка для перехода в канал
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📢 Перейти в канал з відповідями",
            url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"
        )
    ]])

def get_back_button(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """
    Создание кнопки "Назад"
    
    Args:
        callback_data: Данные для callback_query
        
    Returns:
        InlineKeyboardMarkup: Кнопка "Назад"
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Назад", callback_data=callback_data)
    ]])

def get_question_view_keyboard(question_id: str, question: dict, current_page: int = 0) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для просмотра вопроса
    
    Args:
        question_id: ID вопроса
        question: Данные вопроса
        current_page: Текущая страница в списке вопросов
        
    Returns:
        InlineKeyboardMarkup: Клавиатура для просмотра вопроса
    """
    keyboard = []
    
    # Создаем кнопки в зависимости от статуса вопроса
    if question['status'] == 'pending':
        keyboard.append([
            InlineKeyboardButton("✅ Відповісти", callback_data=f"answer_{question_id}"),
            InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{question_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(
                "⭐️ Важливе" if not question.get('important') else "🔵 Звичайне",
                callback_data=f"important_{question_id}"
            )
        ])
    elif question['status'] == 'answered':
        keyboard.append([
            InlineKeyboardButton("🔄 Змінити відповідь", callback_data=f"edit_{question_id}"),
            InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{question_id}")
        ])
    
    # Добавляем кнопку возврата к списку
    keyboard.append([InlineKeyboardButton("🔙 До списку", callback_data=f"page_{current_page}")])
    
    return InlineKeyboardMarkup(keyboard)
