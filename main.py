import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from dotenv import load_dotenv
from typing import Dict, List

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY = range(4)

# Получение токена бота из переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')  # Публичный канал для ответов
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')  # Приватная группа для админов
ADMIN_IDS = [int(id_) for id_ in os.getenv('ADMIN_IDS', '').split(',') if id_]
BOT_MODE = os.getenv('BOT_MODE', 'polling')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

# Категории вопросов
CATEGORIES: Dict[str, str] = {
    'general': '🌟 Загальні',
    'spiritual': '🙏 Духовні',
    'personal': '👤 Особисті',
    'urgent': '⚡️ Термінові'
}

class Database:
    def __init__(self, filename='db.json'):
        self.filename = filename
        self.questions = {}
        self.stats = {
            'total_questions': 0,
            'answered_questions': 0,
            'categories': {}
        }
        self.load()

    def load(self):
        """Загрузка базы данных из файла"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.questions = data.get('questions', {})
                    self.stats = data.get('stats', {
                        'total_questions': 0,
                        'answered_questions': 0,
                        'categories': {}
                    })
        except Exception as e:
            logger.error(f"Помилка при завантаженні бази даних: {e}")

    def save(self):
        """Сохранение базы данных в файл"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'questions': self.questions,
                    'stats': self.stats
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Помилка при збереженні бази даних: {e}")

    def add_question(self, question_id: str, question_data: dict):
        """Добавление нового вопроса"""
        self.questions[question_id] = question_data
        self.stats['total_questions'] += 1
        category = question_data.get('category')
        if category:
            self.stats['categories'][category] = self.stats['categories'].get(category, 0) + 1
        self.save()

    def update_question(self, question_id: str, update_data: dict):
        """Обновление данных вопроса"""
        if question_id in self.questions:
            self.questions[question_id].update(update_data)
            if update_data.get('status') == 'answered':
                self.stats['answered_questions'] += 1
            self.save()

    def get_question(self, question_id: str) -> dict:
        """Получение данных вопроса"""
        return self.questions.get(question_id, {})

# Инициализация базы данных
db = Database()

def get_main_keyboard():
    """Создание основной клавиатуры"""
    keyboard = [
        ["📝 Задати питання"],
        ["📋 Мої питання", "✉️ Мої відповіді"],
        ["❓ Допомога"],
        [f"📢 Канал з відповідями"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_category_keyboard():
    """Создание клавиатуры с категориями"""
    keyboard = []
    
    # Создаем кнопки для каждой категории
    for cat_id, name in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"cat_{cat_id}")])
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard(question_id: str):
    """Создание клавиатуры для администраторов"""
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

def get_admin_menu_keyboard():
    """Создание клавиатуры главного меню для админов"""
    keyboard = [
        ["📥 Нові питання", "⭐️ Важливі питання"],
        ["✅ Опрацьовані", "❌ Відхилені"],
        ["🔄 Змінити відповідь", "📊 Статистика"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_questions_list_keyboard(questions: List[dict], page: int = 0, items_per_page: int = 5):
    """Создание клавиатуры со списком вопросов"""
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
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

            # Отправляем отдельное сообщение с кнопкой канала
            channel_button = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "📢 Перейти в канал з відповідями",
                    url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"
                )
            ]])
            await update.message.reply_text(
                "Натисніть кнопку нижче, щоб перейти в канал з відповідями:",
                reply_markup=channel_button,
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
    """Обработчик команды /cancel"""
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

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику бота"""
    query = update.callback_query
    await query.answer()

    stats_text = (
        "📊 Статистика бота:\n\n"
        f"📝 Всего вопросов: {db.stats['total_questions']}\n"
        f"✅ Отвечено: {db.stats['answered_questions']}\n"
        f"⏳ Ожидают ответа: {db.stats['total_questions'] - db.stats['answered_questions']}\n\n"
        "📊 По категориям:\n"
    )

    for cat_id, cat_name in CATEGORIES.items():
        count = db.stats['categories'].get(cat_id, 0)
        stats_text += f"{cat_name}: {count}\n"

    await query.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Назад", callback_data='back_to_main')
        ]])
    )

async def handle_admin_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str):
    """Отправка вопроса администраторам"""
    try:
        question = db.questions[question_id]
        message_text = (
            f"📨 Нове анонімне питання\n\n"
            f"Категорія: {CATEGORIES[question['category']]}\n"
            f"Питання: {question['text']}"
        )

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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
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
        if user_id not in ADMIN_IDS and any(data.startswith(prefix) for prefix in ['view_q_', 'answer_', 'reject_', 'important_', 'edit_']):
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
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            question = db.questions[question_id]
            status_emoji = {
                'pending': '⏳',
                'answered': '✅',
                'rejected': '❌'
            }.get(question['status'], '⏳')

            # Формируем текст сообщения
            message_text = (
                f"📨 Питання {status_emoji}\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n"
            )

            if question.get('answer'):
                message_text += f"\n✍️ Відповідь:\n{question['answer']}\n"

            # Создаем клавиатуру действий для вопроса
            keyboard = []
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

            # Добавляем кнопки навигации
            keyboard.append([InlineKeyboardButton("🔙 До списку", callback_data=f"page_{context.user_data.get('current_page', 0)}")])

            await query.message.edit_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING

        elif data.startswith("answer_"):
            question_id = data.replace("answer_", "")
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            context.user_data['answering'] = question_id
            question = db.questions[question_id]

            await query.message.edit_text(
                f"✍️ Відповідь на питання:\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"Напишіть вашу відповідь одним повідомленням:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Скасувати", callback_data=f"view_q_{question_id}")
                ]])
            )
            return TYPING_REPLY

        elif data.startswith("edit_"):
            question_id = data.replace("edit_", "")
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            context.user_data['editing'] = question_id
            question = db.questions[question_id]

            await query.message.edit_text(
                f"🔄 Зміна відповіді:\n\n"
                f"Категорія: {CATEGORIES[question['category']]}\n"
                f"Питання: {question['text']}\n\n"
                f"Поточна відповідь:\n{question.get('answer', '')}\n\n"
                f"Напишіть нову відповідь одним повідомленням:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Скасувати", callback_data=f"view_q_{question_id}")
                ]])
            )
            return TYPING_REPLY

        elif data.startswith("reject_"):
            question_id = data.replace("reject_", "")
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            db.update_question(question_id, {'status': 'rejected'})
            question = db.questions[question_id]

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
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            db.update_question(question_id, {'status': 'pending'})
            question = db.questions[question_id]

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
            if question_id not in db.questions:
                await query.message.edit_text("❌ Питання не знайдено")
                return CHOOSING

            question = db.questions[question_id]
            is_important = not question.get('important', False)
            db.update_question(question_id, {'important': is_important})

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
            if question_id not in db.questions:
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
            stats_text = (
                "📊 Статистика боту:\n\n"
                f"📝 Всього питань: {db.stats['total_questions']}\n"
                f"✅ Відповіді надано: {db.stats['answered_questions']}\n"
                f"⏳ Очікують відповіді: {db.stats['total_questions'] - db.stats['answered_questions']}\n\n"
                "📊 По категоріях:\n"
            )

            for cat_id, cat_name in CATEGORIES.items():
                count = db.stats['categories'].get(cat_id, 0)
                stats_text += f"{cat_name}: {count}\n"

            await query.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
                ]])
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

async def show_my_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать вопросы пользователя"""
    try:
        user_id = update.effective_user.id
        user_questions = []

        # Собираем все вопросы пользователя
        for q_id, question in db.questions.items():
            if question.get('user_id') == user_id:
                status = {
                    'pending': '⏳ Очікує відповіді',
                    'answered': '✅ Відповідь отримано',
                    'rejected': '❌ Відхилено'
                }.get(question['status'], '⏳ Очікує відповіді')

                user_questions.append({
                    'id': q_id,
                    'text': question['text'],
                    'status': status,
                    'category': CATEGORIES[question['category']]
                })

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
            questions_text += (
                f"{i}. {q['category']}\n"
                f"Питання: {q['text']}\n"
                f"Статус: {q['status']}\n\n"
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

async def show_my_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ответы на вопросы пользователя"""
    try:
        user_id = update.effective_user.id
        answered_questions = []

        # Собираем все отвеченные вопросы пользователя
        for q_id, question in db.questions.items():
            if question.get('user_id') == user_id and question.get('status') == 'answered':
                answered_questions.append({
                    'id': q_id,
                    'text': question['text'],
                    'answer': question.get('answer', ''),
                    'category': CATEGORIES[question['category']]
                })

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
                f"{i}. {q['category']}\n"
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        is_admin = user_id in ADMIN_IDS

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
                return await show_my_questions(update, context)

            elif text == "✉️ Мої відповіді":
                return await show_my_answers(update, context)

            elif text == "📢 Канал з відповідями":
                # Отправляем ссылку на канал
                await update.message.reply_text(
                    "Перейдіть в канал, щоб побачити всі відповіді:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "📢 Перейти в канал",
                            url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"
                        )
                    ]]),
                    disable_notification=True
                )
                return CHOOSING

            elif text == "❓ Допомога":
                help_text = (
                    "📌 Як користуватися ботом:\n\n"
                    "1️⃣ Задати питання:\n"
                    "   • Натисніть '📝 Задати питання'\n"
                    "   • Оберіть категорію\n"
                    "   • Напишіть своє питання\n\n"
                    "2️⃣ Отримання відповіді:\n"
                    "   • Ваше питання отримають адміністратори\n"
                    "   • При публікації відповіді вона з'явиться в каналі\n"
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
                await update.message.reply_text(help_text, disable_notification=True)
                return CHOOSING

            # Проверяем, является ли пользователь администратором для админских команд
            elif text in ["📥 Нові питання", "⭐️ Важливі питання", "✅ Опрацьовані", "❌ Відхилені", "🔄 Змінити відповідь", "📊 Статистика"]:
                if not is_admin:
                    await update.message.reply_text(
                        "❌ У вас немає прав адміністратора",
                        reply_markup=get_main_keyboard(),
                        disable_notification=True
                    )
                    return CHOOSING
                return await handle_admin_menu(update, context)

            # Для всех остальных сообщений показываем обычную клавиатуру
            keyboard = get_admin_menu_keyboard() if is_admin else get_main_keyboard()
            await update.message.reply_text(
                "Оберіть опцію з меню:",
                reply_markup=keyboard,
                disable_notification=True
            )
            return CHOOSING

        # Продолжаем обработку обычных сообщений
        return await handle_regular_message(update, context)

    except Exception as e:
        logger.error(f"Загальна помилка в handle_message: {e}")
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Виникла помилка. Будь ласка, почніть спочатку з команди /start",
            disable_notification=True
        )
        return CHOOSING

async def handle_regular_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных текстовых сообщений"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text

        logger.info(f"Отримано повідомлення від користувача {user_id}: {message_text}")
        logger.info(f"Поточний стан: {context.user_data}")

        # Обработка ответа на вопрос или редактирования ответа
        if (context.user_data.get('answering') or context.user_data.get('editing')) and user_id in ADMIN_IDS:
            try:
                question_id = context.user_data.get('answering') or context.user_data.get('editing')
                answer_text = message_text
                question = db.questions[question_id]
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
                await handle_admin_question(update, context, question_id)

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
            if update.effective_chat.id == int(ADMIN_GROUP_ID) and user_id in ADMIN_IDS:
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

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик админского меню"""
    try:
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ У вас нет прав администратора.",
                disable_notification=True
            )
            return CHOOSING
        
        # Получаем текст команды
        text = update.message.text
        
        if text == "📊 Статистика":
            # Подсчитываем статистику по статусам
            status_counts = {'pending': 0, 'answered': 0, 'rejected': 0}
            category_counts = {cat_id: 0 for cat_id in CATEGORIES.keys()}
            important_count = 0
            total_questions = len(db.questions)
            
            for q in db.questions.values():
                status = q.get('status', 'pending')
                status_counts[status] = status_counts.get(status, 0) + 1
                category_counts[q['category']] = category_counts.get(q['category'], 0) + 1
                if q.get('important', False):
                    important_count += 1

            stats_text = (
                "📊 Детальна статистика бота:\n\n"
                f"📝 Загальна кількість питань: {total_questions}\n"
                "➖➖➖➖➖➖➖➖➖➖\n\n"
                "📋 По статусу:\n"
                f"⏳ Очікують відповіді: {status_counts['pending']}\n"
                f"✅ Опрацьовані: {status_counts['answered']}\n"
                f"❌ Відхилені: {status_counts['rejected']}\n"
                f"⭐️ Важливі питання: {important_count}\n\n"
                "📊 По категоріях:\n"
            )

            # Добавляем статистику по категориям с процентами
            for cat_id, cat_name in CATEGORIES.items():
                count = category_counts[cat_id]
                percentage = (count / total_questions * 100) if total_questions > 0 else 0
                stats_text += f"{cat_name}: {count} ({percentage:.1f}%)\n"

            # Добавляем эффективность работы
            if status_counts['answered'] > 0:
                answered_percentage = (status_counts['answered'] / total_questions * 100)
                stats_text += f"\n📈 Ефективність роботи: {answered_percentage:.1f}%"

            await update.message.reply_text(
                stats_text,
                reply_markup=get_admin_menu_keyboard(),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "📥 Нові питання":
            # Получаем список новых вопросов
            new_questions = [q for q in db.questions.values() if q['status'] == 'pending']
            if not new_questions:
                await update.message.reply_text(
                    "📭 Нових питань немає",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            # Сохраняем список вопросов в контексте
            context.user_data['current_questions'] = new_questions
            context.user_data['current_page'] = 0
            
            await update.message.reply_text(
                "📥 Нові питання:",
                reply_markup=get_questions_list_keyboard(new_questions),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "⭐️ Важливі питання":
            # Получаем список важных вопросов
            important_questions = [q for q in db.questions.values() if q.get('important', False)]
            if not important_questions:
                await update.message.reply_text(
                    "⭐️ Важливих питань немає",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            context.user_data['current_questions'] = important_questions
            context.user_data['current_page'] = 0
            
            await update.message.reply_text(
                "⭐️ Важливі питання:",
                reply_markup=get_questions_list_keyboard(important_questions),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "✅ Опрацьовані":
            # Получаем список отвеченных вопросов
            answered_questions = [q for q in db.questions.values() if q['status'] == 'answered']
            if not answered_questions:
                await update.message.reply_text(
                    "✅ Опрацьованих питань немає",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            context.user_data['current_questions'] = answered_questions
            context.user_data['current_page'] = 0
            
            await update.message.reply_text(
                "✅ Опрацьовані питання:",
                reply_markup=get_questions_list_keyboard(answered_questions),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "❌ Відхилені":
            # Получаем список отклоненных вопросов
            rejected_questions = [q for q in db.questions.values() if q['status'] == 'rejected']
            if not rejected_questions:
                await update.message.reply_text(
                    "❌ Відхилених питань немає",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            context.user_data['current_questions'] = rejected_questions
            context.user_data['current_page'] = 0
            
            await update.message.reply_text(
                "❌ Відхилені питання:",
                reply_markup=get_questions_list_keyboard(rejected_questions),
                disable_notification=True
            )
            return CHOOSING
            
        elif text == "🔄 Змінити відповідь":
            # Получаем список отвеченных вопросов для изменения
            answered_questions = [q for q in db.questions.values() if q['status'] == 'answered']
            if not answered_questions:
                await update.message.reply_text(
                    "✅ Немає питань з відповідями для зміни",
                    reply_markup=get_admin_menu_keyboard(),
                    disable_notification=True
                )
                return CHOOSING
            
            context.user_data['current_questions'] = answered_questions
            context.user_data['current_page'] = 0
            context.user_data['editing_answer'] = True
            
            await update.message.reply_text(
                "🔄 Оберіть питання для зміни відповіді:",
                reply_markup=get_questions_list_keyboard(answered_questions),
                disable_notification=True
            )
            return CHOOSING
            
        else:
            await update.message.reply_text(
                "❗️ Оберіть дію з меню:",
                reply_markup=get_admin_menu_keyboard(),
                disable_notification=True
            )
            return CHOOSING
            
    except Exception as e:
        logger.error(f"Помилка в админському меню: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте пізніше.",
            reply_markup=get_admin_menu_keyboard(),
            disable_notification=True
        )
        return CHOOSING

def main():
    """Запуск бота"""
    try:
        # Проверяем наличие всех необходимых переменных окружения
        required_env = {
            'TELEGRAM_TOKEN': 'токен бота',
            'CHANNEL_ID': 'ID каналу для відповідей',
            'ADMIN_GROUP_ID': 'ID групи адміністраторів',
            'ADMIN_IDS': 'ID адміністраторів'
        }

        missing_env = [key for key, desc in required_env.items() if not os.getenv(key)]
        if missing_env:
            print("❌ Відсутні необхідні змінні оточення:")
            for key in missing_env:
                print(f"- {key} ({required_env[key]})")
            return

        # Проверяем корректность ID группы админов
        try:
            admin_group_id = int(os.getenv('ADMIN_GROUP_ID'))
            logger.info(f"ID группы админов: {admin_group_id}")
        except ValueError:
            logger.error("Некорректный формат ADMIN_GROUP_ID")
            print("❌ Некорректный формат ADMIN_GROUP_ID")
            return

        # Создаем приложение
        application = Application.builder().token(TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("cancel", cancel))
        application.add_handler(CommandHandler("stats", show_stats))
        
        # Добавляем обработчик для админского меню
        application.add_handler(MessageHandler(filters.Regex("^(📥 Нові питання|⭐️ Важливі питання|✅ Опрацьовані|❌ Відхилені|🔄 Змінити відповідь|📊 Статистика)$"), handle_admin_menu))
        
        # Добавляем обработчик для обычных сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Добавляем обработчик для callback-запросов
        application.add_handler(CallbackQueryHandler(button_handler))

        print("🚀 Бот запущено!")
        logger.info("Бот запущен и готов к работе")
        
        # Запускаем бота
        if BOT_MODE == 'webhook' and WEBHOOK_URL:
            application.run_webhook(
                listen='0.0.0.0',
                port=int(os.getenv('PORT', 8080)),
                webhook_url=WEBHOOK_URL
            )
        else:
            application.run_polling()

    except Exception as e:
        logger.error(f"Помилка при запуску бота: {e}")
        print(f"❌ Помилка при запуску бота: {e}")

# Для gunicorn
app = Application.builder().token(TOKEN).build()

# Добавляем обработчики
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("cancel", cancel))
app.add_handler(CommandHandler("stats", show_stats))
app.add_handler(MessageHandler(filters.Regex("^(📥 Нові питання|⭐️ Важливі питання|✅ Опрацьовані|❌ Відхилені|🔄 Змінити відповідь|📊 Статистика)$"), handle_admin_menu))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == '__main__':
    main() 