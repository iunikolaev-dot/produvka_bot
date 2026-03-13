"""
Telegram-бот «Продувка» — определение уровня фридайвера
и персональные рекомендации по эквализации.

Запуск:
    export BOT_TOKEN="123456:ABC-DEF..."
    pip install aiogram
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
    RECOMMENDATIONS,
    WELCOME_TEXT,
)

# ──────────────────────────────────────────────
#  Логирование
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  FSM States
# ──────────────────────────────────────────────


class Quiz(StatesGroup):
    waiting_depth = State()  # ждём ответ на вопрос 1 (глубина)
    waiting_tech = State()   # ждём ответ на вопрос 2 (техника)


# ──────────────────────────────────────────────
#  Логика определения уровня
# ──────────────────────────────────────────────

DEPTH_SCORES = {
    "depth_zero": 0,     # нулевой
    "depth_15": 1,       # средний
    "depth_30": 2,       # средний-продвинутый
    "depth_30plus": 3,   # мастер
}

TECH_SCORES = {
    "tech_valsalva": 0,   # нулевой
    "tech_frenzel": 1,    # средний
    "tech_mouthfill": 2,  # мастер
}


def determine_level(depth: str, tech: str) -> str:
    """
    Матрица определения уровня.

    Приоритет: берём МИНИМАЛЬНЫЙ из двух сигналов.
    Безопаснее дать базовые рекомендации продвинутому,
    чем продвинутые рекомендации новичку.
    """
    d = DEPTH_SCORES.get(depth, 0)
    t = TECH_SCORES.get(tech, 0)
    combined = min(d, t)

    if combined == 0:
        return "zero"
    elif combined == 1:
        return "middle"
    else:
        return "master"


# ──────────────────────────────────────────────
#  Клавиатуры
# ──────────────────────────────────────────────


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
                text="🤷 Не знаю / зажимаю нос и дую",
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


# ──────────────────────────────────────────────
#  Роутер и хэндлеры
# ──────────────────────────────────────────────

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start — приветственное сообщение."""
    await state.clear()
    await message.answer(
        text=WELCOME_TEXT,
        reply_markup=welcome_keyboard(),
    )


@router.callback_query(F.data == "start_quiz")
async def on_start_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Поехали» — показываем вопрос 1."""
    await state.clear()
    await state.set_state(Quiz.waiting_depth)
    await callback.message.edit_text(
        text=QUESTION_1_TEXT,
        reply_markup=depth_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "restart")
async def on_restart(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Пройти заново» — начинаем с вопроса 1."""
    await state.clear()
    await state.set_state(Quiz.waiting_depth)
    await callback.message.edit_text(
        text=QUESTION_1_TEXT,
        reply_markup=depth_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    Quiz.waiting_depth,
    F.data.in_({"depth_zero", "depth_15", "depth_30", "depth_30plus"}),
)
async def on_depth_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """Ответ на вопрос 1 — сохраняем глубину, показываем вопрос 2."""
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
    """Ответ на вопрос 2 — определяем уровень и отправляем рекомендацию."""
    data = await state.get_data()
    depth = data.get("depth", "depth_zero")
    tech = callback.data

    level = determine_level(depth, tech)
    recommendation_text = RECOMMENDATIONS[level]

    logger.info(
        "Пользователь %s: depth=%s, tech=%s → level=%s",
        callback.from_user.id, depth, tech, level,
    )

    # Отправляем рекомендацию новым сообщением (текст длинный,
    # edit_text может не влезть из-за лимитов inline-сообщений)
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
    """Обработка неизвестных callback — предлагаем начать заново."""
    await callback.answer(
        text="Что-то пошло не так. Нажми /start, чтобы начать заново.",
        show_alert=True,
    )


@router.message()
async def on_any_message(message: Message, state: FSMContext) -> None:
    """Любое текстовое сообщение (кроме /start) — направляем к /start."""
    await message.answer(
        "Я работаю через кнопки. Нажми /start, чтобы начать."
    )


# ──────────────────────────────────────────────
#  Запуск
# ──────────────────────────────────────────────


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
