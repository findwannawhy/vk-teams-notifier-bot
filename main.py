import logging
import pytz
from bot.bot import Bot
from bot.handler import MessageHandler, CommandHandler
from bot.types import InlineKeyboardMarkup, KeyboardButton
from bot.filter import RegexpFilter
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time
import schedule
from threading import Thread
import re
import os

# --- Константы и глобальные переменные ---
TOKEN = "001.2619402640.1072935266:1011994482"
botname = "vkpracticesannbot"

# Регулярные выражения (из utils/patterns.py)
greet_pattern = re.compile(r'^(qq|ку|привет|здравствуйте|здравствуй|здарова)\s*[!.]*$', re.IGNORECASE)
farewell_pattern = re.compile(r'^(бб|пока|до свидания)\s*[!.]*$', re.IGNORECASE)

user_states = {}

# Инициализация бота
bot = Bot(token=TOKEN)

# Создание планировщика
moscow_tz = pytz.timezone('Europe/Moscow')
scheduler = BackgroundScheduler(timezone=moscow_tz)
scheduler.start()


# --- Функции планировщика ---

def load_scheduled_tasks(bot):
    try:
        if not os.path.exists("tasks.txt"):
            with open("tasks.txt", "w", encoding="utf-8"):
                pass

        with open("tasks.txt", "r", encoding="utf-8") as file:
            tasks = file.readlines()

        for line in tasks:
            if "|" not in line:
                logging.warning(f"Пропуск некорректной строки в tasks.txt: {line.strip()}")
                continue
            try:
                chat_id, message_text, scheduled_time, task_type, status = line.strip().split("|")
                if task_type == "single":
                    run_date = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")
                    if run_date > datetime.now():
                        scheduler.add_job(send_scheduled_message, 'date', run_date=run_date, args=[bot, chat_id, message_text], id=f"{chat_id}_{message_text}_{scheduled_time}_single")
                elif task_type == "recurring":
                    run_time = datetime.strptime(scheduled_time, "%H:%M:%S").time()
                    scheduler.add_job(send_scheduled_message, 'cron', hour=run_time.hour, minute=run_time.minute, args=[bot, chat_id, message_text], id=f"{chat_id}_{message_text}_{scheduled_time}_recurring")
            except ValueError as e:
                 logging.error(f"Ошибка разбора строки в tasks.txt: {line.strip()} - {e}")
            except Exception as e:
                 logging.error(f"Неожиданная ошибка при обработке строки tasks.txt: {line.strip()} - {e}")

    except FileNotFoundError:
        logging.info("Файл tasks.txt не найден, создаю новый.")
        with open("tasks.txt", "w", encoding="utf-8"):
            pass
    except Exception as e:
        logging.error(f"Не удалось загрузить запланированные задачи: {e}")


def save_scheduled_task(chat_id, message_text, scheduled_time_str, task_type, status="pending"):
    try:
        with open("tasks.txt", "a", encoding="utf-8") as file:
            file.write(f"{chat_id}|{message_text}|{scheduled_time_str}|{task_type}|{status}\n")
    except Exception as e:
        logging.error(f"Не удалось сохранить запланированную задачу: {e}")


def send_scheduled_message(bot, chat_id, message_text):
    try:
        bot.send_text(chat_id=chat_id, text=message_text)
        update_task_status(chat_id, message_text, "sent", task_type="single")
    except Exception as e:
        logging.error(f"Не удалось отправить отложенное сообщение в чат {chat_id}: {e}")


def update_task_status(chat_id, message_text, new_status, task_type="single"):
    try:
        with open("tasks.txt", "r", encoding="utf-8") as file:
            tasks = file.readlines()

        updated_tasks = []
        found = False
        for task in tasks:
            try:
                t_chat_id, t_message_text, t_scheduled_time, t_task_type, t_status = task.strip().split("|")
                if t_chat_id == chat_id and t_message_text == message_text and t_task_type == task_type:
                    updated_tasks.append(f"{t_chat_id}|{t_message_text}|{t_scheduled_time}|{t_task_type}|{new_status}\n")
                    found = True
                else:
                    updated_tasks.append(task)
            except ValueError:
                 updated_tasks.append(task)

        if found:
            with open("tasks.txt", "w", encoding="utf-8") as file:
                file.writelines(updated_tasks)
    except FileNotFoundError:
        logging.warning("Файл tasks.txt не обнаружен при обновлении статуса.")
        pass
    except Exception as e:
        logging.error(f"Не удалось обновить статус задачи: {e}")


def schedule_message(bot, chat_id, scheduled_datetime, message_text):
    scheduled_time_str = scheduled_datetime.strftime("%Y-%m-%d %H:%M:%S")
    scheduler.add_job(send_scheduled_message, 'date', run_date=scheduled_datetime, args=[bot, chat_id, message_text], id=f"{chat_id}_{message_text}_{scheduled_time_str}_single")
    save_scheduled_task(chat_id, message_text, scheduled_time_str, "single")


def schedule_recurring_message(bot, chat_id, time_obj, message_text):
    scheduled_time_str = time_obj.strftime("%H:%M:%S")
    scheduler.add_job(send_scheduled_message, 'cron', hour=time_obj.hour, minute=time_obj.minute, args=[bot, chat_id, message_text], id=f"{chat_id}_{message_text}_{scheduled_time_str}_recurring")
    save_scheduled_task(chat_id, message_text, scheduled_time_str, "recurring", status="active")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


# --- Обработчики команд и сообщений ---

# Обработчик команды /start
@bot.start_handler()
def start_command(bot, event):
    bot.send_text(chat_id=event.from_chat, text="Йоу! Жми /menu, чтобы увидеть, что я могу.")

# Обработчик приветствия
@bot.message_handler(filters=RegexpFilter(greet_pattern) & (lambda event: event.chat_type == "private"))
def greet_user(bot, event):
    user_first_name = event.message_author.get("firstName", "Собеседник")
    bot.send_text(chat_id=event.from_chat, text=f"Хай, {user_first_name}! 😉")

# Обработчик прощания
@bot.message_handler(filters=RegexpFilter(farewell_pattern) & (lambda event: event.chat_type == "private"))
def farewell_user(bot, event):
    user_first_name = event.message_author.get("firstName", "Собеседник")
    bot.send_text(chat_id=event.from_chat, text=f"До связи, {user_first_name}! 😎")

# Обработчик приветствия нового участника чата
@bot.new_member_handler()
def greet_new_member(bot, event):
    new_members = event.data.get("newMembers", [])
    if any(member.get("userId") == bot.uin for member in new_members):
        bot.send_text(
            chat_id=event.data["chat"]["chatId"],
            text = """
            Здарова! 🎉 Я ваш новый помощник. Готов служить!
            Напишите <b>/menu</b>, чтобы ознакомиться с моими возможностями!
            """,
            parse_mode = "HTML"
        )
        return
    for member in new_members:
        if member.get("userId") != bot.uin:
            user_first_name = member.get("firstName")
            greeting = f"<b>Приветик, {user_first_name}!</b> ✨ Рады видеть тебя в чате!"
            bot.send_text(
                chat_id=event.data["chat"]["chatId"],
                text=greeting,
                parse_mode="HTML"
            )

# Обработчик команды /menu
@bot.command_handler(command="menu")
def menu_command(bot, event):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(KeyboardButton(text="📌 Запланировать разовое сообщение", callbackData="schedule_message"))
    keyboard.add(KeyboardButton(text="🔁 Создать ежедневную рассылку", callbackData="always_msg"))
    keyboard.add(KeyboardButton(text="👀 Посмотреть разовые сообщения", callbackData="view_scheduled_messages"))
    keyboard.add(KeyboardButton(text="🔄 Посмотреть ежедневные рассылки", callbackData="view_recurring_messages"))
    keyboard.add(KeyboardButton(text="❓ Помощь", callbackData="info_msg"))
    bot.send_text(chat_id=event.from_chat, text="Вот что я умею:", inline_keyboard_markup=keyboard)


# Обработчик нажатия на кнопку "Справка"
@bot.button_handler(filters=lambda event: event.data.get('callbackData') == "info_msg")
def info_message(bot, event):
    user_data = event.data.get('from')
    user_firstname = "Друг"
    if user_data:
        user_firstname = user_data.get("firstName", user_firstname)
    info = f"""
Хэй, {user_firstname}!
Эта инструкция поможет тебе понять мои функции.
1. Кнопка "📌 Запланировать разовое сообщение": Позволяет отправить сообщение <b>один раз</b> в указанное время.
   Ввод в <b>3 шага</b>: сначала дата (формат <b>ДД.ММ.ГГГГ</b>), потом время (формат <b>ЧЧ:ММ</b>), и затем сам <b>текст сообщения</b>.
2. Кнопка "🔁 Создать ежедневную рассылку": Позволяет настроить сообщение, которое будет отправляться <b>каждый день</b> в одно и то же время.
   Ввод в <b>2 шага</b>: время (формат <b>ЧЧ:ММ</b>) и текст рассылки.
3. Кнопка "👀 Посмотреть разовые сообщения": Показывает все одноразовые сообщения (отправленные и ожидающие).
4. Кнопка "🔄 Посмотреть ежедневные рассылки": Отображает все активные ежедневные рассылки и позволяет их удалить.
"""
    bot.send_text(chat_id=event.from_chat, text = info, parse_mode = "HTML")


# Обработчик нажатия на кнопку "Запланировать сообщение"
@bot.button_handler(filters=lambda event: event.data.get('callbackData') == "schedule_message")
def initiate_schedule_message(bot, event):
    bot.send_text(chat_id=event.from_chat, text="Укажите дату отправки (формат ДД.ММ.ГГГГ)")
    user_states[event.from_chat] = {"state": "waiting_for_date", "type": "single"}

# Обработчик нажатия на кнопку "Постоянная рассылка"
@bot.button_handler(filters=lambda event: event.data.get('callbackData') == "always_msg")
def initiate_recurring(bot, event):
    bot.send_text(chat_id=event.from_chat, text="Укажите время для ежедневной отправки (формат ЧЧ:ММ)")
    user_states[event.from_chat] = {"state": "waiting_for_time", "type": "recurring"}

# Обработчик нажатия на кнопку "Просмотр одноразовых сообщений"
@bot.button_handler(filters=lambda event: event.data.get('callbackData') == "view_scheduled_messages")
def view_scheduled_messages(bot, event):
    try:
        with open("tasks.txt", "r", encoding="utf-8") as file:
            tasks = file.readlines()

        user_tasks = []
        for task in tasks:
             try:
                 task_chat_id, message_text, scheduled_time, task_type, status = task.strip().split("|")
                 if task_chat_id == event.from_chat and task_type == "single":
                     user_tasks.append((message_text, scheduled_time, status))
             except ValueError:
                 logging.warning(f"Пропуск некорректной строки в tasks.txt при просмотре: {task.strip()}")
                 continue

        if user_tasks:
            response = "Ваши одноразовые запланированные сообщения:\n\n"
            for i, (message_text, scheduled_time, status) in enumerate(user_tasks, 1):
                try:
                    dt_obj = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")
                    display_time = dt_obj.strftime('%d.%m.%Y %H:%M')
                except ValueError:
                    display_time = scheduled_time
                status_text = "✅ Выполнено" if status == "sent" else "⏳ Ожидает"
                response += f"{i}. Текст: {message_text}\n   Время: {display_time}\n   Статус: {status_text}\n\n"
        else:
            response = "У вас пока нет запланированных разовых сообщений."

        bot.send_text(chat_id=event.from_chat, text=response)
    except FileNotFoundError:
        bot.send_text(chat_id=event.from_chat, text="Список запланированных сообщений пуст.")
    except Exception as e:
        logging.error(f"Ошибка при просмотре запланированных сообщений для {event.from_chat}: {e}")
        bot.send_text(chat_id=event.from_chat, text="Не удалось отобразить сообщения. Попробуйте позже.")


# Обработчик кнопки "Просмотр рассылок"
@bot.button_handler(filters=lambda event: event.data.get('callbackData') == "view_recurring_messages")
def view_recurring_messages(bot, event):
    try:
        with open("tasks.txt", "r", encoding="utf-8") as file:
            tasks = file.readlines()

        user_tasks = []
        task_details = []
        for i, task in enumerate(tasks):
             try:
                 task_chat_id, message_text, scheduled_time, task_type, status = task.strip().split("|")
                 if task_chat_id == event.from_chat and task_type == "recurring" and status == "active":
                     try:
                         time_obj = datetime.strptime(scheduled_time, "%H:%M:%S").time()
                         display_time = time_obj.strftime('%H:%M')
                     except ValueError:
                         display_time = scheduled_time
                     user_tasks.append((i, message_text, display_time))
                     task_details.append({"index": i, "chat_id": task_chat_id, "text": message_text, "time": scheduled_time})
             except ValueError:
                 logging.warning(f"Пропуск некорректной строки в tasks.txt при просмотре рассылок: {task.strip()}")
                 continue

        if user_tasks:
            response = "Ваши активные ежедневные рассылки:\n\n"
            keyboard = InlineKeyboardMarkup()
            for idx, message_text, display_time in user_tasks:
                response += f"{idx + 1}. Текст: {message_text}\n   Время: {display_time}\n\n"
                keyboard.add(KeyboardButton(text=f"❌ Удалить рассылку №{idx + 1}", callbackData=f"delete_recurring_{idx}"))

            bot.send_text(chat_id=event.from_chat, text=response, inline_keyboard_markup=keyboard)
        else:
            bot.send_text(chat_id=event.from_chat, text="У вас нет активных ежедневных рассылок.")
    except FileNotFoundError:
        bot.send_text(chat_id=event.from_chat, text="Список рассылок пуст.")
    except Exception as e:
        logging.error(f"Ошибка при просмотре рассылок для {event.from_chat}: {e}")
        bot.send_text(chat_id=event.from_chat, text="Не удалось отобразить рассылки. Попробуйте позже.")


# Обработка кнопки "Удалить рассылку"
@bot.button_handler(filters=lambda event: event.data.get('callbackData', "").startswith("delete_recurring_"))
def delete_recurring_message(bot, event):
    try:
        task_line_index = int(event.data.get('callbackData').split("_")[2])

        with open("tasks.txt", "r", encoding="utf-8") as file:
            tasks = file.readlines()

        if 0 <= task_line_index < len(tasks):
            deleted_task_line = tasks[task_line_index].strip()
            try:
                chat_id, message_text, scheduled_time, task_type, status = deleted_task_line.split("|")

                if task_type == "recurring":
                    del tasks[task_line_index]
                    with open("tasks.txt", "w", encoding="utf-8") as file:
                        file.writelines(tasks)

                    job_id = f"{chat_id}_{message_text}_{scheduled_time}_recurring"
                    try:
                        scheduler.remove_job(job_id)
                        bot.send_text(chat_id=event.from_chat, text="Ежедневная рассылка успешно отменена.")
                    except Exception as e:
                        logging.warning(f"Не удалось удалить задачу {job_id} из планировщика (возможно, уже удалена?): {e}")
                        bot.send_text(chat_id=event.from_chat, text="Рассылка удалена из списка (планировщик мог уже остановить ее).")

                else:
                     bot.send_text(chat_id=event.from_chat, text="Сбой: Попытка удалить непериодическую задачу.")

            except ValueError:
                bot.send_text(chat_id=event.from_chat, text="Сбой: Не удалось обработать строку задачи для удаления.")
            except Exception as e:
                 logging.error(f"Ошибка при обработке удаления для индекса задачи {task_line_index}: {e}")
                 bot.send_text(chat_id=event.from_chat, text=f"Произошла ошибка при удалении рассылки: {e}")
        else:
            bot.send_text(chat_id=event.from_chat, text="Сбой: Некорректный номер рассылки.")
    except FileNotFoundError:
        bot.send_text(chat_id=event.from_chat, text="Сбой: Файл с задачами не найден.")
    except Exception as e:
        logging.error(f"Общая ошибка при удалении рассылки: {e}")
        bot.send_text(chat_id=event.from_chat, text=f"Произошла ошибка при удалении: {e}")


# Обработчик для сообщений состояния
def handle_message(bot, event):
    chat_id = event.from_chat
    text = event.text

    if chat_id in user_states:
        state = user_states[chat_id]

        if state["state"] == "waiting_for_date":
            try:
                date = datetime.strptime(text, "%d.%m.%Y")
                if date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                     bot.send_text(chat_id=chat_id, text="Эта дата уже прошла. Введите другую дату.")
                     return
                user_states[chat_id].update({"state": "waiting_for_time", "date": date})
                bot.send_text(chat_id=chat_id, text="Теперь введите время (формат ЧЧ:ММ)")
            except ValueError:
                bot.send_text(chat_id=chat_id, text="Неверный формат даты. Нужен ДД.ММ.ГГГГ. Попробуйте еще раз.")

        elif state["state"] == "waiting_for_time":
            try:
                time_input = datetime.strptime(text, "%H:%M").time()
                if state["type"] == "single":
                    scheduled_datetime_naive = datetime.combine(state["date"], time_input)
                    scheduled_datetime = moscow_tz.localize(scheduled_datetime_naive)

                    if scheduled_datetime < datetime.now(moscow_tz):
                         bot.send_text(chat_id=chat_id, text="Увы, это время уже прошло сегодня. Пожалуйста, начните настройку заново.")
                         user_states[chat_id] = {"state": "waiting_for_date", "type": "single"}
                         bot.send_text(chat_id=chat_id, text="Введите дату (формат ДД.ММ.ГГГГ)")
                         return

                user_states[chat_id].update({"state": "waiting_for_text", "time": time_input})
                bot.send_text(chat_id=chat_id, text="Отлично! Теперь введите текст сообщения.")
            except ValueError:
                bot.send_text(chat_id=chat_id, text="Неверный формат времени. Нужен ЧЧ:ММ. Попробуйте еще раз.")

        elif state["state"] == "waiting_for_text":
            message_text = text
            if not message_text:
                bot.send_text(chat_id=chat_id, text="Сообщение не может быть пустым. Напишите что-нибудь.")
                return

            if state["type"] == "single":
                scheduled_datetime = datetime.combine(state["date"], state["time"])
                if scheduled_datetime < datetime.now():
                     bot.send_text(chat_id=chat_id, text="Увы, пока вы вводили текст, это время уже наступило. Начните заново.")
                else:
                    schedule_message(bot, chat_id, scheduled_datetime, message_text)
                    bot.send_text(chat_id=chat_id, text=f"Принято! Сообщение будет отправлено {scheduled_datetime.strftime('%d.%m.%Y в %H:%M')}")

            elif state["type"] == "recurring":
                schedule_recurring_message(bot, chat_id, state["time"], message_text)
                bot.send_text(chat_id=chat_id, text=f"Готово! Рассылка будет приходить ежедневно в {state['time'].strftime('%H:%M')}")

            del user_states[chat_id]
        else:
            if chat_id in user_states:
                del user_states[chat_id]


# --- Запуск ---

scheduler_thread = Thread(target=run_scheduler)
scheduler_thread.daemon = True
scheduler_thread.start()

bot.dispatcher.add_handler(MessageHandler(callback=handle_message))

load_scheduled_tasks(bot)

logging.basicConfig(level=logging.INFO)
logging.info("Запускаю бота...")
bot.start_polling()
logging.info("Бот начал принимать сообщения.")
bot.idle()
logging.info("Бот остановлен.") 