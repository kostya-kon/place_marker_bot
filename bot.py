from collections import defaultdict
from contextlib import closing
import telebot
from telebot import types
import pymysql
from pymysql.cursors import DictCursor
import os

TOKEN = os.getenv("TOKEN", "")

bot = telebot.TeleBot(TOKEN, parse_mode=None) # You can set parse_mode by default. HTML or MARKDOWN

# some vars
ADD, ADDRESS, PIC, LOC = range(4)
USER_STATE = defaultdict(lambda: ADD)
PLACES = defaultdict(lambda: {})

reset1, reset2 = range(2)
RESET_STATE = defaultdict(lambda: reset1)

# functions
def get_pos(message):
    return USER_STATE[message.chat.id]


def update_pos(message, state):
    USER_STATE[message.chat.id] = state


def update_place(user_id, key, value):
    PLACES[user_id][key] = value


def get_place(user_id):
    return PLACES[user_id]


def update_reset(message, state):
    RESET_STATE[message.chat.id] = state


def get_reset(message):
    return RESET_STATE[message.chat.id]


# handlers
@bot.message_handler(commands=['start'])
def start_message(message):
    print(message.chat.id)
    bot.reply_to(message, "Добро пожаловать в бот, где ты можешь сохранять свои места.")
    try:
        with closing(pymysql.connect(
            host='localhost',
            user='root',
            password='Kostya_2020',
            db='place_bot_db',
            charset='utf8mb4',
                cursorclass=DictCursor)) as connection:
            with connection.cursor() as cursor:
                SQL = "INSERT INTO  users(user_id) VALUES ({id})".format(id=message.chat.id)
                cursor.execute(SQL)
                connection.commit()
    except pymysql.err.IntegrityError:
        pass

@bot.message_handler(commands=['add'], func=lambda message: get_pos(message) == ADD)
def add_message(message):
    bot.reply_to(message, "Добваление нового места. Сначала введите адресс: ")
    update_pos(message, ADDRESS)


@bot.message_handler(func=lambda message: get_pos(message) == ADDRESS)
def address_message(message):
    update_place(message.chat.id, "address", message.text)
    bot.reply_to(message, "Теперь прекрепите фото: ")
    update_pos(message, PIC)


@bot.message_handler(func=lambda message: get_pos(message) == PIC, content_types=["photo"])
def photo_message(message):
    update_place(message.chat.id, "pic", message.photo[0].file_id)
    bot.reply_to(message, "Прикрепите локацию: ")
    update_pos(message, LOC)


@bot.message_handler(func=lambda message: get_pos(message) == LOC, content_types=["location"])
def location_message(message):
    update_place(message.chat.id, "loc", message.location)
    bot.reply_to(message, "Место успешно добавленно!")
    bot.send_message(message.chat.id, "Данные: ")
    bot.send_message(message.chat.id, PLACES[message.chat.id]["address"])
    bot.send_photo(message.chat.id, PLACES[message.chat.id]["pic"])
    loc = PLACES[message.chat.id]["loc"]
    bot.send_location(message.chat.id, loc.latitude, loc.longitude)
    update_pos(message, ADD)
    with closing(pymysql.connect(
        host='localhost',
        user='root',
        password='Kostya_2020',
        db='place_bot_db',
        charset='utf8mb4',
            cursorclass=DictCursor)) as connection:
        with connection.cursor() as cursor:
            SQL = "INSERT INTO place(user_id, address, pic, loc_lat, loc_lon) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(SQL, (message.chat.id,
                                 PLACES[message.chat.id]["address"],
                                 PLACES[message.chat.id]["pic"],
                                 loc.latitude, loc.longitude))
            connection.commit()


@bot.message_handler(commands=['list'])
def list_message(message):
    bot.reply_to(message, "Ваш список мест: ")
    with closing(pymysql.connect(
        host='localhost',
        user='root',
        password='Kostya_2020',
        db='place_bot_db',
        charset='utf8mb4',
            cursorclass=DictCursor)) as connection:
        with connection.cursor() as cursor:
            SQL = """
            SELECT place.user_id, place.address, place.pic, 
            place.loc_lat, place.loc_lon 
            FROM users inner join place on users.user_id = place.user_id
            WHERE place.user_id = %s
            LIMIT 10
            """
            cursor.execute(SQL, message.chat.id)
            i = 1
            for row in cursor:
                print(row)
                bot.send_message(row["user_id"], "Место № {i} > {ad}".format(i=i, ad=row["address"]))
                bot.send_photo(row["user_id"], row["pic"])
                bot.send_location(row["user_id"], row["loc_lat"], row["loc_lon"])
                i += 1

# keyboard for reset
markup = types.ReplyKeyboardMarkup()
da = types.KeyboardButton('ДА')
net = types.KeyboardButton('НЕТ')
markup.row(da, net)
close_markup = types.ReplyKeyboardRemove(selective=False)

@bot.message_handler(commands=['reset'], func=lambda message: get_reset(message) == reset1)
def reset_message(message):
    bot.reply_to(message, "Вы уверены, что хотите удалить записи?(Да/Нет)", reply_markup=markup)
    update_reset(message, reset2)


@bot.message_handler(func=lambda message: get_reset(message) == reset2)
def reset_message_stage2(message):
    if message.text.lower() == "да":
        with closing(pymysql.connect(
                host='localhost',
                user='root',
                password='Kostya_2020',
                db='place_bot_db',
                charset='utf8mb4',
                cursorclass=DictCursor)) as connection:
            with connection.cursor() as cursor:
                SQL = "DELETE FROM place WHERE user_id = %s"
                cursor.execute(SQL, (message.chat.id,))
                connection.commit()
            bot.reply_to(message, "Успешно удалено", reply_markup=close_markup)
            update_reset(message, reset1)
    else:
        bot.reply_to(message, "Удаление отменено", reply_markup=close_markup)
        update_reset(message, reset1)



bot.polling()