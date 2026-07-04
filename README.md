# O'z-o'zini rivojlantiruvchi Telegram bot

Admin botga oddiy matn bilan funksiya tavsiflab yozadi → Gemini shu funksiya
uchun kod yozadi → bot kodni `plugins/` papkasiga saqlab, darhol (restartsiz)
o'ziga ulab oladi.

## Fayllar
- `bot.py` — asosiy bot, buyruqlar va plugin yuklovchi
- `gemini_helper.py` — Gemini'ga so'rov yuborib kod olish
- `config.py` — muhit o'zgaruvchilaridan sozlamalarni o'qiydi
- `plugins/` — Gemini yozgan har bir funksiya shu yerda alohida faylda saqlanadi

## Lokal ishga tushirish
```bash
pip install -r requirements.txt
cp .env.example .env   # va qiymatlarni to'ldiring
export $(cat .env | xargs)   # yoki muhit o'zgaruvchilarini boshqacha yuklang
python bot.py
