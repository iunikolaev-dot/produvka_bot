"""
Vercel serverless function — Telegram webhook handler.
Stateless: previous answers are encoded into callback_data.

Flow:  /start → Welcome → Q1 (depth) → Q2 (tech) → Q3 (static) → Result

callback_data encoding:
  Q1 buttons:  "depth_zero", "depth_15", ...
  Q2 buttons:  "{depth}__tech_valsalva", ...
  Q3 buttons:  "{depth}__{tech}__static_0", ...

Level = min(depth_score, tech_score, static_score)
  0 → zero (beginner)
  1 → middle
  2+ → master
"""

import os
import json
import logging
from http.server import BaseHTTPRequestHandler

import httpx

from texts import (
    WELCOME_TEXT,
    QUESTION_1_TEXT,
    QUESTION_2_TEXT,
    QUESTION_3_TEXT,
    RECOMMENDATIONS,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Score maps ────────────────────────────────────────────────
DEPTH_SCORES = {
    "depth_zero": 0,
    "depth_15": 1,
    "depth_30": 2,
    "depth_30plus": 3,
}

TECH_SCORES = {
    "tech_valsalva": 0,
    "tech_frenzel": 1,
    "tech_mouthfill": 2,
}

STATIC_SCORES = {
    "static_0": 0,   # не замерял / < 1 мин
    "static_1": 1,   # 1–2 мин
    "static_2": 2,   # 2–3,5 мин
    "static_3": 3,   # 3,5+ мин
}


def determine_level(depth_key: str, tech_key: str, static_key: str) -> str:
    """Safety-first: уровень определяется самым слабым звеном."""
    combined = min(
        DEPTH_SCORES.get(depth_key, 0),
        TECH_SCORES.get(tech_key, 0),
        STATIC_SCORES.get(static_key, 0),
    )
    if combined == 0:
        return "zero"
    elif combined == 1:
        return "middle"
    else:
        return "master"


# ── Keyboards ─────────────────────────────────────────────────
def welcome_kb():
    return {
        "inline_keyboard": [
            [{"text": "Поехали! 🐋", "callback_data": "start_quiz"}]
        ]
    }


def depth_kb():
    return {
        "inline_keyboard": [
            [{"text": "🏖 Ещё не нырял(а) / только бассейн", "callback_data": "depth_zero"}],
            [{"text": "🐠 До 15 метров", "callback_data": "depth_15"}],
            [{"text": "🐬 15–30 метров", "callback_data": "depth_30"}],
            [{"text": "🐋 Больше 30 метров", "callback_data": "depth_30plus"}],
        ]
    }


def tech_kb(depth_key: str):
    """Q2 buttons carry depth answer."""
    return {
        "inline_keyboard": [
            [{"text": "🤷 Вальсальва (зажимаю нос и дую)",
              "callback_data": f"{depth_key}__tech_valsalva"}],
            [{"text": "👅 Френзель",
              "callback_data": f"{depth_key}__tech_frenzel"}],
            [{"text": "🐡 Маусфилл",
              "callback_data": f"{depth_key}__tech_mouthfill"}],
        ]
    }


def static_kb(depth_key: str, tech_key: str):
    """Q3 buttons carry both previous answers."""
    prefix = f"{depth_key}__{tech_key}"
    return {
        "inline_keyboard": [
            [{"text": "🌱 Не замерял(а) / меньше 1 минуты",
              "callback_data": f"{prefix}__static_0"}],
            [{"text": "⏱ 1–2 минуты",
              "callback_data": f"{prefix}__static_1"}],
            [{"text": "🫁 2–3,5 минуты",
              "callback_data": f"{prefix}__static_2"}],
            [{"text": "🧘 Больше 3,5 минут",
              "callback_data": f"{prefix}__static_3"}],
        ]
    }


def result_kb():
    return {
        "inline_keyboard": [
            [{"text": "🔄 Пройти заново", "callback_data": "restart"}],
            [{"text": "📩 Записаться на занятие",
              "url": "https://t.me/Olga_Rodnova"}],
        ]
    }


# ── Telegram API helpers ─────────────────────────────────────
def tg_send(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    httpx.post(f"{API}/sendMessage", data=payload, timeout=10)


def tg_edit(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    httpx.post(f"{API}/editMessageText", data=payload, timeout=10)


def tg_answer_callback(callback_query_id):
    httpx.post(
        f"{API}/answerCallbackQuery",
        data={"callback_query_id": callback_query_id},
        timeout=5,
    )


# ── Main handler ─────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        logger.info("Update: %s", json.dumps(body, ensure_ascii=False)[:500])

        try:
            self._process(body)
        except Exception:
            logger.exception("Error processing update")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def _process(self, update: dict):
        # ── /start ────────────────────────────────────────────
        msg = update.get("message")
        if msg:
            text = (msg.get("text") or "").strip()
            chat_id = msg["chat"]["id"]
            if text == "/start":
                tg_send(chat_id, WELCOME_TEXT, welcome_kb())
            else:
                tg_send(chat_id, "Нажми /start, чтобы начать 🤿")
            return

        # ── Callback queries ──────────────────────────────────
        cb = update.get("callback_query")
        if not cb:
            return

        tg_answer_callback(cb["id"])

        data = cb.get("data", "")
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]

        # «Поехали» / restart → Q1
        if data in ("start_quiz", "restart"):
            tg_edit(chat_id, message_id, QUESTION_1_TEXT, depth_kb())
            return

        parts = data.split("__")

        # Q1 answer (depth_*) → Q2
        if len(parts) == 1 and data in DEPTH_SCORES:
            tg_edit(chat_id, message_id, QUESTION_2_TEXT, tech_kb(data))
            return

        # Q2 answer (depth__tech) → Q3
        if len(parts) == 2:
            depth_key, tech_key = parts
            if depth_key in DEPTH_SCORES and tech_key in TECH_SCORES:
                tg_edit(
                    chat_id, message_id,
                    QUESTION_3_TEXT,
                    static_kb(depth_key, tech_key),
                )
                return

        # Q3 answer (depth__tech__static) → Result
        if len(parts) == 3:
            depth_key, tech_key, static_key = parts
            if (
                depth_key in DEPTH_SCORES
                and tech_key in TECH_SCORES
                and static_key in STATIC_SCORES
            ):
                level = determine_level(depth_key, tech_key, static_key)
                rec_text = RECOMMENDATIONS.get(level, RECOMMENDATIONS["zero"])
                tg_edit(chat_id, message_id, rec_text, result_kb())
                return
