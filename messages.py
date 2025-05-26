from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import logger, CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY, CATEGORIES, ADMIN_IDS, CHANNEL_ID
from keyboards import get_main_keyboard, get_admin_menu_keyboard, get_category_keyboard, get_channel_button
from utils import is_admin, format_question_for_user, handle_admin_question, notify_user_about_answer, generate_help_text
from database import Database

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Обработчик всех текстовых сообщений
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        text = update.message.text
        is_admin_user = is_admin(user_id)

        logger.info(f"Получено сообщение от пользователя {user_id}: {text}")

        # Показываем основную клавиатуру только в приватном чате
        if update.effective_chat.type == 'private':
            # Обрабатываем текстовые команды от постоянной клавиатуры
            if text == "📝 Задати питання":
                await update.message.reply_text(
                    "📝 Оберіть категорію питання:",
                    reply_markup=get_category_keyboard(),
                    disable_notification=True
                )
                return TYPING_CATEGORY

            elif text == "📋 Мої питання":
                return await show_my_questions(update, context, db)

            elif text == "✉️ Мої відповіді":
                return await show_my_answers(update, context, db)

            elif text == "📢 Канал з відповідями":
                # Отправляем ссылку на канал
                await update.message.reply_text(
                    "Перейдіть в канал, щоб побачити всі відповіді:",
                    reply_markup=get_channel_button(),
                    disable_notification=True
                )
                return CHOOSING

            elif text == "❓ Допомога":
                help_text = generate_help_text()
                await update.message.reply_text(help_text, disable_notification=True)
                return CHOOSING

            # Проверяем, является ли пользователь администратором для админских команд
            elif text in ["📥 Нові питання", "⭐️ Важливі питання", "✅ Опрацьовані", "❌ Відхилені", "🔄 Змінити відповідь", "📊 Статистика"]:
                if not is_admin_user:
                    await update.message.reply_text(
                        "❌ У вас немає прав адміністратора",
                        reply_markup=get_main_keyboard(),
                        disable_notification=True
                    )
                    return CHOOSING
                return await handle_admin_menu(update, context, db)

            # Для всех остальных сообщений показываем обычную клавиатуру
            keyboard = get_admin_menu_keyboard() if is_admin_user else get_main_keyboard()
            await update.message.reply_text(
                "Оберіть опцію з меню:",
                reply_markup=keyboard,
                disable_notification=True
            )
            return CHOOSING

        # Продолжаем обработку обычных сообщений
        return await handle_regular_message(update, context, db)

    except Exception as e:
        logger.error(f"Загальна помилка в handle_message: {e}")
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Виникла помилка. Будь ласка, почніть спочатку з команди /start",
            disable_notification=True
        )
        return CHOOSING

async def handle_regular_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Обработка обычных текстовых сообщений
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        message_text = update.message.text

        logger.info(f"Отримано повідомлення від користувача {user_id}: {message_text}")
        logger.info(f"Поточний стан: {context.user_data}")

        # Обработка ответа на вопрос или редактирования ответа
        if (context.user_data.get('answering') or context.user_data.get('editing')) and is_admin(user_id):
            try:
                question_id = context.user_data.get('answering') or context.user_data.get('editing')
                answer_text = message_text
                question = db.get_question(question_id)
                is_editing = context.user_data.get('editing')

                # Публикуем ответ в канал
                message_text = (
                    f"❓ Питання ({CATEGORIES[question['category']]})"
                    f"\n\n{question['text']}\n\n"
                    f"✅ Відповідь від служителя:\n{answer_text}"
                )

                if is_editing:
                    # Если это редактирование, то обновляем существующее сообщение
                    try:
                        await context.bot.edit_message_text(
                            chat_id=CHANNEL_ID,
                            message_id=question.get('answer_message_id'),
                            text=message_text
                        )
                    except Exception as e:
                        logger.error(f"Помилка при оновленні повідомлення: {e}")
                        # Если не удалось отредактировать, отправляем новое
                        message = await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message_text + "\n\n🔄 (оновлена відповідь)",
                            disable_notification=True
                        )
                else:
                    # Отправляем новое сообщение
                    message = await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message_text,
                        disable_notification=True
                    )

                # Обновляем статус вопроса
                update_data = {
                    'status': 'answered',
                    'answer': answer_text,
                    'answer_time': datetime.now().isoformat()
                }
                
                if not is_editing:
                    update_data['answer_message_id'] = message.message_id
                
                db.update_question(question_id, update_data)

                # Уведомляем пользователя о ответе
                await notify_user_about_answer(context, db.get_question(question_id))

                # Очищаем состояние
                context.user_data.clear()

                success_message = "✅ Відповідь успішно оновлено" if is_editing else "✅ Відповідь опубліковано"
                await update.message.reply_text(
                    success_message,
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING

            except Exception as e:
                logger.error(f"Помилка при публікації відповіді: {e}")
                context.user_data.clear()
                await update.message.reply_text(
                    "❌ Виникла помилка при публікації відповіді. Будь ласка, спробуйте пізніше.",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING

        # Обработка нового вопроса
        elif context.user_data.get('category') and context.user_data.get('waiting_for_question'):
            try:
                category = context.user_data['category']

                # Генерируем уникальный ID для вопроса
                question_id = f"q{len(db.questions) + 1}"

                # Сохраняем вопрос в базе данных
                db.add_question(question_id, {
                    'id': question_id,
                    'category': category,
                    'text': message_text,
                    'status': 'pending',
                    'time': datetime.now().isoformat(),
                    'important': False,
                    'user_id': user_id
                })

                logger.info(f"Питання збережено з ID {question_id}")

                # Отправляем вопрос в группу администраторов
                await handle_admin_question(context, question_id, db)

                # Очищаем состояние
                context.user_data.clear()

                # Отправляем подтверждение пользователю
                await update.message.reply_text(
                    "✅ Ваше питання успішно надіслано!\n\n"
                    "• Адміністратори отримали його анонімно\n"
                    "• Відповідь з'явиться в каналі\n"
                    "• Ви можете задати ще одне питання",
                    reply_markup=get_main_keyboard(),
                    disable_notification=True
                )
                return CHOOSING

            except Exception as e:
                logger.error(f"Помилка при надсиланні питання: {e}")
                context.user_data.clear()
                await update.message.reply_text(
                    "❌ Виникла помилка при надсиланні питання. Будь ласка, спробуйте пізніше.",
                    reply_markup=get_main_keyboard(),
                    disable_notification=True
                )
                return CHOOSING

        else:
            # Показываем админское меню в группе админов
            if update.effective_chat.id == int(ADMIN_GROUP_ID) and is_admin(user_id):
                await update.message.reply_text(
                    "Оберіть дію з меню адміністратора:",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
            else:
                await update.message.reply_text(
                    "❗️ Будь ласка, використовуйте кнопки для взаємодії з ботом.\n"
                    "Натисніть /start щоб почати.",
                    reply_markup=get_main_keyboard(),
                    disable_notification=True
                )
            return CHOOSING

    except Exception as e:
        logger.error(f"Загальна помилка в handle_regular_message: {e}")
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Виникла помилка. Будь ласка, почніть спочатку з команди /start",
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

async def show_my_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Показать вопросы пользователя
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        user_questions = db.get_questions_by_user(user_id)

        if not user_questions:
            await update.message.reply_text(
                "📝 У вас поки немає питань.\n"
                "Натисніть кнопку «Задати питання», щоб задати перше питання!",
                reply_markup=get_main_keyboard(),
                disable_notification=True
            )
            return CHOOSING

        # Формируем текст со списком вопросов
        questions_text = "📋 Ваші питання:\n\n"
        for i, q in enumerate(user_questions, 1):
            status = {
                'pending': '⏳ Очікує відповіді',
                'answered': '✅ Відповідь отримано',
                'rejected': '❌ Відхилено'
            }.get(q['status'], '⏳ Очікує відповіді')

            questions_text += (
                f"{i}. {CATEGORIES[q['category']]}\n"
                f"Питання: {q['text']}\n"
                f"Статус: {status}\n\n"
            )

        await update.message.reply_text(
            questions_text,
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

    except Exception as e:
        logger.error(f"Помилка при показі питань користувача: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка при отриманні ваших питань. Спробуйте пізніше.",
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

async def show_my_answers(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Показать ответы на вопросы пользователя
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        answered_questions = [q for q in db.get_questions_by_user(user_id) if q.get('status') == 'answered']

        if not answered_questions:
            await update.message.reply_text(
                "📝 У вас поки немає відповідей на питання.\n"
                "Всі відповіді з'являться тут, як тільки адміністратори дадуть відповідь!",
                reply_markup=get_main_keyboard(),
                disable_notification=True
            )
            return CHOOSING

        # Формируем текст со списком ответов
        answers_text = "✉️ Відповіді на ваші питання:\n\n"
        for i, q in enumerate(answered_questions, 1):
            answers_text += (
                f"{i}. {CATEGORIES[q['category']]}\n"
                f"Питання: {q['text']}\n"
                f"Відповідь: {q['answer']}\n\n"
            )

        await update.message.reply_text(
            answers_text,
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

    except Exception as e:
        logger.error(f"Помилка при показі відповідей користувача: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка при отриманні відповідей. Спробуйте пізніше.",
            reply_markup=get_main_keyboard(),
            disable_notification=True
        )
        return CHOOSING

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Обработчик админского меню
    
    Args:
        update: Объект обновления
        context: Контекст бота
        db: Объект базы данных
        
    Returns:
        int: Следующее состояние разговора
    """
    try:
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            await update.message.reply_text(
                "❌ У вас нет прав администратора.",
                disable_notification=True
            )
            return CHOOSING
        
        # Получаем текст команды
        text = update.message.text
        
        if text == "📊 Статистика":
            # Получаем статистику
            stats = db.get_stats()
            stats_text = format_stats(stats)
            
            await update.message.reply_text(
                stats_text,
                reply_markup=get_admin_menu_keyboard(),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "📥 Нові питання":
            # Получаем список новых вопросов
            new_questions = db.get_questions_by_status('pending')
            if not new_questions:
                await update.message.reply_text(
                    "📭 Нових питань немає",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            # Сохраняем список вопросов в контексте
            contex
(Content truncated due to size limit. Use line ranges to read in chunks)