import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import sqlite3
import schedule
import time
import threading

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tasks
                 (id INTEGER PRIMARY KEY, time TEXT, task TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_tasks
                 (id INTEGER PRIMARY KEY, day TEXT, task TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_tasks
                 (id INTEGER PRIMARY KEY, day INTEGER, task TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS special_tasks
                 (id INTEGER PRIMARY KEY, type TEXT, task TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY, key TEXT, value TEXT)''')
    
    # Стандартные задачи
    c.execute("SELECT COUNT(*) FROM daily_tasks")
    if c.fetchone()[0] == 0:
        # Ежедневные задачи
        daily_tasks = [
            ("07:00", "Уточнение задач оперативному составу штаба полка"),
            ("07:30", "Получение задач от командира полка"),
            ("09:00", "Отработка текущих задач"),
            ("16:00", "Работа со входящей документацией"),
            ("17:50", "Прием доклада от начальников служб, начальников отделений"),
            ("18:00", "Видеоконференция НШ 18ОА"),
            ("19:20", "Осуществление смены дежурных по КП, ГОП, проверка заданий стоящих на контроле"),
            ("20:00", "Заслушивание командиров (НШ) подразделений о выполненных мероприятиях, готовность к ночным действиям")
        ]
        
        for time, task in daily_tasks:
            c.execute("INSERT INTO daily_tasks (time, task) VALUES (?, ?)", (time, task))
        
        # Настройки
        c.execute("INSERT INTO settings (key, value) VALUES ('send_time', '17:45')")
    
    conn.commit()
    conn.close()

# Получение задач на дату
def get_tasks_for_date(date):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    day_names = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
    day_name = day_names[date.weekday()]
    day_number = date.day
    
    message = f"🎖️ ЗАДАЧИ НА {date.strftime('%d.%m.%Y')} ({day_name.upper()})\n\n"
    
    # Ежедневные задачи
    c.execute("SELECT time, task FROM daily_tasks ORDER BY time")
    daily_tasks = c.fetchall()
    
    message += "📅 ЕЖЕДНЕВНЫЕ:\n"
    for time, task in daily_tasks:
        message += f"🕐 {time} - {task}\n"
    
    conn.close()
    return message

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📅 Задачи на сегодня", "📋 Задачи на завтра"],
        ["👨‍💻 Админ панель"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🤖 Бот-планировщик служебных задач\n\nИспользуйте кнопки ниже:",
        reply_markup=reply_markup
    )

# Обработка кнопок
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    
    text = update.message.text
    
    if text == "📅 Задачи на сегодня":
        tasks = get_tasks_for_date(datetime.now())
        await update.message.reply_text(tasks)
    
    elif text == "📋 Задачи на завтра":
        tomorrow = datetime.now() + timedelta(days=1)
        tasks = get_tasks_for_date(tomorrow)
        await update.message.reply_text(tasks.replace("ЗАДАЧИ НА", "ЗАДАЧИ НА ЗАВТРА"))
    
    elif text == "👨‍💻 Админ панель":
        await admin_panel(update, context)

# Админ панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """👨‍💻 АДМИН ПАНЕЛЬ

Команды:
/add_daily время - задача - Добавить ежедневную
/delete_daily id - Удалить ежедневную
/time ЧЧ:ММ - Изменить время отправки
/view_all - Показать все задачи
/test - Тест отправки"""
    
    await update.message.reply_text(text)

# Ежедневная отправка
def send_daily_tasks():
    application = Application.builder().token(BOT_TOKEN).build()
    
    async def send():
        tasks = get_tasks_for_date(datetime.now())
        await application.bot.send_message(chat_id=ADMIN_ID, text=tasks)
        logger.info("✅ Задачи отправлены")
    
    import asyncio
    asyncio.run(send())

# Планировщик
def scheduler():
    schedule.every().day.at("17:45").do(send_daily_tasks)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Запуск бота
def main():
    # Инициализация БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем планировщик в отдельном потоке
    thread = threading.Thread(target=scheduler)
    thread.daemon = True
    thread.start()
    
    # Запускаем бота
    logger.info("🚀 Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()
