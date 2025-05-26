import unittest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Импортируем модули для тестирования
from config import CATEGORIES, CHOOSING, TYPING_QUESTION, TYPING_CATEGORY, TYPING_REPLY
from database import Database
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

class TestDatabase(unittest.TestCase):
    """Тесты для модуля базы данных"""
    
    def setUp(self):
        """Подготовка к тестам"""
        # Используем тестовую базу данных
        self.test_db_file = 'test_db.json'
        self.test_sqlite_file = 'test_db.sqlite'
        
        # Удаляем тестовые файлы, если они существуют
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)
        if os.path.exists(self.test_sqlite_file):
            os.remove(self.test_sqlite_file)
        
        # Создаем экземпляр базы данных
        self.db_json = Database(db_type='json', filename=self.test_db_file)
        self.db_sqlite = Database(db_type='sqlite', sqlite_file=self.test_sqlite_file)
    
    def tearDown(self):
        """Очистка после тестов"""
        # Удаляем тестовые файлы
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)
        if os.path.exists(self.test_sqlite_file):
            os.remove(self.test_sqlite_file)
    
    def test_add_question_json(self):
        """Тест добавления вопроса в JSON базу"""
        # Добавляем тестовый вопрос
        question_id = 'test1'
        question_data = {
            'id': question_id,
            'category': 'general',
            'text': 'Test question',
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'important': False,
            'user_id': 123456789
        }
        
        self.db_json.add_question(question_id, question_data)
        
        # Проверяем, что вопрос добавлен
        self.assertIn(question_id, self.db_json.questions)
        self.assertEqual(self.db_json.questions[question_id]['text'], 'Test question')
        self.assertEqual(self.db_json.stats['total_questions'], 1)
        self.assertEqual(self.db_json.stats['categories']['general'], 1)
    
    def test_add_question_sqlite(self):
        """Тест добавления вопроса в SQLite базу"""
        # Добавляем тестовый вопрос
        question_id = 'test1'
        question_data = {
            'id': question_id,
            'category': 'general',
            'text': 'Test question',
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'important': False,
            'user_id': 123456789
        }
        
        self.db_sqlite.add_question(question_id, question_data)
        
        # Проверяем, что вопрос добавлен
        self.assertIn(question_id, self.db_sqlite.questions)
        self.assertEqual(self.db_sqlite.questions[question_id]['text'], 'Test question')
        self.assertEqual(self.db_sqlite.stats['total_questions'], 1)
        self.assertEqual(self.db_sqlite.stats['categories']['general'], 1)
    
    def test_update_question(self):
        """Тест обновления вопроса"""
        # Добавляем тестовый вопрос
        question_id = 'test1'
        question_data = {
            'id': question_id,
            'category': 'general',
            'text': 'Test question',
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'important': False,
            'user_id': 123456789
        }
        
        self.db_json.add_question(question_id, question_data)
        
        # Обновляем вопрос
        update_data = {
            'status': 'answered',
            'answer': 'Test answer',
            'answer_time': datetime.now().isoformat()
        }
        
        self.db_json.update_question(question_id, update_data)
        
        # Проверяем, что вопрос обновлен
        self.assertEqual(self.db_json.questions[question_id]['status'], 'answered')
        self.assertEqual(self.db_json.questions[question_id]['answer'], 'Test answer')
        self.assertEqual(self.db_json.stats['answered_questions'], 1)
    
    def test_get_questions_by_status(self):
        """Тест получения вопросов по статусу"""
        # Добавляем тестовые вопросы
        self.db_json.add_question('test1', {
            'id': 'test1',
            'category': 'general',
            'text': 'Test question 1',
            'status': 'pending',
            'time': datetime.now().isoformat(),
            'important': False,
            'user_id': 123456789
        })
        
        self.db_json.add_question('test2', {
            'id': 'test2',
            'category': 'spiritual',
            'text': 'Test question 2',
            'status': 'answered',
            'time': datetime.now().isoformat(),
            'important': False,
            'user_id': 123456789,
            'answer': 'Test answer',
            'answer_time': datetime.now().isoformat()
        })
        
        # Получаем вопросы по статусу
        pending_questions = self.db_json.get_questions_by_status('pending')
        answered_questions = self.db_json.get_questions_by_status('answered')
        
        # Проверяем результаты
        self.assertEqual(len(pending_questions), 1)
        self.assertEqual(pending_questions[0]['id'], 'test1')
        
        self.assertEqual(len(answered_questions), 1)
        self.assertEqual(answered_questions[0]['id'], 'test2')

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
