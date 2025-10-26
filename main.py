import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import sqlite3

# Настройки для Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.environ.get('PORT', 8443))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tasks
                 (id INTEGER PRIMARY KEY, time TEXT, task TEXT)''')
    
    # Стандартные задачи
    c.execute("SELECT COUNT(*) FROM daily_tasks")
    if c.fetchone()[0] == 0:
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
    
    conn.commit()
    conn.close()

# Получение задач на дату
def get_tasks_for_date(date):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    day_names = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
    day_name = day_names[date.weekday()]
    
    message = f"🎖️ ЗАДАЧИ НА {date.strftime('%d.%m.%Y')} ({day_name.upper()})\n\n"
    
    c.execute("SELECT time, task FROM daily_tasks ORDER BY time")
    daily_tasks = c.fetchall()
    
    message += "📅 ЕЖЕДНЕВНЫЕ:\n"
    for time, task in daily_tasks:
        message += f"🕐 {time} - {task}\n"
    
    conn.close()
    return message

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
        
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
        await update.message.reply_text("👨‍💻 Админ панель\n\nИспользуйте команды:\n/start - Главное меню")

# Запуск бота
def main():
    # Проверка обязательных переменных
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен")
        return
    
    if ADMIN_ID == 0:
        logger.error("❌ ADMIN_ID не установлен")
        return
    
    # Инициализация БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Для Render используем webhook
    if 'RENDER' in os.environ:
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        # Локально используем polling
        logger.info("🚀 Бот запущен (polling)!")
        application.run_polling()

if __name__ == "__main__":
    main()
