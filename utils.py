import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import logger, ADMIN_IDS, ADMIN_GROUP_ID, CHANNEL_ID, CATEGORIES
from database import Database

async def handle_admin_question(context, question_id: str, db: Database) -> bool:
    """
    Отправка вопроса администраторам
    
    Args:
        context: Контекст бота
        question_id: ID вопроса
        db: Объект базы данных
        
    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        question = db.get_question(question_id)
        if not question:
            logger.error(f"Вопрос {question_id} не найден в базе данных")
            return False
            
        message_text = (
            f"📨 Нове анонімне питання\n\n"
            f"Категорія: {CATEGORIES[question['category']]}\n"
            f"Питання: {question['text']}"
        )

        # Импортируем здесь, чтобы избежать циклических импортов
        from keyboards import get_admin_keyboard

        # Отправляем сообщение в группу админов
        admin_message = await context.bot.send_message(
            chat_id=int(ADMIN_GROUP_ID),
            text=message_text,
            reply_markup=get_admin_keyboard(question_id),
            disable_notification=True
        )

        logger.info(f"Питання {question_id} надіслано адмінам")
        return True
    except Exception as e:
        logger.error(f"Помилка при надсиланні питання адмінам: {e}")
        return False

def is_admin(user_id: int) -> bool:
    """
    Проверка, является ли пользователь администратором
    
    Args:
        user_id: ID пользователя
        
    Returns:
        bool: True если пользователь админ, иначе False
    """
    return user_id in ADMIN_IDS

def format_question_for_user(question: dict) -> str:
    """
    Форматирование вопроса для отображения пользователю
    
    Args:
        question: Данные вопроса
        
    Returns:
        str: Отформатированный текст вопроса
    """
    status = {
        'pending': '⏳ Очікує відповіді',
        'answered': '✅ Відповідь отримано',
        'rejected': '❌ Відхилено'
    }.get(question['status'], '⏳ Очікує відповіді')
    
    text = (
        f"Категорія: {CATEGORIES[question['category']]}\n"
        f"Питання: {question['text']}\n"
        f"Статус: {status}"
    )
    
    if question.get('answer') and question['status'] == 'answered':
        text += f"\n\nВідповідь: {question['answer']}"
    
    return text

def format_question_for_admin(question: dict) -> str:
    """
    Форматирование вопроса для отображения администратору
    
    Args:
        question: Данные вопроса
        
    Returns:
        str: Отформатированный текст вопроса
    """
    status_emoji = {
        'pending': '⏳',
        'answered': '✅',
        'rejected': '❌'
    }.get(question['status'], '⏳')
    
    important_emoji = "⭐️" if question.get('important', False) else ""
    
    text = (
        f"📨 Питання {status_emoji} {important_emoji}\n\n"
        f"ID: {question['id']}\n"
        f"Категорія: {CATEGORIES[question['category']]}\n"
        f"Питання: {question['text']}\n"
        f"Час: {format_datetime(question['time'])}"
    )
    
    if question.get('answer'):
        text += f"\n\n✍️ Відповідь:\n{question['answer']}"
        if question.get('answer_time'):
            text += f"\n\nЧас відповіді: {format_datetime(question['answer_time'])}"
    
    return text

def format_datetime(iso_date: str) -> str:
    """
    Форматирование даты и времени из ISO формата в читаемый вид
    
    Args:
        iso_date: Дата в ISO формате
        
    Returns:
        str: Отформатированная дата и время
    """
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception as e:
        logger.error(f"Ошибка при форматировании даты {iso_date}: {e}")
        return iso_date

def format_stats(stats: dict) -> str:
    """
    Форматирование статистики для отображения
    
    Args:
        stats: Данные статистики
        
    Returns:
        str: Отформатированная статистика
    """
    total = stats['total_questions']
    answered = stats['answered_questions']
    pending = total - answered
    
    text = (
        "📊 Статистика бота:\n\n"
        f"📝 Всього питань: {total}\n"
        f"✅ Відповіді надано: {answered}\n"
        f"⏳ Очікують відповіді: {pending}\n\n"
        "📊 По категоріях:\n"
    )
    
    for cat_id, cat_name in CATEGORIES.items():
        count = stats['categories'].get(cat_id, 0)
        percentage = (count / total * 100) if total > 0 else 0
        text += f"{cat_name}: {count} ({percentage:.1f}%)\n"
    
    if answered > 0:
        efficiency = (answered / total * 100)
        text += f"\n📈 Ефективність роботи: {efficiency:.1f}%"
    
    return text

async def notify_user_about_answer(context, question: dict) -> bool:
    """
    Уведомление пользователя о том, что на его вопрос ответили
    
    Args:
        context: Контекст бота
        question: Данные вопроса
        
    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        user_id = question.get('user_id')
        if not user_id:
            logger.warning(f"Не удалось отправить уведомление: отсутствует user_id в вопросе {question['id']}")
            return False
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from keyboards import get_channel_button
        
        message_text = (
            f"✅ На ваше питання надано відповідь!\n\n"
            f"Категорія: {CATEGORIES[question['category']]}\n"
            f"Питання: {question['text']}\n\n"
            f"Відповідь: {question.get('answer', '')}\n\n"
            f"Ви можете переглянути всі відповіді в каналі:"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=get_channel_button(),
            disable_notification=False  # Важное уведомление, поэтому с оповещением
        )
        
        logger.info(f"Уведомление о ответе на вопрос {question['id']} отправлено пользователю {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {question.get('user_id')}: {e}")
        return False

def generate_help_text() -> str:
    """
    Генерация текста справки
    
    Returns:
        str: Текст справки
    """
    return (
        "📌 Як користуватися ботом:\n\n"
        "1️⃣ Задати питання:\n"
        "   • Натисніть '📝 Задати питання'\n"
        "   • Оберіть категорію\n"
        "   • Напишіть своє питання\n\n"
        "2️⃣ Отримання відповіді:\n"
        "   • Ваше питання отримають адміністратори\n"
        "   • При публікації відповіді вона з'явиться в каналі\n"
        "   • Ви отримаєте повідомлення про відповідь\n"
        "   • Перейти в канал можна по кнопці '📢 Канал з відповідями'\n\n"
        "3️⃣ Категорії питань:\n"
        "   🌟 Загальні - будь-які питання\n"
        "   🙏 Духовні - питання віри\n"
        "   👤 Особисті - особисті питання\n"
        "   ⚡️ Термінові - термінові питання\n\n"
        "❗️ Важливо:\n"
        "• Всі питання повністю анонімні\n"
        "• Адміністратори бачать тільки текст питання\n"
        "• В каналі публікуються тільки питання та відповідь"
    )
