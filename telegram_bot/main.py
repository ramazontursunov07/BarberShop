"""Telegram bot: mijoz oddiy gapirib bron qiladi, gap AI agentga (/api/ai/chat/) uzatiladi.

Ishga tushirish (loyiha ildizidan, Django server ishlab turganda):
    python -m telegram_bot.main
"""
import asyncio
import logging
from collections import defaultdict, deque

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from .api import ApiError, BackendClient, NotLinked
from .config import load_settings

logger = logging.getLogger("telegram_bot")

HISTORY_LEN = 20  # API ham oxirgi 20 xabarni qabul qiladi

settings = load_settings()
backend = BackendClient(settings.api_base_url, settings.bot_secret)
dp = Dispatcher()

# Suhbat tarixi xotirada saqlanadi: bot qayta ishga tushsa, suhbat yangidan boshlanadi
histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LEN))
locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

CONTACT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

WELCOME = (
    "Salom! Men sartaroshxona bron yordamchisiman.\n"
    "Oddiy gapiring, masalan: «Ertaga kechqurun soch olish kerak, Jasur akaga».\n\n"
    "/reset: suhbatni yangidan boshlash"
)
ASK_CONTACT = "Boshlash uchun pastdagi tugma orqali telefon raqamingizni yuboring."


async def ask_contact(message: Message) -> None:
    await message.answer(ASK_CONTACT, reply_markup=CONTACT_KEYBOARD)


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    try:
        await backend.get_token(message.from_user.id)
    except NotLinked:
        await ask_contact(message)
        return
    except (ApiError, httpx.HTTPError):
        logger.exception("start: backend xatosi")
        await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
        return
    await message.answer(WELCOME)


@dp.message(Command("reset"))
async def on_reset(message: Message) -> None:
    histories.pop(message.from_user.id, None)
    await message.answer("Suhbat yangidan boshlandi.")


@dp.message(F.contact)
async def on_contact(message: Message) -> None:
    contact = message.contact
    # Faqat o'z kontaktini yuborgan bo'lsa qabul qilamiz (birovning raqamini yuborib bo'lmaydi)
    if contact.user_id != message.from_user.id:
        await message.answer("Iltimos, tugma orqali o'zingizning raqamingizni yuboring.")
        return
    try:
        await backend.get_token(
            message.from_user.id,
            phone=contact.phone_number,
            first_name=contact.first_name or message.from_user.first_name or "",
            last_name=contact.last_name or "",
        )
    except ApiError as exc:
        if exc.status in (400, 409):
            await message.answer(exc.detail, reply_markup=ReplyKeyboardRemove())
        else:
            logger.error("contact: backend xatosi %s", exc)
            await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
        return
    except httpx.HTTPError:
        logger.exception("contact: backendga ulanib bo'lmadi")
        await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
        return
    await message.answer("Raqamingiz tasdiqlandi ✅\n\n" + WELCOME, reply_markup=ReplyKeyboardRemove())


@dp.message(F.voice)
async def on_voice(message: Message) -> None:
    await message.answer("Ovozli xabarlar hali qo'llab-quvvatlanmaydi. Iltimos, matn yozing.")


@dp.message(F.text)
async def on_text(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    text = message.text.strip()
    if not text:
        return

    async with locks[user_id]:  # bir foydalanuvchining xabarlari ketma-ket ishlanadi
        try:
            token = await backend.get_token(user_id)
        except NotLinked:
            await ask_contact(message)
            return
        except (ApiError, httpx.HTTPError):
            logger.exception("auth: backend xatosi")
            await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
            return

        await bot.send_chat_action(message.chat.id, "typing")
        try:
            reply = await backend.chat(token, text, list(histories[user_id]))
        except ApiError as exc:
            if exc.status == 429:
                await message.answer("Hozir juda ko'p so'rov bor, birozdan keyin qayta yozing.")
            elif exc.status == 400:
                await message.answer(exc.detail)
            else:
                logger.error("chat: backend xatosi %s", exc)
                await message.answer("AI yordamchi vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
            return
        except httpx.HTTPError:
            logger.exception("chat: backendga ulanib bo'lmadi")
            await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
            return

        history = histories[user_id]
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        await message.answer(reply)  # oddiy matn: LLM belgilari Telegram formatini buzmasin


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=settings.bot_token)
    try:
        await dp.start_polling(bot)
    finally:
        await backend.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
