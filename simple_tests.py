import unittest
from unittest.mock import patch
from datetime import datetime

# Импортируем модули для тестирования
from config import CATEGORIES, CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY
from utils import is_admin, format_question_for_user, format_datetime, format_stats

class TestConfig(unittest.TestCase):
    """Тесты для модуля конфигурации"""
    
    def test_categories(self):
        """Проверка наличия всех категорий"""
        self.assertIn('general', CATEGORIES)
        self.assertIn('spiritual', CATEGORIES)
        self.assertIn('personal', CATEGORIES)
        self.assertIn('urgent', CATEGORIES)
        
    def test_conversation_states(self):
        """Проверка состояний разговора"""
        self.assertEqual(CHOOSING, 0)
        self.assertEqual(TYPING_QUESTION, 1)
        self.assertEqual(TYPING_CATEGORY, 2)
        self.assertEqual(TYPING_REPLY, 3)

class TestUtils(unittest.TestCase):
    """Тесты для модуля утилит"""
    
    def test_is_admin(self):
        """Тест функции проверки администратора"""
        # Патчим ADMIN_IDS
        with patch('utils.ADMIN_IDS', [123456789]):
            # Проверяем, что функция правильно определяет админа
            self.assertTrue(is_admin(123456789))
            self.assertFalse(is_admin(987654321))
    
    def test_format_datetime(self):
        """Тест функции форматирования даты и времени"""
        # Проверяем форматирование даты
        iso_date = '2023-01-01T12:00:00'
        formatted_date = format_datetime(iso_date)
        self.assertEqual(formatted_date, '01.01.2023 12:00:00')
    
    def test_format_question_for_user(self):
        """Тест функции форматирования вопроса для пользователя"""
        # Создаем тестовый вопрос
        question = {
            'category': 'general',
            'text': 'Test question',
            'status': 'pending'
        }
        
        # Форматируем вопрос
        formatted_question = format_question_for_user(question)
        
        # Проверяем результат
        self.assertIn('Категорія: 🌟 Загальні', formatted_question)
        self.assertIn('Питання: Test question', formatted_question)
        self.assertIn('Статус: ⏳ Очікує відповіді', formatted_question)
    
    def test_format_stats(self):
        """Тест функции форматирования статистики"""
        # Создаем тестовую статистику
        stats = {
            'total_questions': 10,
            'answered_questions': 5,
            'categories': {
                'general': 4,
                'spiritual': 3,
                'personal': 2,
                'urgent': 1
            }
        }
        
        # Форматируем статистику
        formatted_stats = format_stats(stats)
        
        # Проверяем результат
        self.assertIn('Всього питань: 10', formatted_stats)
        self.assertIn('Відповіді надано: 5', formatted_stats)
        self.assertIn('Очікують відповіді: 5', formatted_stats)
        self.assertIn('Ефективність роботи: 50.0%', formatted_stats)

if __name__ == '__main__':
    unittest.main()
