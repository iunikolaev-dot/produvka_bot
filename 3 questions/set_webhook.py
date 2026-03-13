"""
Одноразовый скрипт: регистрирует webhook URL в Telegram.
Запусти ПОСЛЕ деплоя на Vercel:

    python3 set_webhook.py https://ТВОЙ-ПРОЕКТ.vercel.app

Скрипт отправит запрос в Telegram API и покажет результат.
"""

import sys
import os
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    print("❌ Переменная окружения BOT_TOKEN не задана.")
    print("   Экспортируй её:  export BOT_TOKEN='123456:ABC...'")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Использование:  python3 set_webhook.py https://ТВОЙ-ПРОЕКТ.vercel.app")
    sys.exit(1)

base_url = sys.argv[1].rstrip("/")
webhook_url = f"{base_url}/api/webhook"

print(f"📡 Устанавливаю webhook: {webhook_url}")

resp = httpx.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    data={"url": webhook_url},
    timeout=15,
)

data = resp.json()
if data.get("ok"):
    print(f"✅ Webhook установлен!")
    print(f"   URL: {webhook_url}")
    print(f"\n🎉 Бот работает. Открой Telegram и нажми /start")
else:
    print(f"❌ Ошибка: {data.get('description', 'неизвестная')}")
    sys.exit(1)
