"""Telegram bot: mijoz oddiy gapirib bron qiladi, gap AI agentga (/api/ai/chat/) uzatiladi.

Ishga tushirish (loyiha ildizidan, Django server ishlab turganda):
    python -m telegram_bot.main
"""
import asyncio
import io
import logging
from collections import defaultdict, deque

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from .api import ApiError, BackendClient, NotLinked
from .config import load_settings

logger = logging.getLogger("telegram_bot")

HISTORY_LEN = 20  # API ham oxirgi 20 xabarni qabul qiladi
MAX_VOICE_SECONDS = 60
MAX_VOICE_BYTES = 2 * 1024 * 1024  # serverdagi chegara bilan bir xil
MAX_PHOTO_BYTES = 4 * 1024 * 1024  # serverdagi chegara bilan bir xil

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
    "Oddiy gapiring, masalan: «Ertaga kechqurun soch olish kerak, Jasur akaga». "
    "Ovozli xabar ham yuborishingiz mumkin 🎤\n"
    "Selfi yuborsangiz, yuz shakliga mos soch turmagini tavsiya qilaman 📸\n\n"
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


async def get_token_or_prompt(message: Message) -> str | None:
    """Foydalanuvchi tokenini oladi. Bog'lanmagan bo'lsa raqam so'raydi; None qaytarsa, javob berib bo'lingan."""
    try:
        return await backend.get_token(message.from_user.id)
    except NotLinked:
        await ask_contact(message)
    except (ApiError, httpx.HTTPError):
        logger.exception("auth: backend xatosi")
        await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
    return None


async def chat_round(message: Message, bot: Bot, user_id: int, token: str, text: str) -> None:
    """Matnni AI agentga yuboradi va javobni qaytaradi (matnli va ovozli xabar uchun umumiy)."""
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


@dp.message(F.voice)
async def on_voice(message: Message, bot: Bot) -> None:
    voice = message.voice
    if voice.duration > MAX_VOICE_SECONDS or (voice.file_size or 0) > MAX_VOICE_BYTES:
        await message.answer(f"Ovozli xabar juda uzun. {MAX_VOICE_SECONDS} soniyagacha qisqaroq yuboring.")
        return

    user_id = message.from_user.id
    async with locks[user_id]:
        token = await get_token_or_prompt(message)
        if token is None:
            return

        await bot.send_chat_action(message.chat.id, "typing")
        buffer = io.BytesIO()
        try:
            await bot.download(voice, destination=buffer)
        except TelegramAPIError:
            logger.exception("voice: faylni yuklab bo'lmadi")
            await message.answer("Ovozli xabarni olib bo'lmadi, qayta yuboring yoki matn yozing.")
            return

        try:
            text = await backend.transcribe(token, buffer.getvalue())
        except ApiError as exc:
            if exc.status == 422:
                await message.answer("Ovozni tushunolmadim. Qayta, aniqroq gapiring yoki matn yozing.")
            elif exc.status == 429:
                await message.answer("Hozir juda ko'p so'rov bor, birozdan keyin qayta yuboring.")
            elif exc.status == 503:
                await message.answer("Ovozli xabarlar hozir ishlamayapti. Iltimos, matn yozing.")
            else:
                logger.error("voice: backend xatosi %s", exc)
                await message.answer("Ovozni matnga aylantirib bo'lmadi. Iltimos, matn yozing.")
            return
        except httpx.HTTPError:
            logger.exception("voice: backendga ulanib bo'lmadi")
            await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
            return

        # Tanilgan matnni ko'rsatamiz: noto'g'ri tanilsa, mijoz darhol sezadi va to'g'rilaydi
        await message.answer(f"🎤 Eshitdim: «{text}»")
        await chat_round(message, bot, user_id, token, text)


def format_hairstyles(data: dict) -> str:
    lines = [f"📸 Yuz shakli: {data['face_shape_name']}", "", "Sizga mos turmaklar:"]
    lines += [f"• {h['name']}: {h['why']}" for h in data["hairstyles"]]
    if data.get("avoid"):
        lines += ["", "Tavsiya etilmaydi: " + "; ".join(data["avoid"])]
    if data.get("note"):
        lines += ["", data["note"]]
    lines += ["", "Bu umumiy tavsiya, yakuniy qarorni usta bilan maslahatlashing. "
                  "Yozilmoqchi bo'lsangiz, masalan: «Ertaga kechqurun soch olish»."]
    return "\n".join(lines)


@dp.message(F.photo)
async def on_photo(message: Message, bot: Bot) -> None:
    photo = message.photo[-1]  # eng katta o'lcham
    if (photo.file_size or 0) > MAX_PHOTO_BYTES:
        await message.answer("Rasm juda katta. Kichikroq selfi yuboring.")
        return

    user_id = message.from_user.id
    async with locks[user_id]:
        token = await get_token_or_prompt(message)
        if token is None:
            return

        await bot.send_chat_action(message.chat.id, "typing")
        buffer = io.BytesIO()
        try:
            await bot.download(photo, destination=buffer)
        except TelegramAPIError:
            logger.exception("photo: faylni yuklab bo'lmadi")
            await message.answer("Rasmni olib bo'lmadi, qayta yuboring.")
            return

        try:
            data = await backend.face_shape(token, buffer.getvalue())
        except ApiError as exc:
            if exc.status in (400, 413, 422):
                await message.answer(exc.detail)
            elif exc.status == 429:
                await message.answer("Hozir juda ko'p so'rov bor, birozdan keyin qayta yuboring.")
            else:
                logger.error("photo: backend xatosi %s", exc)
                await message.answer("Rasmni tahlil qilib bo'lmadi, keyinroq urinib ko'ring.")
            return
        except httpx.HTTPError:
            logger.exception("photo: backendga ulanib bo'lmadi")
            await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.")
            return
        await message.answer(format_hairstyles(data))


@dp.message(F.text)
async def on_text(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    text = message.text.strip()
    if not text:
        return

    async with locks[user_id]:  # bir foydalanuvchining xabarlari ketma-ket ishlanadi
        token = await get_token_or_prompt(message)
        if token is None:
            return
        await chat_round(message, bot, user_id, token, text)


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
