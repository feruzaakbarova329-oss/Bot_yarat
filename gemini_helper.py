import re

import google.generativeai as genai

from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """\
Sen aiogram 3 (Python) uchun Telegram bot plugin generatori sifatida ishlaysan.
Senga foydalanuvchi tilida funksiya tavsifi beriladi. Shu funksiyani bajaradigan
bitta Python fayl kodini yozishing kerak.

QOIDALAR:
1. Kodda albatta quyidagi importlar bo'lishi shart (kerak bo'lganlarini ishlat):
   from aiogram import Router, F
   from aiogram.types import Message
   from aiogram.filters import Command
2. Faylda albatta `router = Router()` deb nomlangan obyekt bo'lishi shart.
3. Barcha handlerlar shu router ustida ro'yxatdan o'tkazilishi kerak,
   masalan: @router.message(Command("vaqt"))
4. Faqat va faqat Python kodini qaytar. Hech qanday izoh matni, hech qanday
   markdown ``` belgilari bo'lmasin.
5. Fayl nomi uchun ingliz tilida, lotin harflarida, pastki chiziq bilan qisqa
   slug tanla va uni BIRINCHI qatorda quyidagicha izoh sifatida yoz:
   # PLUGIN_NAME: shu_nom
6. Xavfli operatsiyalardan qat'iy saqlan: fayllarni/papkalarni o'chirish,
   os.system yoki subprocess orqali ixtiyoriy tizim buyruqlarini bajarish,
   tashqi manzillarga hujum, boshqa foydalanuvchilar ma'lumotini o'g'irlash
   kabi narsalarni hech qachon yozma.
7. Kod xatosiz va darhol ishga tushadigan bo'lishi kerak.
"""


def _extract_plugin_name(code: str, fallback: str) -> str:
    match = re.search(r"#\s*PLUGIN_NAME:\s*([a-zA-Z0-9_]+)", code)
    if match:
        return match.group(1)
    return fallback


async def generate_plugin_code(description: str):
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(description)
    raw = response.text.strip()

    # Gemini ba'zan ```python bilan o'rab yuborishi mumkin - tozalaymiz
    raw = re.sub(r"^```python\n?", "", raw)
    raw = re.sub(r"^```\n?", "", raw)
    raw = re.sub(r"```$", "", raw).strip()

    fallback_name = "feature_" + str(abs(hash(description)))[:6]
    plugin_name = _extract_plugin_name(raw, fallback=fallback_name)

    # PLUGIN_NAME qatorini kod ichidan olib tashlaymiz (u faqat nom uchun edi)
    raw = re.sub(r"#\s*PLUGIN_NAME:.*\n", "", raw, count=1)

    return plugin_name, raw
