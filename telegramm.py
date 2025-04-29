import telebot
from telebot import types
import sqlite3
import logging
from typing import Optional, Dict, List
import os
from datetime import datetime, timedelta
import json
import signal
import sys
import random
import string
import re
import time
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Улучшенная конфигурация логирования
logging.basicConfig(
    filename="bot_logs.log",
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация и константы
CONFIG = {
    "FEEDBACK_DELAY_HOURS": 24,
    "MAX_DAILY_REQUESTS": 5,
    "SUPPORT_HOURS": {
        "start": 9,
        "end": 21
    },
    "AUTO_CLOSE_HOURS": 48,  # Автоматическое закрытие неактивных заявок
    "MAX_MESSAGE_LENGTH": 4000,  # Максимальная длина сообщения
    "RATING_THRESHOLD": 3,  # Порог для автоматического закрытия заявки
    "PRIORITY_LEVELS": {
        "Низкий": 1,
        "Средний": 2,
        "Высокий": 3,
        "Критический": 4
    }
}

# Получение конфигурационных переменных
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPPORT_CHAT_ID = os.getenv('SUPPORT_CHAT_ID')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5499105806'))

# Глобальная переменная для хранения состояния администратора
admin_mode = {}

# Словарь для хранения временных данных
temp_data = {}

# Проверка обязательных переменных окружения
if not all([BOT_TOKEN, SUPPORT_CHAT_ID, ADMIN_ID]):
    missing_vars = []
    if not BOT_TOKEN:
        missing_vars.append("BOT_TOKEN")
    if not SUPPORT_CHAT_ID:
        missing_vars.append("SUPPORT_CHAT_ID")
    if not ADMIN_ID:
        missing_vars.append("ADMIN_ID")
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    print(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    print("Пожалуйста, проверьте файл .env и убедитесь, что все переменные установлены.")
    sys.exit(1)

# Расширенный словарь проблем и решений
problems = {
    "internet": {
        "title": "🌐 Проблемы с интернетом",
        "icon": "🌐",
        "categories": {
            "slow": {
                "title": "Медленное соединение",
                "steps": [
                    "Проверьте скорость на speedtest.net",
                    "Перезагрузите роутер",
                    "Проверьте количество подключенных устройств",
                    "Убедитесь, что никто не загружает большие файлы"
                ],
                "additional": "Попробуйте подключиться через кабель вместо Wi-Fi",
                "priority": "Средний"
            },
            "disconnects": {
                "title": "Частые разрывы",
                "steps": [
                    "Проверьте качество кабеля",
                    "Обновите прошивку роутера",
                    "Проверьте уровень сигнала Wi-Fi",
                    "Смените канал Wi-Fi на менее загруженный"
                ],
                "additional": "Используйте приложение Wi-Fi Analyzer для проверки загруженности каналов",
                "priority": "Средний"
            },
            "no_connection": {
                "title": "Нет подключения",
                "steps": [
                    "Проверьте физическое подключение кабелей",
                    "Перезагрузите все сетевое оборудование",
                    "Проверьте баланс и статус услуги",
                    "Свяжитесь с провайдером"
                ],
                "additional": "Проверьте работу интернета на других устройствах",
                "priority": "Высокий"
            }
        }
    },
    "system": {
        "title": "💻 Системные ошибки",
        "icon": "💻",
        "categories": {
            "slow": {
                "title": "Медленная работа",
                "steps": [
                    "Проверьте загрузку процессора и памяти",
                    "Закройте неиспользуемые программы",
                    "Проведите очистку диска",
                    "Проверьте на вирусы"
                ],
                "additional": "Рекомендуется регулярная дефрагментация диска",
                "priority": "Средний"
            },
            "blue_screen": {
                "title": "Синий экран",
                "steps": [
                    "Запишите код ошибки",
                    "Обновите драйверы",
                    "Проверьте температуру компонентов",
                    "Запустите проверку памяти"
                ],
                "additional": "Если проблема повторяется, обратитесь к специалисту",
                "priority": "Высокий"
            }
        }
    },
    "mobile": {
        "title": "📱 Мобильные устройства",
        "icon": "📱",
        "categories": {
            "battery": {
                "title": "Батарея",
                "steps": [
                    "Проверьте энергоемкие приложения",
                    "Отключите неиспользуемые функции",
                    "Проверьте здоровье батареи",
                    "Выполните калибровку батареи"
                ],
                "additional": "Рекомендуется замена батареи при емкости ниже 80%",
                "priority": "Средний"
            },
            "performance": {
                "title": "Производительность",
                "steps": [
                    "Очистите кэш",
                    "Удалите неиспользуемые приложения",
                    "Проверьте доступное место",
                    "Выполните сброс настроек"
                ],
                "additional": "Регулярно обновляйте систему и приложения",
                "priority": "Средний"
            }
        }
    },
    "other": {
        "title": "🔧 Другое",
        "icon": "🔧",
        "categories": {
            "other": {
                "title": "Другая проблема",
                "steps": [
                    "Опишите вашу проблему максимально подробно",
                    "Укажите, что вы уже пробовали сделать",
                    "Добавьте любую дополнительную информацию"
                ],
                "additional": "Мы рассмотрим вашу проблему в индивидуальном порядке",
                "priority": "Средний"
            }
        }
    }
}

# Класс для управления подключением к базе данных
class DatabaseConnection:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.max_retries = 3
        self.retry_delay = 0.1  # 100ms

    def __enter__(self):
        for attempt in range(self.max_retries):
            try:
                self.conn = sqlite3.connect(self.db_name, timeout=5.0)  # Add 5 second timeout
                self.cursor = self.conn.cursor()
                return self.cursor
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                raise
            except Exception as e:
                raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                try:
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"Error committing transaction: {e}")
                    self.conn.rollback()
            else:
                try:
                    self.conn.rollback()
                except Exception as e:
                    logger.error(f"Error rolling back transaction: {e}")
            try:
                self.conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

# Инициализация базы данных
def init_database():
    with DatabaseConnection("support_bot.db") as cursor:
        # Таблица пользователей
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP,
            requests_count INTEGER DEFAULT 0,
            is_banned BOOLEAN DEFAULT 0,
            rating REAL DEFAULT 0,
            solved_issues INTEGER DEFAULT 0,
            avg_response_time INTEGER DEFAULT 0
        )
        """)

        # Таблица заявок
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            user_id INTEGER,
            category TEXT,
            problem TEXT,
            status TEXT DEFAULT 'Открыто',
            priority TEXT DEFAULT 'Средний',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_update TIMESTAMP,
            assigned_to INTEGER,
            response_time INTEGER,
            satisfaction_rating INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # Добавляем недостающие колонки, если они не существуют
        try:
            cursor.execute("ALTER TABLE requests ADD COLUMN response_time INTEGER")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

        try:
            cursor.execute("ALTER TABLE requests ADD COLUMN satisfaction_rating INTEGER")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

        # Таблица сообщений заявки
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            sender_id INTEGER,
            message_text TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_internal BOOLEAN DEFAULT 0,
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
        """)

        # Таблица отзывов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

        # Таблица уведомлений
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)

# Инициализация бота
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info("Bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    print(f"❌ Ошибка инициализации бота: {e}")
    sys.exit(1)

# Функция для создания клавиатуры с категориями проблем
def get_problems_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for category_id, category_data in problems.items():
        markup.add(types.InlineKeyboardButton(
            f"{category_data['icon']} {category_data['title']}",
            callback_data=f"cat_{category_id}"
        ))
    markup.add(types.InlineKeyboardButton("📞 Связаться с поддержкой", callback_data="support"))
    markup.add(types.InlineKeyboardButton("📊 Мои заявки", callback_data="my_requests"))
    markup.add(types.InlineKeyboardButton("ℹ️ Помощь", callback_data="help"))
    return markup

# Функция для создания админ-клавиатуры
def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💬 Чат заявок", callback_data="admin_tickets_chat"),
        types.InlineKeyboardButton("📋 Все заявки", callback_data="admin_all_requests")
    )
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
        types.InlineKeyboardButton("🔔 Уведомления", callback_data="admin_notifications")
    )
    markup.add(
        types.InlineKeyboardButton("📈 Аналитика", callback_data="admin_analytics")
    )
    return markup

# Функция для создания клавиатуры с приоритетами
def get_priority_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for priority, level in CONFIG["PRIORITY_LEVELS"].items():
        markup.add(types.InlineKeyboardButton(
            f"{'🔴' if level > 2 else '🟡' if level > 1 else '🟢'} {priority}",
            callback_data=f"priority_{priority}"
        ))
    return markup

# Функция для создания клавиатуры с оценками
def get_rating_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=5)
    for i in range(1, 6):
        markup.add(types.InlineKeyboardButton(
            "⭐" * i,
            callback_data=f"rate_{i}"
        ))
    return markup

# Функция для отправки уведомления
def send_notification(user_id: int, message: str):
    try:
        for attempt in range(3):  # Try up to 3 times
            try:
                with DatabaseConnection("support_bot.db") as cursor:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, message)
                        VALUES (?, ?)
                    """, (user_id, message))
                    break  # If successful, break the retry loop
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                raise
            except Exception as e:
                raise
        
        bot.send_message(user_id, f"🔔 {message}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        # Don't re-raise the exception to prevent breaking the main flow

# Функция для автоматического закрытия неактивных заявок
def auto_close_inactive_requests():
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT r.ticket_id, r.user_id, r.problem
                FROM requests r
                WHERE r.status = 'Открыто'
                AND r.last_update < datetime('now', ?)
            """, (f"-{CONFIG['AUTO_CLOSE_HOURS']} hours",))
            
            inactive_requests = cursor.fetchall()
            
            for ticket_id, user_id, problem in inactive_requests:
                cursor.execute("""
                    UPDATE requests
                    SET status = 'Закрыто',
                        last_update = CURRENT_TIMESTAMP
                    WHERE ticket_id = ?
                """, (ticket_id,))
                
                send_notification(
                    user_id,
                    f"Ваша заявка #{ticket_id} была автоматически закрыта из-за неактивности."
                )
                
                logger.info(f"Auto-closed request {ticket_id}")
    except Exception as e:
        logger.error(f"Error in auto_close_inactive_requests: {e}")

# Функция для обновления статистики пользователя
def update_user_stats(user_id: int):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            # Обновление количества решенных проблем
            cursor.execute("""
                UPDATE users
                SET solved_issues = (
                    SELECT COUNT(*)
                    FROM requests
                    WHERE user_id = ?
                    AND status = 'Решено'
                )
                WHERE user_id = ?
            """, (user_id, user_id))
            
            # Обновление среднего времени ответа
            cursor.execute("""
                UPDATE users
                SET avg_response_time = (
                    SELECT AVG(response_time)
                    FROM requests
                    WHERE user_id = ?
                    AND response_time IS NOT NULL
                )
                WHERE user_id = ?
            """, (user_id, user_id))
            
            # Обновление рейтинга
            cursor.execute("""
                UPDATE users
                SET rating = (
                    SELECT AVG(satisfaction_rating)
                    FROM requests
                    WHERE user_id = ?
                    AND satisfaction_rating IS NOT NULL
                )
                WHERE user_id = ?
            """, (user_id, user_id))
    except Exception as e:
        logger.error(f"Error in update_user_stats: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    try:
        # Регистрация пользователя
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            ))

        # Проверка на админа и его режим
        if message.from_user.id == ADMIN_ID and admin_mode.get(message.from_user.id, False):
            welcome_text = (
                f"👋 Здравствуйте, администратор {message.from_user.first_name}!\n\n"
                "Вы находитесь в панели администратора. Выберите действие:"
            )
            bot.send_message(message.chat.id, welcome_text, reply_markup=get_admin_keyboard())
            return

        welcome_text = (
            f"👋 Здравствуйте, {message.from_user.first_name or 'уважаемый пользователь'}!\n\n"
            "Я ваш виртуальный помощник по технической поддержке. "
            "Здесь вы можете найти решения распространенных проблем или создать заявку в поддержку.\n\n"
            f"🕐 Время работы поддержки: {CONFIG['SUPPORT_HOURS']['start']}-{CONFIG['SUPPORT_HOURS']['end']} (МСК)\n"
            "⚡️ Среднее время ответа: 15 минут\n\n"
            "Выберите категорию проблемы из списка ниже:"
        )

        bot.send_message(message.chat.id, welcome_text, reply_markup=get_problems_keyboard())
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(commands=['admin'])
def enter_admin_mode(message):
    try:
        if message.from_user.id == ADMIN_ID:
            admin_mode[message.from_user.id] = True
            logger.info(f"Admin {message.from_user.id} entered admin mode")
            bot.send_message(
                message.chat.id,
                "🔑 Вы вошли в режим администратора.\n"
                "Используйте /exit_admin для выхода из режима администратора.",
                reply_markup=get_admin_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ У вас нет прав администратора."
            )
    except Exception as e:
        logger.error(f"Error in enter_admin_mode: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(commands=['exit_admin'])
def exit_admin_mode(message):
    try:
        if message.from_user.id == ADMIN_ID:
            admin_mode[message.from_user.id] = False
            logger.info(f"Admin {message.from_user.id} exited admin mode")
            bot.send_message(
                message.chat.id,
                "🔒 Вы вышли из режима администратора.\n"
                "Используйте /admin для входа в режим администратора.",
                reply_markup=get_problems_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ У вас нет прав администратора."
            )
    except Exception as e:
        logger.error(f"Error in exit_admin_mode: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(commands=['help'])
def show_help(message):
    try:
        help_text = (
            "ℹ️ Справка по использованию бота:\n\n"
            "📝 Основные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "/feedback - Оставить отзыв\n\n"
            "📋 Как создать заявку:\n"
            "1. Выберите категорию проблемы\n"
            "2. Опишите проблему подробно\n"
            "3. Укажите приоритет\n"
            "4. Дождитесь ответа поддержки\n\n"
            "📊 Статистика заявок:\n"
            "- Вы можете отслеживать статус заявок\n"
            "- Получать уведомления об ответах\n"
            "- Оценивать качество поддержки\n\n"
            "❓ Частые вопросы:\n"
            "Q: Сколько ждать ответа?\n"
            "A: Среднее время ответа - 15 минут\n\n"
            "Q: Как отменить заявку?\n"
            "A: В разделе 'Мои заявки' выберите заявку и нажмите 'Отменить'\n\n"
            "📞 Контакты поддержки:\n"
            "Если у вас срочный вопрос, свяжитесь с нами напрямую."
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📞 Связаться с поддержкой", callback_data="support"))
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))

        bot.send_message(message.chat.id, help_text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in show_help: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

@bot.message_handler(commands=['feedback'])
def start_feedback(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT r.ticket_id, r.problem
                FROM requests r
                WHERE r.user_id = ?
                AND r.status = 'Решено'
                AND r.satisfaction_rating IS NULL
                ORDER BY r.created_at DESC
            """, (message.from_user.id,))
            
            solved_requests = cursor.fetchall()
            
            if not solved_requests:
                bot.send_message(
                    message.chat.id,
                    "📭 У вас нет решенных заявок для оценки."
                )
                return
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ticket_id, problem in solved_requests:
                markup.add(types.InlineKeyboardButton(
                    f"#{ticket_id} - {problem[:30]}...",
                    callback_data=f"rate_request_{ticket_id}"
                ))
            
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                "📝 Выберите заявку для оценки:",
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in start_feedback: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

def show_request_details(message, ticket_id):
    try:
        logger.info(f"Showing details for ticket {ticket_id}")
        
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT problem, status, created_at, last_update, user_id, category, priority
                FROM requests
                WHERE ticket_id = ?
            """, (ticket_id,))
            request = cursor.fetchone()

            if not request:
                bot.send_message(
                    message.chat.id,
                    "❌ Заявка не найдена."
                )
                return

            problem, status, created_at, last_update, user_id, category, priority = request

            cursor.execute("""
                SELECT sender_id, message_text, sent_at
                FROM request_messages
                WHERE request_id = (
                    SELECT id FROM requests WHERE ticket_id = ?
                )
                ORDER BY sent_at
            """, (ticket_id,))
            messages = cursor.fetchall()

            text = (
                f"📋 Заявка #{ticket_id}\n\n"
                f"📝 Проблема:\n{problem}\n\n"
                f"📊 Статус: {status}\n"
                f"📅 Создано: {created_at}\n"
                f"📦 Категория: {category}\n"
                f"⚡️ Приоритет: {priority}\n"
            )
            if last_update:
                text += f"🔄 Последнее обновление: {last_update}\n\n"

            if messages:
                text += "📨 История сообщений:\n"
                for msg in messages:
                    sender_id, message_text, sent_at = msg
                    text += f"\n{sent_at}:\n{message_text}\n"

            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # Кнопки для пользователя
            if message.chat.id == user_id:
                if status == 'Открыто':
                    markup.add(
                        types.InlineKeyboardButton("📝 Добавить комментарий", callback_data=f"comment_{ticket_id}"),
                        types.InlineKeyboardButton("✅ Решено и закрыть", callback_data=f"resolve_{ticket_id}"),
                        types.InlineKeyboardButton("❌ Отменить заявку", callback_data=f"cancel_{ticket_id}")
                    )
                elif status == 'Решено':
                    markup.add(
                        types.InlineKeyboardButton("⭐ Оценить решение", callback_data=f"rate_{ticket_id}"),
                        types.InlineKeyboardButton("✅ Закрыть заявку", callback_data=f"close_{ticket_id}")
                    )
            # Кнопки для администратора
            elif message.chat.id == ADMIN_ID:
                if status == 'Открыто':
                    markup.add(
                        types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}"),
                        types.InlineKeyboardButton("✅ Решить", callback_data=f"admin_resolve_{ticket_id}"),
                        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{ticket_id}")
                    )
                elif status == 'Решено':
                    markup.add(
                        types.InlineKeyboardButton("✅ Закрыть заявку", callback_data=f"admin_close_{ticket_id}"),
                        types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}")
                    )
            
            markup.add(types.InlineKeyboardButton("◀️ Назад к списку", callback_data="my_requests"))

            try:
                bot.send_message(
                    message.chat.id,
                    text,
                    reply_markup=markup
                )
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                bot.send_message(
                    message.chat.id,
                    "❌ Не удалось отобразить детали заявки. Пожалуйста, попробуйте позже."
                )
    except Exception as e:
        logger.error(f"Error in show_request_details: {e}", exc_info=True)
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отображении деталей заявки. Пожалуйста, попробуйте позже."
        )

def resolve_issue(call):
    try:
        ticket_id = call.data.split("_")[1]
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                UPDATE requests
                SET status = 'Решено',
                    last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (ticket_id,))
            
            if cursor.rowcount > 0:
                # Получаем информацию о заявке
                cursor.execute("""
                    SELECT user_id, problem
                    FROM requests
                    WHERE ticket_id = ?
                """, (ticket_id,))
                user_id, problem = cursor.fetchone()
                
                # Отправляем уведомление пользователю
                send_notification(
                    user_id,
                    f"✅ Ваша заявка #{ticket_id} решена!\n\n"
                    f"Проблема: {problem}\n\n"
                    "Пожалуйста, оцените качество решения."
                )
                
                bot.answer_callback_query(
                    call.id,
                    "✅ Заявка помечена как решенная"
                )
                
                # Показываем обновленные детали заявки
                show_request_details(call.message, ticket_id)
            else:
                bot.answer_callback_query(
                    call.id,
                    "❌ Не удалось обновить статус заявки"
                )
    except Exception as e:
        logger.error(f"Error in resolve_issue: {e}")
        bot.answer_callback_query(
            call.id,
            "❌ Произошла ошибка при обновлении статуса"
        )

def close_request(message, ticket_id, is_admin=False):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                UPDATE requests
                SET status = 'Закрыто',
                    last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (ticket_id,))

            if cursor.rowcount > 0:
                # Получаем информацию о заявке
                cursor.execute("""
                    SELECT user_id, problem
                    FROM requests
                    WHERE ticket_id = ?
                """, (ticket_id,))
                user_id, problem = cursor.fetchone()

                # Отправляем уведомление пользователю
                if not is_admin:
                    send_notification(
                        user_id,
                        f"✅ Ваша заявка #{ticket_id} была закрыта.\n\n"
                        f"Проблема: {problem}\n\n"
                        "Спасибо за использование нашего сервиса!"
                    )
                else:
                    send_notification(
                        user_id,
                        f"✅ Администратор закрыл вашу заявку #{ticket_id}.\n\n"
                        f"Проблема: {problem}\n\n"
                        "Спасибо за использование нашего сервиса!"
                    )

                bot.send_message(
                    message.chat.id,
                    f"✅ Заявка #{ticket_id} успешно закрыта."
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Не удалось закрыть заявку. Возможно, она уже закрыта или не существует."
                )
    except Exception as e:
        logger.error(f"Error in close_request: {e}", exc_info=True)
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при закрытии заявки."
        )

def start_rating(message, ticket_id):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT problem
                FROM requests
                WHERE ticket_id = ?
            """, (ticket_id,))
            problem = cursor.fetchone()[0]

        text = (
            f"📝 Заявка #{ticket_id}\n\n"
            f"Проблема: {problem}\n\n"
            "Пожалуйста, оцените качество решения вашей проблемы:"
        )

        markup = types.InlineKeyboardMarkup(row_width=5)
        for i in range(1, 6):
            markup.add(types.InlineKeyboardButton(
                "⭐" * i,
                callback_data=f"rate_{ticket_id}_{i}"
            ))
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data=f"request_{ticket_id}"))

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in start_rating: {e}", exc_info=True)
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при запуске оценки."
        )

def process_rating(call):
    try:
        # Handle both rate_request_ and rate_ callbacks
        if call.data.startswith("rate_request_"):
            ticket_id = call.data.split("_")[2]
            start_rating(call.message, ticket_id)
            return
            
        # Handle actual rating submission
        _, ticket_id, rating = call.data.split("_")
        rating = int(rating)

        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                UPDATE requests
                SET satisfaction_rating = ?,
                    last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (rating, ticket_id))

            # Обновляем статистику пользователя
            update_user_stats(call.from_user.id)

        bot.answer_callback_query(
            call.id,
            f"✅ Спасибо за вашу оценку! ({'⭐' * rating})"
        )

        # Показываем детали заявки снова
        show_request_details(call.message, ticket_id)
    except Exception as e:
        logger.error(f"Error in process_rating: {e}", exc_info=True)
        bot.answer_callback_query(
            call.id,
            "❌ Произошла ошибка при сохранении оценки."
        )

def show_problem_solution(message, category_id, subcategory_id):
    try:
        if category_id not in problems or subcategory_id not in problems[category_id]['categories']:
            bot.send_message(
                message.chat.id,
                "❌ Проблема не найдена."
            )
            return
        
        subcategory = problems[category_id]['categories'][subcategory_id]
        text = (
            f"🔍 {subcategory['title']}\n\n"
            "📋 Шаги решения:\n"
        )
        
        for i, step in enumerate(subcategory['steps'], 1):
            text += f"{i}. {step}\n"
        
        if 'additional' in subcategory:
            text += f"\n💡 Дополнительно:\n{subcategory['additional']}\n"
        
        text += f"\n⚡️ Приоритет: {subcategory['priority']}"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(
            "📝 Создать заявку",
            callback_data=f"new_ticket_cat_{category_id}"
        ))
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category_id}"))
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_problem_solution: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отображении решения."
        )

def show_admin_notifications(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT id, message, created_at, is_read
                FROM notifications
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            notifications = cursor.fetchall()
            
            if not notifications:
                text = "📭 Нет уведомлений"
            else:
                text = "📢 Последние уведомления:\n\n"
                for n_id, message, created_at, is_read in notifications:
                    status = "✅" if is_read else "❌"
                    text += f"{status} {created_at}\n{message}\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_admin_notifications: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении уведомлений."
        )

def show_users_list(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, 
                       requests_count, rating, solved_issues, avg_response_time
                FROM users
                ORDER BY requests_count DESC
            """)
            
            users = cursor.fetchall()
            
            if not users:
                text = "👥 Нет зарегистрированных пользователей"
            else:
                text = "👥 Список пользователей:\n\n"
                for user in users:
                    user_id, username, first_name, last_name, requests_count, rating, solved_issues, avg_time = user
                    text += (
                        f"👤 {first_name} {last_name or ''}\n"
                        f"📱 @{username or 'нет'}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📊 Заявок: {requests_count}\n"
                        f"⭐ Рейтинг: {rating or 'нет'}\n"
                        f"✅ Решено: {solved_issues}\n"
                        f"⏱ Среднее время ответа: {avg_time or 'нет'} мин\n\n"
                    )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_users_list: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении списка пользователей."
        )

def show_all_requests(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT r.ticket_id, r.problem, r.status, r.created_at, r.priority,
                       u.username, u.first_name, u.last_name
                FROM requests r
                JOIN users u ON r.user_id = u.user_id
                ORDER BY r.created_at DESC
                LIMIT 50
            """)
            
            requests = cursor.fetchall()
            
            if not requests:
                text = "📭 Нет заявок"
            else:
                text = "📋 Все заявки:\n\n"
                for req in requests:
                    ticket_id, problem, status, created_at, priority, username, first_name, last_name = req
                    text += (
                        f"🔹 #{ticket_id}\n"
                        f"👤 {first_name} {last_name or ''} (@{username or 'нет'})\n"
                        f"📝 {problem[:30]}...\n"
                        f"📊 Статус: {status}\n"
                        f"📅 Создано: {created_at}\n"
                        f"⚡️ Приоритет: {priority}\n\n"
                    )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_all_requests: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении списка заявок."
        )

def show_admin_stats(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'Решено' THEN 1 ELSE 0 END) as solved_requests,
                    AVG(response_time) as avg_response_time,
                    AVG(satisfaction_rating) as avg_rating
                FROM requests
            """)
            stats = cursor.fetchone()
            
            # Статистика по категориям
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM requests
                GROUP BY category
                ORDER BY count DESC
            """)
            categories = cursor.fetchall()
            
            text = (
                "📊 Статистика бота:\n\n"
                f"📝 Всего заявок: {stats[0]}\n"
                f"✅ Решено: {stats[1]}\n"
                f"⏱ Среднее время ответа: {stats[2] or 'нет'} мин\n"
                f"⭐ Средняя оценка: {stats[3] or 'нет'}\n\n"
                "📈 Статистика по категориям:\n"
            )
            
            for category, count in categories:
                text += f"• {category}: {count}\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_admin_stats: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении статистики."
        )

def show_admin_settings(message):
    try:
        text = (
            "⚙️ Настройки бота:\n\n"
            f"🕐 Автоматическое закрытие: {CONFIG['AUTO_CLOSE_HOURS']} ч\n"
            f"📝 Макс. длина сообщения: {CONFIG['MAX_MESSAGE_LENGTH']} символов\n"
            f"⭐ Порог оценки: {CONFIG['RATING_THRESHOLD']}\n"
            f"🕐 Время работы: {CONFIG['SUPPORT_HOURS']['start']}-{CONFIG['SUPPORT_HOURS']['end']} (МСК)\n"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_admin_settings: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении настроек."
        )

def cancel_request(message, ticket_id=None):
    try:
        # Удаляем временные данные пользователя
        if message.chat.id in temp_data:
            del temp_data[message.chat.id]
        
        # Если это отмена создания новой заявки
        if ticket_id is None:
            bot.send_message(
                message.chat.id,
                "❌ Создание заявки отменено.",
                reply_markup=get_problems_keyboard()
            )
            return
        
        # Если это отмена существующей заявки
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                UPDATE requests
                SET status = 'Отменено',
                    last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
                AND user_id = ?
            """, (ticket_id, message.chat.id))
            
            if cursor.rowcount > 0:
                bot.send_message(
                    message.chat.id,
                    f"✅ Заявка #{ticket_id} отменена.",
                    reply_markup=get_problems_keyboard()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Не удалось отменить заявку. Возможно, она уже закрыта или не существует.",
                    reply_markup=get_problems_keyboard()
                )
    except Exception as e:
        logger.error(f"Error in cancel_request: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отмене заявки.",
            reply_markup=get_problems_keyboard()
        )

def show_admin_analytics(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            # Аналитика по времени
            cursor.execute("""
                SELECT 
                    strftime('%H', created_at) as hour,
                    COUNT(*) as count
                FROM requests
                GROUP BY hour
                ORDER BY hour
            """)
            hourly_stats = cursor.fetchall()
            
            # Аналитика по дням недели
            cursor.execute("""
                SELECT 
                    strftime('%w', created_at) as weekday,
                    COUNT(*) as count
                FROM requests
                GROUP BY weekday
                ORDER BY weekday
            """)
            daily_stats = cursor.fetchall()
            
            # Аналитика по приоритетам
            cursor.execute("""
                SELECT 
                    priority,
                    COUNT(*) as count,
                    AVG(response_time) as avg_time
                FROM requests
                GROUP BY priority
                ORDER BY count DESC
            """)
            priority_stats = cursor.fetchall()
            
            text = "📊 Аналитика бота:\n\n"
            
            # Часовой график
            text += "🕐 Распределение заявок по часам:\n"
            for hour, count in hourly_stats:
                text += f"{hour}:00 - {count} заявок\n"
            
            # Дневной график
            weekdays = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
            text += "\n📅 Распределение по дням недели:\n"
            for weekday, count in daily_stats:
                text += f"{weekdays[int(weekday)]} - {count} заявок\n"
            
            # Статистика по приоритетам
            text += "\n⚡️ Статистика по приоритетам:\n"
            for priority, count, avg_time in priority_stats:
                text += (
                    f"{priority}:\n"
                    f"• Заявок: {count}\n"
                    f"• Среднее время ответа: {avg_time or 'нет'} мин\n"
                )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_admin_analytics: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении аналитики."
        )

def start_admin_reply(message, ticket_id):
    try:
        msg = bot.send_message(
            message.chat.id,
            "Введите ваш ответ на заявку:"
        )
        bot.register_next_step_handler(msg, process_admin_reply, ticket_id)
    except Exception as e:
        logger.error(f"Error in start_admin_reply: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при начале ответа на заявку."
        )

def process_admin_reply(message, ticket_id):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            # Получаем информацию о заявке
            cursor.execute("""
                SELECT user_id, problem
                FROM requests
                WHERE ticket_id = ?
            """, (ticket_id,))
            user_id, problem = cursor.fetchone()
            
            # Сохраняем сообщение
            cursor.execute("""
                INSERT INTO request_messages (request_id, sender_id, message_text)
                VALUES (
                    (SELECT id FROM requests WHERE ticket_id = ?),
                    ?,
                    ?
                )
            """, (ticket_id, message.from_user.id, message.text))
            
            # Отправляем уведомление пользователю
            send_notification(
                user_id,
                f"📨 Получен ответ на вашу заявку #{ticket_id}:\n\n"
                f"{message.text}"
            )
            
            bot.send_message(
                message.chat.id,
                "✅ Ответ успешно отправлен пользователю."
            )
            
            # Показываем обновленные детали заявки
            show_request_details(message, ticket_id)
    except Exception as e:
        logger.error(f"Error in process_admin_reply: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отправке ответа."
        )

def start_admin_reject(message, ticket_id):
    try:
        msg = bot.send_message(
            message.chat.id,
            "Введите причину отклонения заявки:"
        )
        bot.register_next_step_handler(msg, process_admin_reject, ticket_id)
    except Exception as e:
        logger.error(f"Error in start_admin_reject: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отклонении заявки."
        )

def process_admin_reject(message, ticket_id):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            # Обновляем статус заявки
            cursor.execute("""
                UPDATE requests
                SET status = 'Отклонено',
                    last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (ticket_id,))
            
            # Получаем информацию о заявке
            cursor.execute("""
                SELECT user_id, problem
                FROM requests
                WHERE ticket_id = ?
            """, (ticket_id,))
            user_id, problem = cursor.fetchone()
            
            # Сохраняем сообщение с причиной
            cursor.execute("""
                INSERT INTO request_messages (request_id, sender_id, message_text)
                VALUES (
                    (SELECT id FROM requests WHERE ticket_id = ?),
                    ?,
                    ?
                )
            """, (ticket_id, message.from_user.id, f"Заявка отклонена. Причина: {message.text}"))
            
            # Отправляем уведомление пользователю
            send_notification(
                user_id,
                f"❌ Ваша заявка #{ticket_id} была отклонена.\n\n"
                f"Причина: {message.text}"
            )
            
            bot.send_message(
                message.chat.id,
                "✅ Заявка успешно отклонена."
            )
            
            # Показываем обновленные детали заявки
            show_request_details(message, ticket_id)
    except Exception as e:
        logger.error(f"Error in process_admin_reject: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отклонении заявки."
        )

def add_comment(message, ticket_id):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                INSERT INTO request_messages (request_id, sender_id, message_text)
                VALUES (
                    (SELECT id FROM requests WHERE ticket_id = ?),
                    ?,
                    ?
                )
            """, (ticket_id, message.from_user.id, message.text))
            
            # Обновляем время последнего обновления заявки
            cursor.execute("""
                UPDATE requests
                SET last_update = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (ticket_id,))
            
            bot.send_message(
                message.chat.id,
                "✅ Комментарий успешно добавлен."
            )
            
            # Показываем обновленные детали заявки
            show_request_details(message, ticket_id)
    except Exception as e:
        logger.error(f"Error in add_comment: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при добавлении комментария."
        )

def show_admin_tickets_chat(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT r.ticket_id, r.problem, r.status, r.created_at, 
                       u.username, u.first_name, u.last_name
                FROM requests r
                JOIN users u ON r.user_id = u.user_id
                WHERE r.status != 'Закрыто'
                ORDER BY 
                    CASE r.status
                        WHEN 'Открыто' THEN 1
                        WHEN 'Решено' THEN 2
                        ELSE 3
                    END,
                    r.created_at DESC
                LIMIT 10
            """)
            
            active_tickets = cursor.fetchall()
            
            if not active_tickets:
                bot.send_message(
                    message.chat.id,
                    "📭 Нет активных заявок",
                    reply_markup=get_admin_keyboard()
                )
                return
            
            text = "💬 Активные заявки:\n\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for ticket in active_tickets:
                ticket_id, problem, status, created_at, username, first_name, last_name = ticket
                status_emoji = {
                    'Открыто': '🆕',
                    'Решено': '✅',
                    'Отклонено': '❌'
                }.get(status, '❓')
                
                user_display = f"{first_name} {last_name or ''}" if first_name else f"@{username}" if username else "Неизвестный"
                
                button_text = (
                    f"{status_emoji} #{ticket_id} | {status}\n"
                    f"👤 {user_display}\n"
                    f"📝 {problem[:30]}..."
                )
                
                markup.add(types.InlineKeyboardButton(
                    button_text,
                    callback_data=f"admin_ticket_chat_{ticket_id}"
                ))
            
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_admin_tickets_chat: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении списка заявок."
        )

def show_admin_ticket_chat(message, ticket_id):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT r.problem, r.status, r.created_at, r.priority,
                       u.username, u.first_name, u.last_name, u.user_id
                FROM requests r
                JOIN users u ON r.user_id = u.user_id
                WHERE r.ticket_id = ?
            """, (ticket_id,))
            
            ticket_info = cursor.fetchone()
            if not ticket_info:
                bot.send_message(
                    message.chat.id,
                    "❌ Заявка не найдена."
                )
                return
            
            problem, status, created_at, priority, username, first_name, last_name, user_id = ticket_info
            
            # Получаем историю сообщений
            cursor.execute("""
                SELECT rm.sender_id, rm.message_text, rm.sent_at,
                       u.username, u.first_name, u.last_name
                FROM request_messages rm
                LEFT JOIN users u ON rm.sender_id = u.user_id
                WHERE rm.request_id = (SELECT id FROM requests WHERE ticket_id = ?)
                ORDER BY rm.sent_at
            """, (ticket_id,))
            
            messages = cursor.fetchall()
            
            # Формируем текст с информацией о заявке
            user_display = f"{first_name} {last_name or ''}" if first_name else f"@{username}" if username else "Неизвестный"
            
            text = (
                f"📋 Заявка #{ticket_id}\n\n"
                f"👤 Пользователь: {user_display}\n"
                f"📊 Статус: {status}\n"
                f"⚡️ Приоритет: {priority}\n"
                f"📅 Создано: {created_at}\n\n"
                f"📝 Проблема:\n{problem}\n\n"
            )
            
            if messages:
                text += "💬 История сообщений:\n"
                for msg in messages:
                    sender_id, msg_text, sent_at, s_username, s_first_name, s_last_name = msg
                    sender_display = (
                        "👨‍💼 Админ: " if sender_id == ADMIN_ID
                        else "👤 Пользователь: "
                    )
                    text += f"\n{sent_at}\n{sender_display}{msg_text}\n"
            
            # Создаем клавиатуру с действиями
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            if status == 'Открыто':
                markup.add(
                    types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}"),
                    types.InlineKeyboardButton("✅ Решено", callback_data=f"admin_resolve_{ticket_id}")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{ticket_id}")
                )
            elif status == 'Решено':
                markup.add(
                    types.InlineKeyboardButton("✅ Закрыть", callback_data=f"admin_close_{ticket_id}"),
                    types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}")
                )
            
            markup.add(types.InlineKeyboardButton("◀️ Назад к заявкам", callback_data="admin_tickets_chat"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_admin_ticket_chat: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отображении заявки."
        )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        logger.info(f"Received callback: {call.data} from user {call.from_user.id}")
        
        # Обработка админ-команд
        if call.from_user.id == ADMIN_ID:
            if call.data == "admin_tickets_chat":
                show_admin_tickets_chat(call.message)
                return
            elif call.data.startswith("admin_ticket_chat_"):
                ticket_id = call.data.split("_")[3]
                show_admin_ticket_chat(call.message, ticket_id)
                return
            elif call.data == "admin_all_requests":
                show_all_requests(call.message)
                return
            elif call.data == "admin_stats":
                show_admin_stats(call.message)
                return
            elif call.data == "admin_users":
                show_users_list(call.message)
                return
            elif call.data == "admin_settings":
                show_admin_settings(call.message)
                return
            elif call.data == "admin_notifications":
                show_admin_notifications(call.message)
                return
            elif call.data == "admin_analytics":
                show_admin_analytics(call.message)
                return
            elif call.data.startswith("admin_reply_"):
                ticket_id = call.data.split("_")[2]
                start_admin_reply(call.message, ticket_id)
                return
            elif call.data.startswith("admin_resolve_"):
                ticket_id = call.data.split("_")[2]
                resolve_issue(call)
                return
            elif call.data.startswith("admin_reject_"):
                ticket_id = call.data.split("_")[2]
                start_admin_reject(call.message, ticket_id)
                return
            elif call.data.startswith("admin_close_"):
                ticket_id = call.data.split("_")[2]
                close_request(call.message, ticket_id, is_admin=True)
                return
        
        # Обработка обычных команд
        if call.data == "help":
            show_help(call.message)
        elif call.data == "cancel_new_ticket":
            cancel_request(call.message)
        elif call.data.startswith("new_ticket_cat_"):
            category_id = call.data.split("_")[3]
            # Генерация уникального ID заявки
            ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Сохранение временных данных
            temp_data[call.message.chat.id] = {
                'ticket_id': ticket_id,
                'category': category_id
            }
            
            # Запрос описания проблемы
            msg = bot.send_message(
                call.message.chat.id,
                "📝 Опишите вашу проблему максимально подробно:"
            )
            bot.register_next_step_handler(msg, process_problem_description)
        elif call.data.startswith("cat_"):
            category_id = call.data[4:]
            show_category_problems(call.message, category_id)
        elif call.data.startswith("subcat_"):
            try:
                _, category_id, subcategory_id = call.data.split("_", 2)
                show_problem_solution(call.message, category_id, subcategory_id)
            except ValueError:
                logger.error(f"Invalid subcategory format: {call.data}")
                bot.answer_callback_query(call.id, "❌ Неверный формат данных")
        elif call.data == "support":
            start_support_request(call.message)
        elif call.data == "my_requests":
            show_user_requests(call.message)
        elif call.data == "back_to_main":
            try:
                if call.from_user.id == ADMIN_ID and admin_mode.get(call.from_user.id, False):
                    bot.edit_message_text(
                        "Выберите действие:",
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    bot.edit_message_text(
                        "Выберите категорию проблемы:",
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=get_problems_keyboard()
                    )
            except Exception as e:
                logger.error(f"Error in back_to_main: {e}")
                bot.answer_callback_query(call.id, "❌ Не удалось вернуться в главное меню")
        elif call.data.startswith("request_"):
            ticket_id = call.data[8:]
            show_request_details(call.message, ticket_id)
        elif call.data.startswith("resolve_"):
            resolve_issue(call)
        elif call.data.startswith("comment_"):
            ticket_id = call.data[8:]
            try:
                with DatabaseConnection("support_bot.db") as cursor:
                    cursor.execute("SELECT id FROM requests WHERE ticket_id = ?", (ticket_id,))
                    if cursor.fetchone():
                        msg = bot.send_message(
                            call.message.chat.id,
                            "Введите ваш комментарий к заявке:"
                        )
                        bot.register_next_step_handler(msg, add_comment, ticket_id)
                    else:
                        bot.answer_callback_query(call.id, "❌ Заявка не найдена")
            except Exception as e:
                logger.error(f"Error in comment handler: {e}")
                bot.answer_callback_query(call.id, "❌ Не удалось добавить комментарий")
        elif call.data.startswith("cancel_"):
            ticket_id = call.data[7:]
            cancel_request(call.message, ticket_id)
        elif call.data.startswith("close_"):
            ticket_id = call.data[6:]
            close_request(call.message, ticket_id)
        elif call.data.startswith("rate_"):
            if "_" in call.data[5:]:  # Если это оценка конкретной заявки
                process_rating(call)
            else:  # Если это запуск оценки
                ticket_id = call.data[5:]
                start_rating(call.message, ticket_id)
        else:
            logger.warning(f"Unknown callback data: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
    except Exception as e:
        logger.error(f"Error in callback handler: {str(e)}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.")
        except Exception as inner_e:
            logger.error(f"Error sending error message: {inner_e}")

def process_problem_description(message):
    try:
        if message.chat.id not in temp_data:
            bot.send_message(
                message.chat.id,
                "❌ Произошла ошибка. Пожалуйста, начните создание заявки заново.",
                reply_markup=get_problems_keyboard()
            )
            return

        ticket_data = temp_data[message.chat.id]
        
        # Создаем новую заявку в базе данных
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                INSERT INTO requests (ticket_id, user_id, category, problem, created_at, last_update)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (ticket_data['ticket_id'], message.chat.id, ticket_data['category'], message.text))

        # Отправляем уведомление администратору
        admin_notification = (
            f"📝 Новая заявка #{ticket_data['ticket_id']}\n"
            f"От: {message.from_user.first_name} {message.from_user.last_name or ''} (@{message.from_user.username or 'нет'})\n"
            f"Категория: {problems[ticket_data['category']]['title']}\n\n"
            f"Проблема:\n{message.text}"
        )
        bot.send_message(ADMIN_ID, admin_notification)

        # Отправляем подтверждение пользователю
        confirmation = (
            f"✅ Ваша заявка #{ticket_data['ticket_id']} успешно создана!\n\n"
            "Мы уведомим вас, когда появится ответ от службы поддержки."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Мои заявки", callback_data="my_requests"))
        markup.add(types.InlineKeyboardButton("◀️ На главную", callback_data="back_to_main"))
        
        bot.send_message(message.chat.id, confirmation, reply_markup=markup)

        # Очищаем временные данные
        del temp_data[message.chat.id]

    except Exception as e:
        logger.error(f"Error in process_problem_description: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при создании заявки. Пожалуйста, попробуйте позже.",
            reply_markup=get_problems_keyboard()
        )

def signal_handler(sig, frame):
    print('\n🛑 Останавливаю бота...')
    logger.info("Bot stopping by interrupt signal")
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def show_user_requests(message):
    try:
        with DatabaseConnection("support_bot.db") as cursor:
            cursor.execute("""
                SELECT ticket_id, problem, status, created_at, priority
                FROM requests
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (message.chat.id,))
            
            requests = cursor.fetchall()
            
            if not requests:
                bot.send_message(
                    message.chat.id,
                    "📭 У вас пока нет заявок."
                )
                return
            
            text = "📋 Ваши заявки:\n\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for ticket_id, problem, status, created_at, priority in requests:
                text += (
                    f"🔹 #{ticket_id}\n"
                    f"📝 {problem[:30]}...\n"
                    f"📊 Статус: {status}\n"
                    f"📅 Создано: {created_at}\n"
                    f"⚡️ Приоритет: {priority}\n\n"
                )
                markup.add(types.InlineKeyboardButton(
                    f"#{ticket_id} - {problem[:30]}...",
                    callback_data=f"request_{ticket_id}"
                ))
            
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                message.chat.id,
                text,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in show_user_requests: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при получении списка заявок."
        )

def show_category_problems(message, category_id):
    try:
        if category_id not in problems:
            bot.send_message(
                message.chat.id,
                "❌ Категория не найдена."
            )
            return
        
        category = problems[category_id]
        text = f"{category['icon']} {category['title']}\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for subcategory_id, subcategory_data in category['categories'].items():
            markup.add(types.InlineKeyboardButton(
                subcategory_data['title'],
                callback_data=f"subcat_{category_id}_{subcategory_id}"
            ))
        
        markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"))
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_category_problems: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отображении категории."
        )

def start_support_request(message):
    try:
        # Генерация уникального ID заявки
        ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Сохранение временных данных
        temp_data[message.chat.id] = {
            'ticket_id': ticket_id,
            'step': 'category'
        }
        
        text = (
            "📝 Создание новой заявки\n\n"
            "Пожалуйста, выберите категорию проблемы:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for category_id, category_data in problems.items():
            markup.add(types.InlineKeyboardButton(
                f"{category_data['icon']} {category_data['title']}",
                callback_data=f"new_ticket_cat_{category_id}"
            ))
        
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_new_ticket"))
        
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in start_support_request: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при создании заявки."
        )

if __name__ == "__main__":
    try:
        init_database()
        logger.info("Bot started successfully")
        print("✅ Бот запущен. Нажмите Ctrl+C для остановки")
        
        # Запуск периодических задач
        def periodic_tasks():
            while True:
                try:
                    auto_close_inactive_requests()
                    time.sleep(3600)  # Проверка каждый час
                except Exception as e:
                    logger.error(f"Error in periodic tasks: {e}")
                    time.sleep(60)
        
        import threading
        periodic_thread = threading.Thread(target=periodic_tasks)
        periodic_thread.daemon = True
        periodic_thread.start()
        
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        bot.stop_polling()
