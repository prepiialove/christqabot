from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import logger, CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY, CATEGORIES, ADMIN_IDS, CHANNEL_ID
from keyboards import (
    get_main_keyboard, get_admin_menu_keyboard, get_category_keyboard, 
    get_questions_list_keyboard, get_question_view_keyboard, get_back_button
)
from utils import is_admin, format_question_for_admin, handle_admin_question, notify_user_about_answer, format_stats
from database import Database

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Обработчик нажатий на кнопки
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        logger.info(f"Получен callback_query: {data} от пользователя {user_id}")

        # Отвечаем на callback_query
        await query.answer()

        if data == "back_to_main":
            await query.message.edit_text(
                "Оберіть дію:",
                reply_markup=get_main_keyboard()
            )
            context.user_data.clear()
            return CHOOSING

        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            context.user_data['category'] = category
            context.user_data['waiting_for_question'] = True

            await query.message.edit_text(
                f"📝 Ви обрали категорію: {CATEGORIES[category]}\n\n"
                "Напишіть ваше питання одним повідомленням.\n"
                "❗️ Питання буде надіслано анонімно."
            )
            return TYPING_QUESTION

        # Проверяем, является ли пользователь администратором для админских функций
        if not is_admin(user_id) and any(data.startswith(prefix) for prefix in ['view_q_', 'answer_', 'reject_', 'important_', 'edit_']):
            await query.message.reply_text(
                "❌ У вас немає прав для виконання цієї дії.",
                disable_notification=True
            )
            return CHOOSING

        if data == "admin_menu":
            await query.message.edit_text(
                "Оберіть дію з меню адміністратора:",
                reply_markup=get_admin_menu_keyboard()
            )
            context.user_data.clear()
            return CHOOSING

        elif data.startswith("page_"):
            page = int(data.replace("page_", ""))
            questions = context.user_data.get('current_questions', [])
            context.user_data['current_page'] = page
            
            await query.message.edit_text(
                "Оберіть питання:",
                reply_markup=get_questions_list_keyboard(questions, page)
            )
            return CHOOSING

        elif data.startswith("view_q_"):
            question_id = data.replace("view_q_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            # Формируем текст сообщения
            message_text = format_question_for_admin(question)

            # Создаем клавиатуру действий для вопроса
            keyboard = get_question_view_keyboard(
                question_id, 
                question, 
                context.user_data.get('current_page', 0)
            )

            await query.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            return CHOOSING

        elif data.startswith("answer_"):
            question_id = data.replace("answer_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            context.user_data['answering'] = question_id

            await query.message.edit_text(
                f"✍️ Відповідь на питання:\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"Напишіть вашу відповідь одним повідомленням:",
                reply_markup=get_back_button(f"view_q_{question_id}")
            )
            return TYPING_REPLY

        elif data.startswith("edit_"):
            question_id = data.replace("edit_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            context.user_data['editing'] = question_id

            await query.message.edit_text(
                f"🔄 Зміна відповіді:\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"Поточна відповідь:\n{question.get('answer', '')}\n\n"
                f"Напишіть нову відповідь одним повідомленням:",
                reply_markup=get_back_button(f"view_q_{question_id}")
            )
            return TYPING_REPLY

        elif data.startswith("reject_"):
            question_id = data.replace("reject_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            db.update_question(question_id, {'status': 'rejected'})
            question = db.get_question(question_id)

            keyboard = [[
                InlineKeyboardButton("↩️ Відновити", callback_data=f"restore_{question_id}"),
                InlineKeyboardButton("🔙 До списку", callback_data=f"page_{context.user_data.get('current_page', 0)}")
            ]]

            await query.message.edit_text(
                f"📨 Питання\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"❌ Питання відхилено",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING

        elif data.startswith("restore_"):
            question_id = data.replace("restore_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            db.update_question(question_id, {'status': 'pending'})
            question = db.get_question(question_id)

            # Импортируем здесь, чтобы избежать циклических импортов
            from keyboards import get_admin_keyboard

            await query.message.edit_text(
                f"📨 Питання\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"✅ Питання відновлено",
                reply_markup=get_admin_keyboard(question_id)
            )
            return CHOOSING

        elif data.startswith("important_"):
            question_id = data.replace("important_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            is_important = not question.get('important', False)
            db.update_question(question_id, {'important': is_important})
            question = db.get_question(question_id)

            # Обновляем сообщение с новыми кнопками
            keyboard = []
            if question['status'] == 'pending':
                keyboard.append([
                    InlineKeyboardButton("✅ Відповісти", callback_data=f"answer_{question_id}"),
                    InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{question_id}")
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "🔵 Зробити звичайним" if is_important else "⭐️ Зробити важливим",
                        callback_data=f"important_{question_id}"
                    ),
                    InlineKeyboardButton("📌 Закріпити", callback_data=f"pin_{question_id}")
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 До списку", callback_data=f"page_{context.user_data.get('current_page', 0)}")])

            status_emoji = "⭐️" if is_important else "🔵"
            await query.message.edit_text(
                f"📨 Питання {status_emoji}\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"{'⭐️ Позначено як важливе' if is_important else '🔵 Позначено як звичайне'}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING

        elif data.startswith("pin_"):
            question_id = data.replace("pin_", "")
            question = db.get_question(question_id)
            
            if not question:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            try:
                # Закрепляем сообщение в группе админов
                await context.bot.pin_chat_message(
                    chat_id=int(ADMIN_GROUP_ID),
                    message_id=query.message.message_id,
                    disable_notification=True
                )
                await query.answer("📌 Повідомлення закріплено!")
            except Exception as e:
                logger.error(f"Помилка при закріпленні повідомлення: {e}")
                await query.answer("❌ Помилка при закріпленні повідомлення")
            return CHOOSING

        elif data == "stats":
            stats = db.get_stats()
            stats_text = format_stats(stats)

            await query.message.edit_text(
                stats_text,
                reply_markup=get_back_button("admin_menu")
            )
            return CHOOSING

        else:
            logger.warning(f"Неизвестный callback_data: {data}")
            return CHOOSING

    except Exception as e:
        logger.error(f"Помилка в обробці кнопки: {e}")
        try:
            await query.message.edit_text(
                "❌ Виникла помилка. Будь ласка, почніть спочатку з команди /start"
            )
        except:
            await update.effective_message.reply_text(
                "❌ Виникла помилка. Будь ласка, почніть спочатку з команди /start"
            )
        return CHOOSING
