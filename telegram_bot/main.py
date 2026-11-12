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
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
                           KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove)

from .api import ApiError, BackendClient, NotLinked
from .config import load_settings
from .images import photos_for

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
    "/yaqin: eng yaqin sartaroshxonalar 📍\n"
    "Hoziroq kelmoqchi bo'lsangiz «navbat bormi?» deb yozing.\n"
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


async def send_hairstyle_photos(message: Message, names: list[str]) -> None:
    """Tavsiya etilgan turmaklarning tayyor rasmlari (Pexels). Xato bo'lsa, jim o'tib ketadi: matn allaqachon yuborilgan."""
    try:
        photos = await photos_for(settings.pexels_api_key, names)
        if len(photos) >= 2:
            await message.answer_media_group(
                [InputMediaPhoto(media=p["url"], caption=p["caption"]) for p in photos]
            )
        elif photos:
            await message.answer_photo(photos[0]["url"], caption=photos[0]["caption"])
    except TelegramAPIError:
        logger.warning("hairstyle: rasmlarni yuborib bo'lmadi", exc_info=True)


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
        await send_hairstyle_photos(message, [h["name"] for h in data["hairstyles"]])


LOCATION_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📍 Joylashuvimni yuborish", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


@dp.message(Command("yaqin"))
async def on_nearby_command(message: Message) -> None:
    await message.answer("Eng yaqin sartaroshxonalarni topish uchun joylashuvingizni yuboring.",
                         reply_markup=LOCATION_KEYBOARD)


def format_nearby(shops: list[dict]) -> str:
    if not shops:
        return "Yaqin atrofda (10 km) sartaroshxona topilmadi."
    lines = ["📍 Eng yaqin sartaroshxonalar:"]
    for s in shops:
        rating = f" ⭐{s['rating']}" if s.get("rating") else ""
        lines.append(f"\n{s['name']} — {s['distance_km']} km{rating}\n{s['address']}, {s['opens_at']}–{s['closes_at']}\n"
                     f"📞 {s['phone']}")
    lines.append("\nBron qilish uchun yozing, masalan: «ertaga kechqurun soch olish»")
    return "\n".join(lines)


@dp.message(F.location)
async def on_location(message: Message) -> None:
    try:
        shops = await backend.nearby_shops(message.location.latitude, message.location.longitude)
    except (ApiError, httpx.HTTPError):
        logger.exception("nearby: backend xatosi")
        await message.answer("Xizmat vaqtincha ishlamayapti, keyinroq urinib ko'ring.", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(format_nearby(shops), reply_markup=ReplyKeyboardRemove())


@dp.callback_query(F.data.startswith("rate:"))
async def on_rate(call: CallbackQuery) -> None:
    """Xizmatdan keyingi baho tugmalari: callback_data = rate:<booking_id>:<1-5>."""
    try:
        _, booking_id, rating = call.data.split(":")
        booking_id, rating = int(booking_id), int(rating)
    except ValueError:
        await call.answer()
        return
    try:
        token = await backend.get_token(call.from_user.id)
        await backend.post_review(token, booking_id, rating)
    except NotLinked:
        await call.answer("Avval raqamingizni yuboring (/start)", show_alert=True)
        return
    except ApiError as exc:
        # Masalan, sharh allaqachon yozilgan
        await call.answer("Bu bronga baho allaqachon berilgan" if exc.status == 400 else "Xatolik, keyinroq urinib ko'ring",
                          show_alert=True)
        return
    except httpx.HTTPError:
        logger.exception("rate: backend xatosi")
        await call.answer("Xizmat vaqtincha ishlamayapti", show_alert=True)
        return
    await call.answer("Rahmat!")
    if call.message:
        try:
            await call.message.edit_text(f"Rahmat! Bahoyingiz: {'⭐' * rating}")
        except TelegramAPIError:
            pass


def _rem_markup(booking_id: int, *codes: str) -> InlineKeyboardMarkup:
    """Eslatma tugmalari: c = kelaman, x = bekor qilaman, xy/xn = bekor qilishni tasdiqlash/qaytarish."""
    labels = {"c": "✅ Kelaman", "x": "❌ Bekor qilaman", "xy": "Ha, bekor qil", "xn": "Yo'q, qoldiraman"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels[c], callback_data=f"rem:{booking_id}:{c}") for c in codes]
    ])


CANCEL_QUESTION = "\n\nRostdan bekor qilasizmi?"


async def _rem_edit(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    if call.message:
        try:
            await call.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            logger.warning("rem: xabarni tahrirlab bo'lmadi")


@dp.callback_query(F.data.startswith("rem:"))
async def on_reminder(call: CallbackQuery) -> None:
    """Eslatma tugmalari: rem:<bron_id>:<c|l|x|xy|xn>. Bron faqat shu Telegram egasining o'ziniki bo'lsa o'zgaradi."""
    try:
        _, booking_id, code = call.data.split(":")
        booking_id = int(booking_id)
    except ValueError:
        await call.answer()
        return
    if code not in ("c", "l", "x", "xy", "xn"):
        await call.answer()
        return

    base = ((call.message.text or "") if call.message else "").split(CANCEL_QUESTION)[0]

    if code == "x":  # tasodifan bosib yubormaslik uchun avval so'raymiz
        await call.answer()
        await _rem_edit(call, base + CANCEL_QUESTION, _rem_markup(booking_id, "xy", "xn"))
        return
    if code == "xn":
        await call.answer("Bron saqlanib qoldi")
        await _rem_edit(call, base, _rem_markup(booking_id, "c", "x"))
        return

    try:
        token = await backend.get_token(call.from_user.id)
        if code == "xy":
            await backend.cancel_booking(token, booking_id)
        else:
            await backend.respond_booking(token, booking_id, "confirm" if code == "c" else "late", 10)
    except NotLinked:
        await call.answer("Avval raqamingizni yuboring (/start)", show_alert=True)
        return
    except ApiError as exc:
        # Masalan: bekor qilish muddati o'tgan, bron allaqachon bekor qilingan
        await call.answer(exc.detail[:190] if exc.status in (400, 404) else "Xatolik, keyinroq urinib ko'ring",
                          show_alert=True)
        if code == "xy":
            await _rem_edit(call, base, _rem_markup(booking_id, "c", "x"))
        return
    except httpx.HTTPError:
        logger.exception("rem: backend xatosi")
        await call.answer("Xizmat vaqtincha ishlamayapti", show_alert=True)
        return

    if code == "c":
        await call.answer("Rahmat!")
        await _rem_edit(call, base + "\n\n✅ Rahmat, sizni kutamiz!", _rem_markup(booking_id, "x"))
    elif code == "l":
        await call.answer("Ustaga xabar berdik")
        await _rem_edit(call, base + "\n\n⏱ Ustaga 10 daqiqa kechikishingiz haqida xabar berdik. Iltimos, undan ortiq kechikmang.",
                        _rem_markup(booking_id, "x"))
    else:
        await call.answer("Bron bekor qilindi")
        await _rem_edit(call, base + "\n\n❌ Bron bekor qilindi.", None)


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
