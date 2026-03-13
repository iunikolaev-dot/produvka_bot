"""
Конфигурация бота «Продувка» от Personal Best Freediving.

Токен читается из переменной окружения BOT_TOKEN.
Локально — из файла .env, на сервере — из настроек окружения.
"""

import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError(
        "Переменная окружения BOT_TOKEN не задана. "
        "Создай файл .env с содержимым BOT_TOKEN=твой_токен "
        "или задай переменную окружения на сервере."
    )
