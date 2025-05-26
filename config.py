import os
import logging
from dotenv import load_dotenv
from typing import List, Dict, Optional

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

# Режим работы бота (polling или webhook)
BOT_MODE = os.getenv('BOT_MODE', 'polling')  # По умолчанию используем polling
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')  # URL для webhook
PORT = int(os.getenv('PORT', '8080'))  # Порт для webhook сервера

# Категории вопросов
CATEGORIES: Dict[str, str] = {
    'general': '🌟 Загальні',
    'spiritual': '🙏 Духовні',
    'personal': '👤 Особисті',
    'urgent': '⚡️ Термінові'
}

# Проверка наличия всех необходимых переменных окружения
def validate_config() -> bool:
    """Проверка конфигурации на наличие всех необходимых переменных окружения"""
    required_env = {
        'TELEGRAM_TOKEN': 'токен бота',
        'CHANNEL_ID': 'ID каналу для відповідей',
        'ADMIN_GROUP_ID': 'ID групи адміністраторів',
        'ADMIN_IDS': 'ID адміністраторів'
    }

    missing_env = [key for key, desc in required_env.items() if not os.getenv(key)]
    if missing_env:
        logger.error("Відсутні необхідні змінні оточення:")
        for key in missing_env:
            logger.error(f"- {key} ({required_env[key]})")
        return False

    # Проверяем корректность ID группы админов
    try:
        admin_group_id = int(os.getenv('ADMIN_GROUP_ID', '0'))
        logger.info(f"ID группы админов: {admin_group_id}")
    except ValueError:
        logger.error("Некорректный формат ADMIN_GROUP_ID")
        return False

    # Проверяем режим работы
    if BOT_MODE == 'webhook' and not WEBHOOK_URL:
        logger.error("Для режима webhook необходимо указать WEBHOOK_URL")
        return False

    return True
