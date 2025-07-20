import os
import sqlite3
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from telebot import TeleBot, types
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut

from config import TOKEN, DATABASE
from logic import *

bot = TeleBot(TOKEN)
manager = DB_Map(DATABASE)
geolocator = Nominatim(user_agent="mapbot")


def geocode_city(name: str):
    """
    Возвращает (lat, lon) или None, если не нашло.
    """
    try:
        loc = geolocator.geocode(name, timeout=10)
    except (GeocoderTimedOut, GeocoderUnavailable):
        return None
    if loc:
        return loc.latitude, loc.longitude
    return None


@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    bot.send_message(
        message.chat.id,
        "Привет! Я картографический бот.\n"
        "Напиши /help, чтобы узнать, что я умею."
    )


@bot.message_handler(commands=['help'])
def handle_help(message: types.Message):
    help_text = (
        "Доступные команды:\n"
        "/start — запустить бота\n"
        "/help — показать это сообщение\n"
        "/show_city <city_name> — отобразить город на карте\n"
        "/remember_city <city_name> — сохранить город в список избранных\n"
        "/show_my_cities — показать все ваши сохранённые города на карте\n"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['show_city'])
def handle_show_city(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Использование: /show_city <city_name>")
        return
    city_name = parts[1].strip()

    coords = geocode_city(city_name)
    if not coords:
        bot.send_message(message.chat.id, f"Не удалось найти координаты города «{city_name}».")
        return
    lat, lon = coords

    # рисуем карту
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.coastlines(resolution='110m')
    ax.set_global()
    ax.plot(lon, lat, 'ro', markersize=8, transform=ccrs.PlateCarree())
    ax.text(lon + 1, lat + 1, city_name, transform=ccrs.PlateCarree())
    ax.set_title(f"Город: {city_name}")

    img_path = f"temp_{message.chat.id}_city.png"
    plt.savefig(img_path, bbox_inches='tight')
    plt.close(fig)

    with open(img_path, 'rb') as img:
        bot.send_photo(message.chat.id, img)
    os.remove(img_path)


@bot.message_handler(commands=['remember_city'])
def handle_remember_city(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Использование: /remember_city <city_name>")
        return
    city_name = parts[1].strip()
    user_id = message.chat.id

    # Проверим, хоть как-то, что город существует
    if not geocode_city(city_name):
        bot.send_message(message.chat.id, f"Город «{city_name}» не найден геокодером.")
        return

    if manager.add_city(user_id, city_name):
        bot.send_message(message.chat.id, f"Город «{city_name}» успешно сохранён!")
    else:
        bot.send_message(
            message.chat.id,
            "Не смог сохранить город. Возможно он уже в списке."
        )


@bot.message_handler(commands=['show_my_cities'])
def handle_show_visited_cities(message: types.Message):
    user_id = message.chat.id
    cities = manager.select_cities(user_id)
    if not cities:
        bot.send_message(user_id, "У вас ещё нет сохранённых городов.")
        return

    # Геокодим каждый город
    coords = []
    for city in cities:
        c = geocode_city(city)
        if c:
            coords.append((city, c[0], c[1]))

    if not coords:
        bot.send_message(user_id, "Не удалось получить координаты для ваших городов.")
        return

    # рисуем
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.coastlines(resolution='110m')
    ax.set_global()
    for city, lat, lon in coords:
        ax.plot(lon, lat, 'ro', markersize=5, transform=ccrs.PlateCarree())
        ax.text(lon + 0.5, lat + 0.5, city,
                fontsize=8, transform=ccrs.PlateCarree())
    ax.set_title("Мои сохранённые города")

    img_path = f"temp_{user_id}_cities.png"
    plt.savefig(img_path, bbox_inches='tight')
    plt.close(fig)

    with open(img_path, 'rb') as img:
        bot.send_photo(user_id, img)
    os.remove(img_path)


if __name__ == '__main__':
    bot.polling(none_stop=True)
