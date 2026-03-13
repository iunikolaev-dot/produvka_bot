"""
Telegram-бот «Продувка» — определение уровня фридайвера
и персональные рекомендации по эквализации.

3 вопроса: глубина → техника продувки → статика → результат.

Запуск:
    pip install -r requirements.txt
    python bot.py
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import BOT_TOKEN
from recommendations import (
    QUESTION_1_TEXT,
    QUESTION_2_TEXT,
    QUESTION_3_TEXT,
    RECOMMENDATIONS,
    WELCOME_TEXT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── FSM States ────────────────────────────────────────────────


class Quiz(StatesGroup):
    waiting_depth = State()
    waiting_tech = State()
    waiting_static = State()


# ── Scoring ───────────────────────────────────────────────────

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


def determine_level(depth: str, tech: str, static: str) -> str:
    """Уровень = самое слабое звено из трёх ответов."""
    combined = min(
        DEPTH_SCORES.get(depth, 0),
        TECH_SCORES.get(tech, 0),
        STATIC_SCORES.get(static, 0),
    )
    if combined == 0:
        return "zero"
    elif combined == 1:
        return "middle"
    else:
        return "master"


# ── Keyboards ─────────────────────────────────────────────────


def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали! 🐋", callback_data="start_quiz")],
        ]
    )


def depth_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🏖 Ещё не нырял(а) / только бассейн",
                callback_data="depth_zero",
            )],
            [InlineKeyboardButton(
                text="🐠 До 15 метров",
                callback_data="depth_15",
            )],
            [InlineKeyboardButton(
                text="🐬 15–30 метров",
                callback_data="depth_30",
            )],
            [InlineKeyboardButton(
                text="🐋 Больше 30 метров",
                callback_data="depth_30plus",
            )],
        ]
    )


def tech_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🤷 Вальсальва (зажимаю нос и дую)",
                callback_data="tech_valsalva",
            )],
            [InlineKeyboardButton(
                text="👅 Френзель",
                callback_data="tech_frenzel",
            )],
            [InlineKeyboardButton(
                text="🐡 Маусфилл",
                callback_data="tech_mouthfill",
            )],
        ]
    )


def static_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🌱 Не замерял(а) / меньше 1 минуты",
                callback_data="static_0",
            )],
            [InlineKeyboardButton(
                text="⏱ 1–2 минуты",
                callback_data="static_1",
            )],
            [InlineKeyboardButton(
                text="🫁 2–3,5 минуты",
                callback_data="static_2",
            )],
            [InlineKeyboardButton(
                text="🧘 Больше 3,5 минут",
                callback_data="static_3",
            )],
        ]
    )


def result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Пройти заново",
                callback_data="restart",
            )],
            [InlineKeyboardButton(
                text="📩 Записаться на занятие",
                url="https://t.me/Olga_Rodnova",
            )],
        ]
    )


# ── Router & Handlers ─────────────────────────────────────────

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        text=WELCOME_TEXT,
        reply_markup=welcome_keyboard(),
    )


@router.callback_query(F.data == "start_quiz")
async def on_start_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Quiz.waiting_depth)
    await callback.message.edit_text(
        text=QUESTION_1_TEXT,
        reply_markup=depth_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "restart")
async def on_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Quiz.waiting_depth)
    await callback.message.edit_text(
        text=QUESTION_1_TEXT,
        reply_markup=depth_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    Quiz.waiting_depth,
    F.data.in_({"depth_zero", "depth_15", "depth_30", "depth_30plus"}),
)
async def on_depth_answer(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(depth=callback.data)
    await state.set_state(Quiz.waiting_tech)
    await callback.message.edit_text(
        text=QUESTION_2_TEXT,
        reply_markup=tech_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    Quiz.waiting_tech,
    F.data.in_({"tech_valsalva", "tech_frenzel", "tech_mouthfill"}),
)
async def on_tech_answer(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(tech=callback.data)
    await state.set_state(Quiz.waiting_static)
    await callback.message.edit_text(
        text=QUESTION_3_TEXT,
        reply_markup=static_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    Quiz.waiting_static,
    F.data.in_({"static_0", "static_1", "static_2", "static_3"}),
)
async def on_static_answer(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    depth = data.get("depth", "depth_zero")
    tech = data.get("tech", "tech_valsalva")
    static = callback.data

    level = determine_level(depth, tech, static)
    recommendation_text = RECOMMENDATIONS[level]

    logger.info(
        "Пользователь %s: depth=%s, tech=%s, static=%s → level=%s",
        callback.from_user.id, depth, tech, static, level,
    )

    await callback.message.edit_text(
        text="⏳ Анализирую ответы...",
    )
    await callback.message.answer(
        text=recommendation_text,
        reply_markup=result_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    await state.clear()
    await callback.answer()


@router.callback_query()
async def on_unknown_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer(
        text="Что-то пошло не так. Нажми /start, чтобы начать заново.",
        show_alert=True,
    )


@router.message()
async def on_any_message(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Я работаю через кнопки. Нажми /start, чтобы начать."
    )


# ── Start ─────────────────────────────────────────────────────


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запущен (polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
