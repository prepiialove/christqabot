import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import threading

from config import CATEGORIES, logger

class DatabaseException(Exception):
    """Базовое исключение для ошибок базы данных"""
    pass

class Database:
    """Класс для работы с базой данных"""
    def __init__(self, db_type: str = 'json', filename: str = 'db.json', sqlite_file: str = 'bot.db'):
        """
        Инициализация базы данных
        
        Args:
            db_type: Тип базы данных ('json' или 'sqlite')
            filename: Имя файла для JSON базы данных
            sqlite_file: Имя файла для SQLite базы данных
        """
        self.db_type = db_type
        self.filename = filename
        self.sqlite_file = sqlite_file
        self.questions = {}
        self.stats = {
            'total_questions': 0,
            'answered_questions': 0,
            'categories': {cat: 0 for cat in CATEGORIES.keys()}
        }
        self.lock = threading.Lock()  # Для безопасного доступа к данным
        
        # Инициализация базы данных в зависимости от типа
        if db_type == 'json':
            self.load_json()
        elif db_type == 'sqlite':
            self.init_sqlite()
        else:
            raise DatabaseException(f"Неподдерживаемый тип базы данных: {db_type}")

    def load_json(self) -> None:
        """Загрузка базы данных из JSON файла"""
        try:
            if os.path.exists(self.filename):
                with self.lock:
                    with open(self.filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.questions = data.get('questions', {})
                        self.stats = data.get('stats', {
                            'total_questions': 0,
                            'answered_questions': 0,
                            'categories': {cat: 0 for cat in CATEGORIES.keys()}
                        })
                logger.info(f"База данных успешно загружена из {self.filename}")
            else:
                logger.info(f"Файл базы данных {self.filename} не найден, создана новая база")
                self.save_json()
        except Exception as e:
            logger.error(f"Ошибка при загрузке базы данных из JSON: {e}")
            raise DatabaseException(f"Ошибка при загрузке базы данных: {e}")

    def save_json(self) -> None:
        """Сохранение базы данных в JSON файл"""
        try:
            with self.lock:
                with open(self.filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'questions': self.questions,
                        'stats': self.stats
                    }, f, ensure_ascii=False, indent=2)
            logger.info(f"База данных успешно сохранена в {self.filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении базы данных в JSON: {e}")
            raise DatabaseException(f"Ошибка при сохранении базы данных: {e}")

    def init_sqlite(self) -> None:
        """Инициализация SQLite базы данных"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.sqlite_file)
                cursor = conn.cursor()
                
                # Создаем таблицу для вопросов, если она не существует
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    time TEXT NOT NULL,
                    important INTEGER DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    answer TEXT,
                    answer_time TEXT,
                    answer_message_id INTEGER
                )
                ''')
                
                # Создаем таблицу для статистики
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER
                )
                ''')
                
                # Инициализируем статистику, если она не существует
                cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_questions', 0)")
                cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('answered_questions', 0)")
                
                # Инициализируем статистику по категориям
                for cat in CATEGORIES.keys():
                    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES (?, 0)", (f"category_{cat}",))
                
                conn.commit()
                conn.close()
                
                # Загружаем данные из SQLite в память
                self._load_from_sqlite()
                
            logger.info(f"SQLite база данных инициализирована в {self.sqlite_file}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации SQLite базы данных: {e}")
            raise DatabaseException(f"Ошибка при инициализации SQLite базы данных: {e}")

    def _load_from_sqlite(self) -> None:
        """Загрузка данных из SQLite в память"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.sqlite_file)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Загружаем вопросы
                cursor.execute("SELECT * FROM questions")
                rows = cursor.fetchall()
                self.questions = {}
                for row in rows:
                    question = dict(row)
                    # Преобразуем important из 0/1 в False/True
                    question['important'] = bool(question['important'])
                    self.questions[question['id']] = question
                
                # Загружаем статистику
                cursor.execute("SELECT * FROM stats")
                rows = cursor.fetchall()
                self.stats = {
                    'total_questions': 0,
                    'answered_questions': 0,
                    'categories': {cat: 0 for cat in CATEGORIES.keys()}
                }
                
                for row in rows:
                    key, value = row['key'], row['value']
                    if key == 'total_questions':
                        self.stats['total_questions'] = value
                    elif key == 'answered_questions':
                        self.stats['answered_questions'] = value
                    elif key.startswith('category_'):
                        cat = key.replace('category_', '')
                        if cat in CATEGORIES:
                            self.stats['categories'][cat] = value
                
                conn.close()
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных из SQLite: {e}")
            raise DatabaseException(f"Ошибка при загрузке данных из SQLite: {e}")

    def _save_to_sqlite(self) -> None:
        """Сохранение данных из памяти в SQLite"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.sqlite_file)
                cursor = conn.cursor()
                
                # Сохраняем вопросы
                for q_id, question in self.questions.items():
                    # Преобразуем important из True/False в 1/0
                    important = 1 if question.get('important', False) else 0
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO questions 
                    (id, category, text, status, time, important, user_id, answer, answer_time, answer_message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        question['id'],
                        question['category'],
                        question['text'],
                        question['status'],
                        question['time'],
                        important,
                        question['user_id'],
                        question.get('answer'),
                        question.get('answer_time'),
                        question.get('answer_message_id')
                    ))
                
                # Сохраняем статистику
                cursor.execute("UPDATE stats SET value = ? WHERE key = ?", 
                              (self.stats['total_questions'], 'total_questions'))
                cursor.execute("UPDATE stats SET value = ? WHERE key = ?", 
                              (self.stats['answered_questions'], 'answered_questions'))
                
                # Сохраняем статистику по категориям
                for cat, count in self.stats['categories'].items():
                    cursor.execute("UPDATE stats SET value = ? WHERE key = ?", 
                                  (count, f"category_{cat}"))
                
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных в SQLite: {e}")
            raise DatabaseException(f"Ошибка при сохранении данных в SQLite: {e}")

    def save(self) -> None:
        """Сохранение базы данных"""
        if self.db_type == 'json':
            self.save_json()
        elif self.db_type == 'sqlite':
            self._save_to_sqlite()

    def add_question(self, question_id: str, question_data: dict) -> None:
        """
        Добавление нового вопроса
        
        Args:
            question_id: Уникальный идентификатор вопроса
            question_data: Данные вопроса
        """
        try:
            with self.lock:
                self.questions[question_id] = question_data
                self.stats['total_questions'] += 1
                category = question_data.get('category')
                if category and category in self.stats['categories']:
                    self.stats['categories'][category] = self.stats['categories'].get(category, 0) + 1
            self.save()
            logger.info(f"Вопрос {question_id} успешно добавлен")
        except Exception as e:
            logger.error(f"Ошибка при добавлении вопроса: {e}")
            raise DatabaseException(f"Ошибка при добавлении вопроса: {e}")

    def update_question(self, question_id: str, update_data: dict) -> None:
        """
        Обновление данных вопроса
        
        Args:
            question_id: Уникальный идентификатор вопроса
            update_data: Данные для обновления
        """
        try:
            with self.lock:
                if question_id in self.questions:
                    # Проверяем, меняется ли статус на 'answered'
                    was_answered = self.questions[question_id].get('status') == 'answered'
                    will_be_answered = update_data.get('status') == 'answered'
                    
                    # Обновляем данные вопроса
                    self.questions[question_id].update(update_data)
                    
                    # Если вопрос стал отвеченным, увеличиваем счетчик
                    if not was_answered and will_be_answered:
                        self.stats['answered_questions'] += 1
                    
                    self.save()
                    logger.info(f"Вопрос {question_id} успешно обновлен")
                else:
                    logger.warning(f"Попытка обновить несуществующий вопрос: {question_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении вопроса: {e}")
            raise DatabaseException(f"Ошибка при обновлении вопроса: {e}")

    def get_question(self, question_id: str) -> dict:
        """
        Получение данных вопроса
        
        Args:
            question_id: Уникальный идентификатор вопроса
            
        Returns:
            Данные вопроса или пустой словарь, если вопрос не найден
        """
        with self.lock:
            return self.questions.get(question_id, {})

    def get_questions_by_status(self, status: str) -> List[dict]:
        """
        Получение списка вопросов по статусу
        
        Args:
            status: Статус вопросов ('pending', 'answered', 'rejected')
            
        Returns:
            Список вопросов с указанным статусом
        """
        with self.lock:
            return [q for q in self.questions.values() if q.get('status') == status]

    def get_questions_by_user(self, user_id: int) -> List[dict]:
        """
        Получение списка вопросов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список вопросов пользователя
        """
        with self.lock:
            return [q for q in self.questions.values() if q.get('user_id') == user_id]

    def get_important_questions(self) -> List[dict]:
        """
        Получение списка важных вопросов
        
        Returns:
            Список важных вопросов
        """
        with self.lock:
            return [q for q in self.questions.values() if q.get('important', False)]

    def get_stats(self) -> dict:
        """
        Получение статистики
        
        Returns:
            Статистика использования бота
        """
        with self.lock:
            return self.stats.copy()

    def backup(self, backup_dir: str = 'backups') -> str:
        """
        Создание резервной копии базы данных
        
        Args:
            backup_dir: Директория для резервных копий
            
        Returns:
            Путь к файлу резервной копии
        """
        try:
            # Создаем директорию для резервных копий, если она не существует
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # Формируем имя файла резервной копии с текущей датой и временем
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if self.db_type == 'json':
                backup_file = os.path.join(backup_dir, f"backup_{timestamp}_{os.path.basename(self.filename)}")
                with self.lock:
                    with open(self.filename, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
            elif self.db_type == 'sqlite':
                backup_file = os.path.join(backup_dir, f"backup_{timestamp}_{os.path.basename(self.sqlite_file)}")
                with self.lock:
                    conn = sqlite3.connect(self.sqlite_file)
                    backup_conn = sqlite3.connect(backup_file)
                    conn.backup(backup_conn)
                    backup_conn.close()
                    conn.close()
            
            logger.info(f"Создана резервная копия базы данных: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")
            raise DatabaseException(f"Ошибка при создании резервной копии: {e}")

    def migrate_json_to_sqlite(self, json_file: str, sqlite_file: str) -> None:
        """
        Миграция данных из JSON в SQLite
        
        Args:
            json_file: Путь к JSON файлу
            sqlite_file: Путь к SQLite файлу
        """
        try:
            # Загружаем данные из JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = data.get('questions', {})
                stats = data.get('stats', {
                    'total_questions': 0,
                    'answered_questions': 0,
                    'categories': {cat: 0 for cat in CATEGORIES.keys()}
                })
            
            # Создаем и инициализируем SQLite базу данных
            conn = sqlite3.connect(sqlite_file)
            cursor = conn.cursor()
            
            # Создаем таблицы
            cur
(Content truncated due to size limit. Use line ranges to read in chunks)