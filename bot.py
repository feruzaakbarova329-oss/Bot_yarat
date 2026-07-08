
import os
import json
import asyncio
import logging
import httpx
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from io import BytesIO
import numpy as np
import cv2
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

MAIN_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # bosh administrator (siz)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")  # masalan: ravshan_uzz (@ belgisiz)


def admin_contact_url() -> str:
    if ADMIN_USERNAME:
        return f"https://t.me/{ADMIN_USERNAME}"
    return f"tg://user?id={ADMIN_ID}"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
DATA_FILE = "bots_data.json"
TRIAL_DAYS = 7

logging.basicConfig(level=logging.INFO)

main_bot = Bot(token=MAIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
main_dp = Dispatcher(storage=MemoryStorage())

BOT_TYPES = {
    "kino": "🎬 Kino bot",
    "shop": "🛒 Savdo bot",
    "ai": "🤖 AI-yordamchi bot",
    "post": "📢 E'lon/Xabar bot",
    "money": "💱 Pul (valyuta) bot",
    "translate": "🌐 Tarjimon bot",
    "contact": "📞 Aloqa bot",
    "survey": "📝 Anketa bot",
    "taxi": "🚕 Taxi bot",
    "test": "🎓 Ta'lim/Test bot",
    "fitness": "🏋️ Fitnes/Dieta bot",
    "prayer": "🕌 Namoz vaqtlari bot",
    "weather": "🌤 Ob-havo bot",
    "football": "⚽ Futbol natijalar bot",
    "cars": "🚗 Avtomobil e'lonlari bot",
}

DEFAULT_PRICES = {
    "kino": 120_000,
    "ai": 120_000,
    "shop": 120_000,
    "post": 120_000,
    "money": 120_000,
    "translate": 120_000,
    "contact": 120_000,
    "survey": 120_000,
    "taxi": 120_000,
    "test": 120_000,
    "fitness": 120_000,
    "prayer": 120_000,
    "weather": 120_000,
    "football": 120_000,
    "cars": 120_000,
}
MONTHLY_RATE = 0.2  # keyingi oylar uchun narxning 20 foizi (24,000 so'm/oy)

running_bots = {}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"bots": {}, "next_bot_id": 1}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()
data.setdefault("next_bot_id", 1)
data.setdefault("prices", dict(DEFAULT_PRICES))
data.setdefault("global_buttons", [])  # [{"label": "...", "response": "..."}]
for _key, _val in DEFAULT_PRICES.items():
    data["prices"].setdefault(_key, _val)


def get_price(bot_type: str) -> int:
    return data["prices"].get(bot_type, DEFAULT_PRICES.get(bot_type, 0))


def is_active(info: dict) -> bool:
    paid_until = info.get("paid_until")
    if paid_until and datetime.now() < datetime.fromisoformat(paid_until):
        return True
    created = datetime.fromisoformat(info["created_at"])
    return datetime.now() < created + timedelta(days=TRIAL_DAYS)


def next_payment_amount(info: dict) -> int:
    """Birinchi to'lov — to'liq narx. Keyingi to'lovlar — 20 foiz."""
    price = get_price(info["type"])
    if info.get("paid_until"):
        return int(price * MONTHLY_RATE)
    return price


async def ask_gemini_chat(contents: list) -> str:
    headers = {"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"}
    payload = {"contents": contents}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GEMINI_URL, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]

async def ask_gemini(prompt: str) -> str:
    return await ask_gemini_chat([{"role": "user", "parts": [{"text": prompt}]}])


# ---------- Holatlar (FSM) ----------
class NewBotFlow(StatesGroup):
    waiting_token = State()


class EditPrice(StatesGroup):
    waiting_amount = State()


class GlobalButtonAdd(StatesGroup):
    waiting_label = State()
    waiting_response = State()


class BMIFlow(StatesGroup):
    waiting_weight = State()
    waiting_height = State()


class CityFlow(StatesGroup):
    waiting_city = State()


class AddMovie(StatesGroup):
    waiting_code = State()
    waiting_desc = State()
    waiting_video = State()


class AddProduct(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_barcode = State()


class Checkout(StatesGroup):
    waiting_address = State()
    waiting_phone = State()


class PostFlow(StatesGroup):
    waiting_text = State()
    waiting_confirm = State()


class AddChannel(StatesGroup):
    waiting_username = State()


class CurrencyAdd(StatesGroup):
    waiting_code = State()
    waiting_rate = State()


class CurrencyUpdate(StatesGroup):
    waiting_rate = State()


class MoneyAmount(StatesGroup):
    waiting_amount = State()


class SurveyAdmin(StatesGroup):
    waiting_question = State()


class SurveyAnswer(StatesGroup):
    answering = State()


class TaxiFlow(StatesGroup):
    waiting_from = State()
    waiting_to = State()
    waiting_phone = State()


class TestAdmin(StatesGroup):
    waiting_question = State()
    waiting_options = State()
    waiting_correct = State()


class TestAnswer(StatesGroup):
    answering = State()


class PrayerCity(StatesGroup):
    waiting_city = State()


class WeatherCity(StatesGroup):
    waiting_city = State()


class FootballAdmin(StatesGroup):
    waiting_match = State()
    waiting_score = State()
    waiting_date = State()


class CarAdFlow(StatesGroup):
    waiting_brand = State()
    waiting_year = State()
    waiting_price = State()
    waiting_phone = State()


class AddAdmin(StatesGroup):
    waiting_id = State()


def is_admin(info: dict, uid: int) -> bool:
    return uid in info.get("admin_ids", [info.get("admin_id")])


def admins_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm_add")],
        [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="➖ Adminni o'chirish", callback_data="adm_del")],
    ])


def setup_admin_management(dp: Dispatcher, token: str):
    info = data["bots"][token]
    info.setdefault("admin_ids", [info.get("admin_id")])
    owner_id = info["admin_id"]

    @dp.message(Command("cancel"))
    async def cancel_cmd(message: Message, state: FSMContext):
        current = await state.get_state()
        if current is None:
            await message.answer("Bekor qilinadigan jarayon yo'q.")
            return
        await state.clear()
        await message.answer("❌ Jarayon bekor qilindi.")

    @dp.message(Command("admins"))
    @dp.message(F.text == "👤 Adminlar")
    async def admins_panel(message: Message):
        if not is_admin(info, message.from_user.id):
            return
        await message.answer("👤 Adminlar boshqaruvi:", reply_markup=admins_kb())

    @dp.callback_query(F.data == "adm_add")
    async def adm_add_cb(callback: CallbackQuery, state: FSMContext):
        if not is_admin(info, callback.from_user.id):
            return
        await callback.message.answer("Yangi admin Telegram ID'ini yuboring (/myid orqali bilib olish mumkin):")
        await state.set_state(AddAdmin.waiting_id)
        await callback.answer()

    @dp.message(AddAdmin.waiting_id)
    async def adm_add_process(message: Message, state: FSMContext):
        try:

new_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting.")
            return
        if new_id not in info["admin_ids"]:
            info["admin_ids"].append(new_id)
            save_data()
        await message.answer(f"✅ Admin qo'shildi: {new_id}")
        await state.clear()

    @dp.callback_query(F.data == "adm_list")
    async def adm_list_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        lines = []
        for aid in info["admin_ids"]:
            tag = " (asosiy)" if aid == owner_id else ""
            lines.append(f"• {aid}{tag}")
        await callback.message.answer("👤 Adminlar:\n\n" + "\n".join(lines))
        await callback.answer()

    @dp.callback_query(F.data == "adm_del")
    async def adm_del_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        removable = [aid for aid in info["admin_ids"] if aid != owner_id]
        if not removable:
            await callback.message.answer("O'chirish uchun qo'shimcha admin yo'q.")
            await callback.answer()
            return
        buttons = [[InlineKeyboardButton(text=str(aid), callback_data=f"admdel_{aid}")] for aid in removable]
        await callback.message.answer("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    @dp.callback_query(F.data.startswith("admdel_"))
    async def adm_delid_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        target_id = int(callback.data.split("_", 1)[1])
        if target_id in info["admin_ids"] and target_id != owner_id:
            info["admin_ids"].remove(target_id)
            save_data()
            await callback.message.answer(f"🗑 Admin o'chirildi: {target_id}")
        await callback.answer()


# ---------- Majburiy obuna (barcha botlar uchun umumiy) ----------
def channels_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch_add")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="ch_list")],
        [InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="ch_del")],
    ])


async def get_missing_channels(bot: Bot, channels: dict, user_id: int):
    missing = []
    for chat_id, info in channels.items():
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                missing.append(info)
        except Exception as e:
            logging.error(f"Obuna tekshirishda xato ({chat_id}): {e}")
            # Xatolik bo'lsa ham xavfsiz tomonni tanlaymiz — obuna talab qilinadi
            missing.append(info)
    return missing


def subscribe_kb(missing):
    buttons = [[InlineKeyboardButton(text=info["title"], url=f"https://t.me/{info['username'].lstrip('@')}")] for info in missing]
    buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def require_subscription(event, info: dict, admin_id: int) -> bool:
    uid = event.from_user.id
    if is_admin(info, uid):
        return True
    channels = info.get("channels", {})
    if not channels:
        return True
    missing = await get_missing_channels(event.bot, channels, uid)
    if missing:
        kb = subscribe_kb(missing)
        text = "Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:"
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)
        return False
    return True

async def check_active(event, info: dict, admin_id: int) -> bool:
    """True bo'lsa - bot ishlaydi. False bo'lsa - sinov tugagan / to'lov kerak."""
    if is_active(info):
        return True
    uid = event.from_user.id
    amount = next_payment_amount(info)
    is_renewal = bool(info.get("paid_until"))
    kb = None
    if is_admin(info, uid):
        kb = contact_admin_kb()
        if is_renewal:
            text = (
                f"⏳ <b>Oylik to'lov muddati tugadi.</b>\n\n"
                f"Davom ettirish uchun: <b>{amount:,} so'm</b> (oylik, narxning 20%).\n\n"
                "To'lovni amalga oshirish uchun administrator bilan bog'laning."
            )
        else:
            text = (
                f"⏳ <b>Bepul sinov muddati tugadi.</b>\n\n"
                f"Ushbu bot ({BOT_TYPES.get(info['type'])}) boshlang'ich narxi: <b>{amount:,} so'm</b>.\n"
                f"Keyingi oylardan boshlab: {int(get_price(info['type']) * MONTHLY_RATE):,} so'm/oy.\n\n"
                "To'lovni amalga oshirish uchun administrator bilan bog'laning."
            )
    else:
        text = "🚧 Bot vaqtincha ishlamayapti."
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)
    return False


def setup_subscription_handlers(dp: Dispatcher, token: str, admin_id: int):
    info = data["bots"][token]
    info.setdefault("channels", {})

    @dp.callback_query(F.data == "ch_add")
    async def ch_add_cb(callback: CallbackQuery, state: FSMContext):
        if not is_admin(info, callback.from_user.id):
            return
        await callback.message.answer(
            "Kanal usernameni yuboring (masalan: @mening_kanalim).\n"
            "⚠️ Bot o'sha kanalda ADMIN bo'lishi shart!"
        )
        await state.set_state(AddChannel.waiting_username)
        await callback.answer()

    @dp.message(AddChannel.waiting_username)
    async def ch_add_process(message: Message, state: FSMContext):
        if not is_admin(info, message.from_user.id):
            return
        username = message.text.strip()
        try:
            chat = await message.bot.get_chat(username)
            info["channels"][str(chat.id)] = {"username": username, "title": chat.title}
            save_data()
            await message.answer(f"✅ Qo'shildi: {chat.title}")

            # Bot o'sha kanalda ADMIN ekanligini darhol tekshiramiz
            try:
                bot_member = await message.bot.get_chat_member(chat_id=chat.id, user_id=message.bot.id)
                if bot_member.status not in ("administrator", "creator"):
                    await message.answer(
                        f"⚠️ <b>Diqqat!</b> Bot \"{chat.title}\" kanalida ADMIN emas.\n"
                        "Obuna tekshiruvi ishlashi uchun botni o'sha kanalga ADMIN qilib qo'ying!"
                    )
            except Exception:
                await message.answer(
                    f"⚠️ <b>Diqqat!</b> Bot \"{chat.title}\" kanalida ADMIN ekanligini tekshira olmadim.\n"
                    "Iltimos, botni o'sha kanalga ADMIN qilib qo'ying, aks holda obuna tekshiruvi ishlamaydi!"
                )
        except Exception as e:
            await message.answer(f"❌ Xatolik: kanal topilmadi.\n{e}")
        await state.clear()

    @dp.callback_query(F.data == "ch_list")
    async def ch_list_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        if not info["channels"]:
            await callback.message.answer("Hozircha majburiy kanallar yo'q.")
        else:
            text = "📋 Majburiy obuna kanallari:\n\n" + "\n".join(
                f"• {c['title']} ({c['username']})" for c in info["channels"].values()
            )
            await callback.message.answer(text)
        await callback.answer()

@dp.callback_query(F.data == "ch_del")
    async def ch_del_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        if not info["channels"]:
            await callback.message.answer("O'chirish uchun kanal yo'q.")
            await callback.answer()
            return
        buttons = [[InlineKeyboardButton(text=c["title"], callback_data=f"chdel_{cid}")] for cid, c in info["channels"].items()]
        await callback.message.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    @dp.callback_query(F.data.startswith("chdel_"))
    async def ch_delid_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        cid = callback.data.split("_", 1)[1]
        removed = info["channels"].pop(cid, None)
        save_data()
        if removed:
            await callback.message.answer(f"🗑 O'chirildi: {removed['title']}")
        await callback.answer()

    @dp.callback_query(F.data == "check_sub")
    async def check_sub_cb(callback: CallbackQuery):
        missing = await get_missing_channels(callback.bot, info["channels"], callback.from_user.id)
        if missing:
            await callback.answer("Hali barcha kanallarga obuna bo'lmagansiz ❌", show_alert=True)
        else:
            await callback.message.edit_text("✅ Rahmat! Endi /start bosib davom eting.")
            await callback.answer()

    @dp.message(Command("channels"))
    @dp.message(F.text == "📡 Majburiy obuna")
    async def channels_panel(message: Message):
        if not is_admin(info, message.from_user.id):
            return
        await message.answer("📡 Majburiy obuna boshqaruvi:", reply_markup=channels_admin_kb())


# ---------- Bosh (creator) bot — XALQ UCHUN OMMAVIY ----------
def types_kb():
    buttons = [[InlineKeyboardButton(text=f"{name} — {get_price(key):,} so'm/oy", callback_data=f"type_{key}")] for key, name in BOT_TYPES.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def contact_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Admin bilan bog'lanish", url=admin_contact_url())]
    ])


@main_dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


@main_dp.message(Command("start"))
async def main_start(message: Message):
    price_lines = "\n".join(f"{BOT_TYPES[key]} — {get_price(key):,} so'm" for key in BOT_TYPES)
    text = (
        "🤖 <b>Bot yaratuvchi platformaga xush kelibsiz!</b>\n\n"
        "Bu yerda bir necha daqiqada o'zingizga kerakli botni yaratishingiz mumkin.\n\n"
        "💳 <b>Boshlang'ich narxlar:</b>\n"
        f"{price_lines}\n\n"
        f"📅 Keyingi oylardan boshlab — narxning atigi {int(MONTHLY_RATE*100)}%.\n"
        f"🎁 Har bir bot uchun {TRIAL_DAYS} kunlik BEPUL sinov muddati bor!\n\n"
        "💳 To'lov usuli: administrator bilan bog'lanish\n\n"
        "Bot yaratish: /newbot\n"
        "Botlaringiz: /mybots"
    )
    await message.answer(text, reply_markup=contact_admin_kb())


@main_dp.message(Command("newbot"))
async def newbot_start(message: Message, state: FSMContext):
    await message.answer(
        "Yangi bot tokenini yuboring.\n"
        "(@BotFather orqali /newbot bilan yaratib, tokenni shu yerga joylashtiring)"
    )
    await state.set_state(NewBotFlow.waiting_token)


@main_dp.message(NewBotFlow.waiting_token)
async def newbot_token(message: Message, state: FSMContext):
    token = message.text.strip()
    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer("❌ Token noto'g'ri. Qaytadan yuboring.")
        return

    await state.update_data(token=token, bot_name=me.first_name)
    await message.answer(f"✅ Bot topildi: <b>{me.first_name}</b>\n\nEndi bot turini tanlang:", reply_markup=types_kb())

@main_dp.callback_query(F.data.startswith("type_"))
async def newbot_type(callback: CallbackQuery, state: FSMContext):
    bot_type = callback.data.split("_", 1)[1]
    state_data = await state.get_data()
    token = state_data.get("token")
    bot_name = state_data.Ravshan:
import os
import json
import asyncio
import logging
import httpx
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from io import BytesIO
import numpy as np
import cv2
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

MAIN_BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # bosh administrator (siz)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")  # masalan: ravshan_uzz (@ belgisiz)


def admin_contact_url() -> str:
    if ADMIN_USERNAME:
        return f"https://t.me/{ADMIN_USERNAME}"
    return f"tg://user?id={ADMIN_ID}"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
DATA_FILE = "bots_data.json"
TRIAL_DAYS = 7

logging.basicConfig(level=logging.INFO)

main_bot = Bot(token=MAIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
main_dp = Dispatcher(storage=MemoryStorage())

BOT_TYPES = {
    "kino": "🎬 Kino bot",
    "shop": "🛒 Savdo bot",
    "ai": "🤖 AI-yordamchi bot",
    "post": "📢 E'lon/Xabar bot",
    "money": "💱 Pul (valyuta) bot",
    "translate": "🌐 Tarjimon bot",
    "contact": "📞 Aloqa bot",
    "survey": "📝 Anketa bot",
    "taxi": "🚕 Taxi bot",
    "test": "🎓 Ta'lim/Test bot",
    "fitness": "🏋️ Fitnes/Dieta bot",
    "prayer": "🕌 Namoz vaqtlari bot",
    "weather": "🌤 Ob-havo bot",
    "football": "⚽ Futbol natijalar bot",
    "cars": "🚗 Avtomobil e'lonlari bot",
}

DEFAULT_PRICES = {
    "kino": 120_000,
    "ai": 120_000,
    "shop": 120_000,
    "post": 120_000,
    "money": 120_000,
    "translate": 120_000,
    "contact": 120_000,
    "survey": 120_000,
    "taxi": 120_000,
    "test": 120_000,
    "fitness": 120_000,
    "prayer": 120_000,
    "weather": 120_000,
    "football": 120_000,
    "cars": 120_000,
}
MONTHLY_RATE = 0.2  # keyingi oylar uchun narxning 20 foizi (24,000 so'm/oy)

running_bots = {}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"bots": {}, "next_bot_id": 1}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()
data.setdefault("next_bot_id", 1)
data.setdefault("prices", dict(DEFAULT_PRICES))
data.setdefault("global_buttons", [])  # [{"label": "...", "response": "..."}]
for _key, _val in DEFAULT_PRICES.items():
    data["prices"].setdefault(_key, _val)


def get_price(bot_type: str) -> int:
    return data["prices"].get(bot_type, DEFAULT_PRICES.get(bot_type, 0))


def is_active(info: dict) -> bool:
    paid_until = info.get("paid_until")
    if paid_until and datetime.now() < datetime.fromisoformat(paid_until):
        return True
    created = datetime.fromisoformat(info["created_at"])
    return datetime.now() < created + timedelta(days=TRIAL_DAYS)


def next_payment_amount(info: dict) -> int:
    """Birinchi to'lov — to'liq narx. Keyingi to'lovlar — 20 foiz."""
    price = get_price(info["type"])
    if info.get("paid_until"):
        return int(price * MONTHLY_RATE)
    return price


async def ask_gemini_chat(contents: list) -> str:
    headers = {"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"}
    payload = {"contents": contents}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GEMINI_URL, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]

async def ask_gemini(prompt: str) -> str:
    return await ask_gemini_chat([{"role": "user", "parts": [{"text": prompt}]}])


# ---------- Holatlar (FSM) ----------
class NewBotFlow(StatesGroup):
    waiting_token = State()


class EditPrice(StatesGroup):
    waiting_amount = State()


class GlobalButtonAdd(StatesGroup):
    waiting_label = State()
    waiting_response = State()


class BMIFlow(StatesGroup):
    waiting_weight = State()
    waiting_height = State()


class CityFlow(StatesGroup):
    waiting_city = State()


class AddMovie(StatesGroup):
    waiting_code = State()
    waiting_desc = State()
    waiting_video = State()


class AddProduct(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_barcode = State()


class Checkout(StatesGroup):
    waiting_address = State()
    waiting_phone = State()


class PostFlow(StatesGroup):
    waiting_text = State()
    waiting_confirm = State()


class AddChannel(StatesGroup):
    waiting_username = State()


class CurrencyAdd(StatesGroup):
    waiting_code = State()
    waiting_rate = State()


class CurrencyUpdate(StatesGroup):
    waiting_rate = State()


class MoneyAmount(StatesGroup):
    waiting_amount = State()


class SurveyAdmin(StatesGroup):
    waiting_question = State()


class SurveyAnswer(StatesGroup):
    answering = State()


class TaxiFlow(StatesGroup):
    waiting_from = State()
    waiting_to = State()
    waiting_phone = State()


class TestAdmin(StatesGroup):
    waiting_question = State()
    waiting_options = State()
    waiting_correct = State()


class TestAnswer(StatesGroup):
    answering = State()


class PrayerCity(StatesGroup):
    waiting_city = State()


class WeatherCity(StatesGroup):
    waiting_city = State()


class FootballAdmin(StatesGroup):
    waiting_match = State()
    waiting_score = State()
    waiting_date = State()


class CarAdFlow(StatesGroup):
    waiting_brand = State()
    waiting_year = State()
    waiting_price = State()
    waiting_phone = State()


class AddAdmin(StatesGroup):
    waiting_id = State()


def is_admin(info: dict, uid: int) -> bool:
    return uid in info.get("admin_ids", [info.get("admin_id")])


def admins_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm_add")],
        [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="➖ Adminni o'chirish", callback_data="adm_del")],
    ])


def setup_admin_management(dp: Dispatcher, token: str):
    info = data["bots"][token]
    info.setdefault("admin_ids", [info.get("admin_id")])
    owner_id = info["admin_id"]

    @dp.message(Command("cancel"))
    async def cancel_cmd(message: Message, state: FSMContext):
        current = await state.get_state()
        if current is None:
            await message.answer("Bekor qilinadigan jarayon yo'q.")
            return
        await state.clear()
        await message.answer("❌ Jarayon bekor qilindi.")

    @dp.message(Command("admins"))
    @dp.message(F.text == "👤 Adminlar")
    async def admins_panel(message: Message):
        if not is_admin(info, message.from_user.id):
            return
        await message.answer("👤 Adminlar boshqaruvi:", reply_markup=admins_kb())

    @dp.callback_query(F.data == "adm_add")
    async def adm_add_cb(callback: CallbackQuery, state: FSMContext):
        if not is_admin(info, callback.from_user.id):
            return
        await callback.message.answer("Yangi admin Telegram ID'ini yuboring (/myid orqali bilib olish mumkin):")
        await state.set_state(AddAdmin.waiting_id)
        await callback.answer()

    @dp.message(AddAdmin.waiting_id)
    async def adm_add_process(message: Message, state: FSMContext):
        try:

new_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting.")
            return
        if new_id not in info["admin_ids"]:
            info["admin_ids"].append(new_id)
            save_data()
        await message.answer(f"✅ Admin qo'shildi: {new_id}")
        await state.clear()

    @dp.callback_query(F.data == "adm_list")
    async def adm_list_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        lines = []
        for aid in info["admin_ids"]:
            tag = " (asosiy)" if aid == owner_id else ""
            lines.append(f"• {aid}{tag}")
        await callback.message.answer("👤 Adminlar:\n\n" + "\n".join(lines))
        await callback.answer()

    @dp.callback_query(F.data == "adm_del")
    async def adm_del_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        removable = [aid for aid in info["admin_ids"] if aid != owner_id]
        if not removable:
            await callback.message.answer("O'chirish uchun qo'shimcha admin yo'q.")
            await callback.answer()
            return
        buttons = [[InlineKeyboardButton(text=str(aid), callback_data=f"admdel_{aid}")] for aid in removable]
        await callback.message.answer("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    @dp.callback_query(F.data.startswith("admdel_"))
    async def adm_delid_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        target_id = int(callback.data.split("_", 1)[1])
        if target_id in info["admin_ids"] and target_id != owner_id:
            info["admin_ids"].remove(target_id)
            save_data()
            await callback.message.answer(f"🗑 Admin o'chirildi: {target_id}")
        await callback.answer()


# ---------- Majburiy obuna (barcha botlar uchun umumiy) ----------
def channels_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch_add")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="ch_list")],
        [InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="ch_del")],
    ])


async def get_missing_channels(bot: Bot, channels: dict, user_id: int):
    missing = []
    for chat_id, info in channels.items():
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                missing.append(info)
        except Exception as e:
            logging.error(f"Obuna tekshirishda xato ({chat_id}): {e}")
            # Xatolik bo'lsa ham xavfsiz tomonni tanlaymiz — obuna talab qilinadi
            missing.append(info)
    return missing


def subscribe_kb(missing):
    buttons = [[InlineKeyboardButton(text=info["title"], url=f"https://t.me/{info['username'].lstrip('@')}")] for info in missing]
    buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def require_subscription(event, info: dict, admin_id: int) -> bool:
    uid = event.from_user.id
    if is_admin(info, uid):
        return True
    channels = info.get("channels", {})
    if not channels:
        return True
    missing = await get_missing_channels(event.bot, channels, uid)
    if missing:
        kb = subscribe_kb(missing)
        text = "Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:"
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)
        return False
    return True

async def check_active(event, info: dict, admin_id: int) -> bool:
    """True bo'lsa - bot ishlaydi. False bo'lsa - sinov tugagan / to'lov kerak."""
    if is_active(info):
        return True
    uid = event.from_user.id
    amount = next_payment_amount(info)
    is_renewal = bool(info.get("paid_until"))
    kb = None
    if is_admin(info, uid):
        kb = contact_admin_kb()
        if is_renewal:
            text = (
                f"⏳ <b>Oylik to'lov muddati tugadi.</b>\n\n"
                f"Davom ettirish uchun: <b>{amount:,} so'm</b> (oylik, narxning 20%).\n\n"
                "To'lovni amalga oshirish uchun administrator bilan bog'laning."
            )
        else:
            text = (
                f"⏳ <b>Bepul sinov muddati tugadi.</b>\n\n"
                f"Ushbu bot ({BOT_TYPES.get(info['type'])}) boshlang'ich narxi: <b>{amount:,} so'm</b>.\n"
                f"Keyingi oylardan boshlab: {int(get_price(info['type']) * MONTHLY_RATE):,} so'm/oy.\n\n"
                "To'lovni amalga oshirish uchun administrator bilan bog'laning."
            )
    else:
        text = "🚧 Bot vaqtincha ishlamayapti."
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)
    return False


def setup_subscription_handlers(dp: Dispatcher, token: str, admin_id: int):
    info = data["bots"][token]
    info.setdefault("channels", {})

    @dp.callback_query(F.data == "ch_add")
    async def ch_add_cb(callback: CallbackQuery, state: FSMContext):
        if not is_admin(info, callback.from_user.id):
            return
        await callback.message.answer(
            "Kanal usernameni yuboring (masalan: @mening_kanalim).\n"
            "⚠️ Bot o'sha kanalda ADMIN bo'lishi shart!"
        )
        await state.set_state(AddChannel.waiting_username)
        await callback.answer()

    @dp.message(AddChannel.waiting_username)
    async def ch_add_process(message: Message, state: FSMContext):
        if not is_admin(info, message.from_user.id):
            return
        username = message.text.strip()
        try:
            chat = await message.bot.get_chat(username)
            info["channels"][str(chat.id)] = {"username": username, "title": chat.title}
            save_data()
            await message.answer(f"✅ Qo'shildi: {chat.title}")

            # Bot o'sha kanalda ADMIN ekanligini darhol tekshiramiz
            try:
                bot_member = await message.bot.get_chat_member(chat_id=chat.id, user_id=message.bot.id)
                if bot_member.status not in ("administrator", "creator"):
                    await message.answer(
                        f"⚠️ <b>Diqqat!</b> Bot \"{chat.title}\" kanalida ADMIN emas.\n"
                        "Obuna tekshiruvi ishlashi uchun botni o'sha kanalga ADMIN qilib qo'ying!"
                    )
            except Exception:
                await message.answer(
                    f"⚠️ <b>Diqqat!</b> Bot \"{chat.title}\" kanalida ADMIN ekanligini tekshira olmadim.\n"
                    "Iltimos, botni o'sha kanalga ADMIN qilib qo'ying, aks holda obuna tekshiruvi ishlamaydi!"
                )
        except Exception as e:
            await message.answer(f"❌ Xatolik: kanal topilmadi.\n{e}")
        await state.clear()

    @dp.callback_query(F.data == "ch_list")
    async def ch_list_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        if not info["channels"]:
            await callback.message.answer("Hozircha majburiy kanallar yo'q.")
        else:
            text = "📋 Majburiy obuna kanallari:\n\n" + "\n".join(
                f"• {c['title']} ({c['username']})" for c in info["channels"].values()
            )
            await callback.message.answer(text)
        await callback.answer()

@dp.callback_query(F.data == "ch_del")
    async def ch_del_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        if not info["channels"]:
            await callback.message.answer("O'chirish uchun kanal yo'q.")
            await callback.answer()
            return
        buttons = [[InlineKeyboardButton(text=c["title"], callback_data=f"chdel_{cid}")] for cid, c in info["channels"].items()]
        await callback.message.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    @dp.callback_query(F.data.startswith("chdel_"))
    async def ch_delid_cb(callback: CallbackQuery):
        if not is_admin(info, callback.from_user.id):
            return
        cid = callback.data.split("_", 1)[1]
        removed = info["channels"].pop(cid, None)
        save_data()
        if removed:
            await callback.message.answer(f"🗑 O'chirildi: {removed['title']}")
        await callback.answer()

    @dp.callback_query(F.data == "check_sub")
    async def check_sub_cb(callback: CallbackQuery):
        missing = await get_missing_channels(callback.bot, info["channels"], callback.from_user.id)
        if missing:
            await callback.answer("Hali barcha kanallarga obuna bo'lmagansiz ❌", show_alert=True)
        else:
            await callback.message.edit_text("✅ Rahmat! Endi /start bosib davom eting.")
            await callback.answer()

    @dp.message(Command("channels"))
    @dp.message(F.text == "📡 Majburiy obuna")
    async def channels_panel(message: Message):
        if not is_admin(info, message.from_user.id):
            return
        await message.answer("📡 Majburiy obuna boshqaruvi:", reply_markup=channels_admin_kb())


# ---------- Bosh (creator) bot — XALQ UCHUN OMMAVIY ----------
def types_kb():
    buttons = [[InlineKeyboardButton(text=f"{name} — {get_price(key):,} so'm/oy", callback_data=f"type_{key}")] for key, name in BOT_TYPES.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def contact_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Admin bilan bog'lanish", url=admin_contact_url())]
    ])


@main_dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


@main_dp.message(Command("start"))
async def main_start(message: Message):
    price_lines = "\n".join(f"{BOT_TYPES[key]} — {get_price(key):,} so'm" for key in BOT_TYPES)
    text = (
        "🤖 <b>Bot yaratuvchi platformaga xush kelibsiz!</b>\n\n"
        "Bu yerda bir necha daqiqada o'zingizga kerakli botni yaratishingiz mumkin.\n\n"
        "💳 <b>Boshlang'ich narxlar:</b>\n"
        f"{price_lines}\n\n"
        f"📅 Keyingi oylardan boshlab — narxning atigi {int(MONTHLY_RATE*100)}%.\n"
        f"🎁 Har bir bot uchun {TRIAL_DAYS} kunlik BEPUL sinov muddati bor!\n\n"
        "💳 To'lov usuli: administrator bilan bog'lanish\n\n"
        "Bot yaratish: /newbot\n"
        "Botlaringiz: /mybots"
    )
    await message.answer(text, reply_markup=contact_admin_kb())


@main_dp.message(Command("newbot"))
async def newbot_start(message: Message, state: FSMContext):
    await message.answer(
        "Yangi bot tokenini yuboring.\n"
        "(@BotFather orqali /newbot bilan yaratib, tokenni shu yerga joylashtiring)"
    )
    await state.set_state(NewBotFlow.waiting_token)


@main_dp.message(NewBotFlow.waiting_token)
async def newbot_token(message: Message, state: FSMContext):
    token = message.text.strip()
    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer("❌ Token noto'g'ri. Qaytadan yuboring.")
        return

    await state.update_data(token=token, bot_name=me.first_name)
    await message.answer(f"✅ Bot topildi: <b>{me.first_name}</b>\n\nEndi bot turini tanlang:", reply_markup=types_kb())

@main_dp.callback_query(F.data.startswith("type_"))
async def newbot_type(callback: CallbackQuery, state: FSMContext):
    bot_type = callback.data.split("_", 1)[1]
    state_data = await state.get_data()
    token = state_data.get("token")
    bot_name = state_data.
