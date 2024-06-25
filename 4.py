import telebot
from telebot import types
import sqlite3
import logging

# API_TOKEN = ''

bot = telebot.TeleBot(API_TOKEN)
# admin_id = 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()])

def initialize_db():
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("""CREATE TABLE IF NOT EXISTS requests (
                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER,
                              description TEXT,
                              status TEXT,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                              )""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                              user_id INTEGER PRIMARY KEY,
                              full_name TEXT
                              )""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS admin_responses (
                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER,
                              response TEXT,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                              )""")
            connect.commit()
            logging.info("База данных успешно инициализирована.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")

initialize_db()

# Оповещение администратора о новой заявке
def notify_admin_new_request(request_id, user_id, description):
    try:
        markup = types.InlineKeyboardMarkup()
        btn_delete = types.InlineKeyboardButton("Удалить заявку", callback_data=f"delete_{request_id}")
        btn_contact = types.InlineKeyboardButton("Связаться с пользователем", callback_data=f"contact_{user_id}")
        markup.row(btn_delete, btn_contact)

        bot.send_message(admin_id, f"Поступила новая заявка #{request_id} от пользователя {user_id}:\n{description}", reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Ошибка при отправке уведомления администратору: {e}")

# Сохранение полного имени пользователя в базе данных
def save_full_name(message):
    user_id = message.from_user.id
    full_name = message.text.strip()
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("INSERT OR REPLACE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
            connect.commit()
            logging.info(f"Пользователь '{full_name}' сохранён в базе данных.")
        bot.send_message(message.chat.id, f"Спасибо! Ваше полное имя '{full_name}' сохранено. Пожалуйста, отправьте описание вашей проблемы для создания заявки.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при сохранении полного имени в базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при сохранении вашего полного имени. Попробуйте еще раз.")

# Создание основного меню для пользователя
def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_pending = types.KeyboardButton("📋 Заявки в процессе")
    btn_completed = types.KeyboardButton("✅ Завершенные заявки")
    btn_rejected = types.KeyboardButton("❌ Отклоненные заявки")
    btn_create = types.KeyboardButton("📝 Создать новую заявку")
    btn_cancel = types.KeyboardButton("❌ Отмена")
    markup.add(btn_pending, btn_completed, btn_rejected, btn_create, btn_cancel)
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            if user_data is None:
                msg = bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, предоставьте ваше полное имя.")
                bot.register_next_step_handler(msg, save_full_name)
            else:
                bot.send_message(message.chat.id, "Добро пожаловать обратно! Вы уже зарегистрированы. Пожалуйста, выберите действие из меню ниже.", reply_markup=create_main_menu())
    except sqlite3.Error as e:
        logging.error(f"Ошибка доступа к базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при доступе к базе данных. Попробуйте позже.")

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
    Доступные команды:
    /start - Начать работу с ботом
    /status - Просмотреть статус своих заявок
    /pending - Просмотреть заявки в процессе
    /completed - Просмотреть завершенные заявки
    /rejected - Просмотреть отклоненные заявки
    /create - Создать новую заявку
    /cancel - Отменить текущую операцию
    /all_requests - Просмотреть все заявки (только для администратора)
    /help - Показать это сообщение снова
    """
    bot.reply_to(message, help_text)

# Обработчик кнопки "Связаться с пользователем"
@bot.message_handler(func=lambda message: message.text.startswith('Связаться с пользователем'))
def contact_user(message):
    try:
        # Парсим user_id из текста кнопки
        user_id = int(message.text.split("_")[1])
        bot.send_message(user_id, f"Вы начали приватный диалог с пользователем {user_id}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения пользователю: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при попытке связаться с пользователем.")

@bot.message_handler(func=lambda message: message.text == "📋 Заявки в процессе")
def view_pending_requests(message):
    user_id = message.from_user.id
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("SELECT id, description, status, created_at FROM requests WHERE user_id = ? AND status = 'Pending'", (user_id,))
            pending_requests = cursor.fetchall()
        if pending_requests:
            response = "Ваши заявки в процессе:\n"
            for req in pending_requests:
                response += f"Запрос #{req[0]}: {req[1]} - Статус: {req[2]} (Создано: {req[3]})\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "У вас нет заявок в процессе.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка доступа к базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при доступе к базе данных. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "✅ Завершенные заявки")
def view_completed_requests(message):
    user_id = message.from_user.id
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("SELECT id, description, status, created_at FROM requests WHERE user_id = ? AND status = 'Completed'", (user_id,))
            completed_requests = cursor.fetchall()
        if completed_requests:
            response = "Ваши завершенные заявки:\n"
            for req in completed_requests:
                response += f"Запрос #{req[0]}: {req[1]} - Статус: {req[2]} (Создано: {req[3]})\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "У вас нет завершенных заявок.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка доступа к базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при доступе к базе данных. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "❌ Отклоненные заявки")
def view_rejected_requests(message):
    user_id = message.from_user.id
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("SELECT id, description, status, created_at FROM requests WHERE user_id = ? AND status = 'Rejected'", (user_id,))
            rejected_requests = cursor.fetchall()
        if rejected_requests:
            response = "Ваши отклоненные заявки:\n"
            for req in rejected_requests:
                                response += f"Запрос #{req[0]}: {req[1]} - Статус: {req[2]} (Создано: {req[3]})\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "У вас нет отклоненных заявок.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка доступа к базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при доступе к базе данных. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "📝 Создать новую заявку")
def create_new_request(message):
    msg = bot.send_message(message.chat.id, "Пожалуйста, опишите вашу проблему.")
    bot.register_next_step_handler(msg, process_new_request)

def process_new_request(message):
    user_id = message.from_user.id
    description = message.text.strip()
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("INSERT INTO requests (user_id, description, status) VALUES (?, ?, 'Pending')", (user_id, description))
            request_id = cursor.lastrowid
            connect.commit()
            logging.info(f"Создана новая заявка #{request_id} от пользователя {user_id}.")
        bot.send_message(message.chat.id, f"Ваша заявка #{request_id} создана и находится в обработке.")
        notify_admin_new_request(request_id, user_id, description)
    except sqlite3.Error as e:
        logging.error(f"Ошибка при создании новой заявки в базе данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при создании вашей заявки. Попробуйте еще раз.")

@bot.message_handler(func=lambda message: message.text == "❌ Отмена")
def cancel_operation(message):
    bot.send_message(message.chat.id, "Операция отменена.", reply_markup=create_main_menu())

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    bot.reply_to(message, "Извините, я не понимаю эту команду. Используйте /help для списка доступных команд.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    if call.data.startswith("delete_"):
        request_id = int(call.data.split("_")[1])
        delete_request(call.message, request_id)
    elif call.data.startswith("contact_"):
        user_id = int(call.data.split("_")[1])
        contact_user(call.message, user_id)

def delete_request(message, request_id):
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("DELETE FROM requests WHERE id = ?", (request_id,))
            connect.commit()
            bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=f"Заявка #{request_id} удалена.")
            logging.info(f"Заявка #{request_id} удалена.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при удалении заявки из базы данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при удалении заявки. Попробуйте еще раз.")

def contact_user(message, user_id):
    try:
        with sqlite3.connect('requests_new.db') as connect:
            cursor = connect.cursor()
            cursor.execute("SELECT full_name FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
        if user_data:
            bot.send_message(message.chat.id, f"Связь с пользователем {user_data[0]}.")
        else:
            bot.send_message(message.chat.id, "Информация о пользователе не найдена.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при получении информации о пользователе из базы данных: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении информации о пользователе. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_request_callback(call):
    request_id = int(call.data.split("_")[1])
    delete_request(call.message, request_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('contact_'))
def contact_user_callback(call):
    user_id = int(call.data.split("_")[1])
    contact_user(call.message, user_id)
if __name__ == '__main__':
    bot.polling(none_stop=True)
