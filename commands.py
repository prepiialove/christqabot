from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from typing import Dict, List, Optional, Tuple

from config import logger, CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY, ADMIN_IDS
from keyboards import get_main_keyboard, get_category_keyboard, get_admin_menu_keyboard
from utils import is_admin, format_question_for_user, generate_help_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start
    
    Args:
        update: Объект обновления
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user = update.effective_user
        logger.info(f"Користувач {user.id} запустив бота")

        # Показываем приветственное сообщение только в приватном чате
        if update.effective_chat.type == 'private':
            welcome_text = (
                f"👋 Вітаю, {user.first_name}!\n\n"
                "🤖 Це бот для анонімних питань.\n\n"
                "📝 Ви можете:\n"
                "• Задавати питання анонімно\n"
                "• Переглядати свої питання\n"
                "• Отримувати відповіді в каналі\n\n"
                "❗️ Всі питання повністю анонімні\n"
                "✅ Відповіді публікуються в каналі"
            )

            # Отправляем приветственное сообщение с основной клавиатурой
            await update.message.reply_text(
                welcome_text,
                reply_markup=get_main_keyboard(),
                disable_notification=True
            )

            # Импортируем здесь, чтобы избежать циклических импортов
            from keyboards import get_channel_button
            
            # Отправляем отдельное сообщение с кнопкой канала
            await update.message.reply_text(
                "Натисніть кнопку нижче, щоб перейти в канал з відповідями:",
                reply_markup=get_channel_button(),
                disable_notification=True
            )

        return CHOOSING

    except Exception as e:
        logger.error(f"Помилка в команді start: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка при запуску бота. Спробуйте пізніше.",
            disable_notification=True
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /cancel
    
    Args:
        update: Объект обновления
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Дію скасовано.\nОберіть нову дію:",
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

    except Exception as e:
        logger.error(f"Помилка в команді cancel: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте пізніше.",
            disable_notification=True
        )
        return CHOOSING

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /help
    
    Args:
        update: Объект обновления
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        help_text = generate_help_text()
        await update.message.reply_text(
            help_text,
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING
    except Exception as e:
        logger.error(f"Помилка в команді help: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте пізніше.",
            disable_notification=True
        )
        return CHOOSING

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /admin
    
    Args:
        update: Объект обновления
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            await update.message.reply_text(
                "❌ У вас немає прав адміністратора.",
                reply_markup=get_main_keyboard(),
                disable_notification=True
            )
            return CHOOSING
        
        await update.message.reply_text(
            "👑 Панель адміністратора\n\nОберіть дію:",
            reply_markup=get_admin_menu_keyboard(),
            disable_notification=True
        )
        return CHOOSING
    except Exception as e:
        logger.error(f"Помилка в команді admin: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте пізніше.",
            disable_notification=True
        )
        return CHOOSING
