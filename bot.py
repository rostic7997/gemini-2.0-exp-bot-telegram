import logging
import threading
import time
import tkinter as tk
from tkinter import ttk
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Конфигурация API
genai.configure(api_key="google-gemini-2.0-flash-exp-API")

# Создание модели
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для аналитики
user_message_count = {}
bot_message_count = {}
chat_sessions = {}
active_users = {}

# Функция отправки сообщения
async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_input = update.message.text

    if user_input.startswith("/"):
        response = handle_command(user_input, user_id, update.message.from_user.username)
    else:
        if user_id not in user_message_count:
            user_message_count[user_id] = 0
        if user_id not in bot_message_count:
            bot_message_count[user_id] = 0
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])

        user_message_count[user_id] += 1
        response = chat_sessions[user_id].send_message(user_input)
        bot_message_count[user_id] += 1

        # Обновляем активных пользователей
        active_users[user_id] = update.message.from_user.username

    await update.message.reply_text(response.text)

# Функция обработки команд
def handle_command(command: str, user_id: int, username: str) -> str:
    if command == "/help":
        return "Доступные команды:\n/help - помощь\n/clear - очистить чат\n/exit - выйти из программы\n"
    elif command == "/clear":
        if user_id in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
        return ""
    elif command == "/exit":
        return "Выход из программы."
    else:
        return "Неизвестная команда. Введите /help для списка доступных команд.\n"

# Функция перевода текста
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_input = update.message.text

    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])

    response = chat_sessions[user_id].send_message(f"Переведи на английский: {user_input}")

    await update.message.reply_text(response.text)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Я ваш чат-бот на основе модели Gemini. Введите ваше сообщение или используйте команды.')

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(handle_command("/help", update.message.from_user.id, update.message.from_user.username))

# Команда /clear
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(handle_command("/clear", update.message.from_user.id, update.message.from_user.username))

# Команда /exit
async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(handle_command("/exit", update.message.from_user.id, update.message.from_user.username))

# Обработчик ошибок
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

# Функция для обновления статистики в GUI
def update_statistics(root, tree, user_count_label, bot_count_label):
    while True:
        # Очистка таблицы
        for i in tree.get_children():
            tree.delete(i)

        # Обновление таблицы активных пользователей
        for user_id, username in active_users.items():
            tree.insert("", "end", values=(user_id, username))

        # Обновление счетчиков
        total_user_messages = sum(user_message_count.values())
        total_bot_messages = sum(bot_message_count.values())
        user_count_label.config(text=f"Сообщений от пользователей: {total_user_messages}")
        bot_count_label.config(text=f"Сообщений от бота: {total_bot_messages}")

        # Обновление GUI
        root.update_idletasks()
        time.sleep(10)  # Обновление каждые 10 секунд

def create_statistics_window():
    root = tk.Tk()
    root.title("Статистика пользователей")

    # Создание таблицы
    tree = ttk.Treeview(root, columns=("ID", "Никнейм"), show="headings")
    tree.heading("ID", text="ID")
    tree.heading("Никнейм", text="Никнейм")
    tree.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Создание меток для счетчиков
    user_count_label = ttk.Label(root, text="Сообщений от пользователей: 0")
    user_count_label.pack(pady=5)

    bot_count_label = ttk.Label(root, text="Сообщений от бота: 0")
    bot_count_label.pack(pady=5)

    # Запуск обновления статистики
    stats_thread = threading.Thread(target=update_statistics, args=(root, tree, user_count_label, bot_count_label))
    stats_thread.daemon = True
    stats_thread.start()

    root.mainloop()

def main() -> None:
    # Токен вашего бота
    TOKEN = "telegram-bot.api_key"

    # Создаем приложение
    application = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("exit", exit_command))
    application.add_handler(CommandHandler("translate", translate_message))

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_message))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error)

    # Запускаем окно статистики в отдельном потоке
    stats_thread = threading.Thread(target=create_statistics_window)
    stats_thread.daemon = True
    stats_thread.start()

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()