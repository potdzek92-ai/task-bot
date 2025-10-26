import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import sqlite3
import time
import threading

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
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY, key TEXT, value TEXT)''')
    
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
        
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('send_time', '17:45')")
    
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
        await admin_panel(update, context)

# Админ панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """👨‍💻 АДМИН ПАНЕЛЬ

Команды:
/add_daily - Добавить ежедневную задачу
/delete_daily - Удалить задачу
/list_daily - Список всех задач
/time ЧЧ:ММ - Изменить время отправки
/test - Тест отправки"""
    
    await update.message.reply_text(text)

# Добавление задачи
async def add_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /add_daily ВРЕМЯ ЗАДАЧА\nПример: /add_daily 08:00 Утреннее совещание")
        return
    
    time_str = context.args[0]
    task = ' '.join(context.args[1:])
    
    # Проверка формата времени
    try:
        datetime.strptime(time_str, '%H:%M')
    except ValueError:
        await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ")
        return
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO daily_tasks (time, task) VALUES (?, ?)", (time_str, task))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Задача добавлена: {time_str} - {task}")

# Список всех задач
async def list_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
        
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT id, time, task FROM daily_tasks ORDER BY time")
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        await update.message.reply_text("📝 Нет задач")
        return
    
    message = "📋 ВСЕ ЗАДАЧИ:\n\n"
    for task_id, time_str, task in tasks:
        message += f"#{task_id} 🕐 {time_str} - {task}\n"
    
    await update.message.reply_text(message)

# Ежедневная отправка
async def send_daily_tasks(app):
    try:
        tasks = get_tasks_for_date(datetime.now())
        await app.bot.send_message(chat_id=ADMIN_ID, text=tasks)
        logger.info("✅ Ежедневные задачи отправлены")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")

# Планировщик
async def scheduler(app):
    while True:
        now = datetime.now()
        # Проверяем каждый час, не время ли отправлять задачи
        if now.hour == 17 and now.minute == 45:
            await send_daily_tasks(app)
        
        # Ждем 1 минуту до следующей проверки
        await asyncio.sleep(60)

# Тестовая команда
async def test_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
        
    await send_daily_tasks(context.application)
    await update.message.reply_text("✅ Тестовое сообщение отправлено")

# Запуск бота
async def main():
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
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("add_daily", add_daily))
    application.add_handler(CommandHandler("list_daily", list_daily))
    application.add_handler(CommandHandler("test", test_send))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем планировщик как асинхронную задачу
    asyncio.create_task(scheduler(application))
    
    # Для Render используем webhook
    if 'RENDER' in os.environ:
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        # Локально используем polling
        logger.info("🚀 Бот запущен (polling)!")
        await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
