import asyncio
import importlib
import logging
import sys
import traceback
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_ID
from gemini_helper import generate_plugin_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent / "plugins"
PLUGINS_DIR.mkdir(exist_ok=True)
(PLUGINS_DIR / "__init__.py").touch(exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

loaded_plugins = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def load_all_plugins():
    """Bot ishga tushganda mavjud barcha pluginlarni yuklaydi."""
    for file in sorted(PLUGINS_DIR.glob("*.py")):
        if file.stem == "__init__":
            continue
        ok, error = await load_plugin(file.stem)
        if not ok:
            logger.warning(f"Plugin yuklanmadi ({file.stem}): {error}")


async def load_plugin(name: str):
    try:
        module_path = f"plugins.{name}"
        if module_path in sys.modules:
            module = importlib.reload(sys.modules[module_path])
        else:
            module = importlib.import_module(module_path)

        if hasattr(module, "router") and isinstance(module.router, Router):
            dp.include_router(module.router)
            loaded_plugins[name] = module
            logger.info(f"Plugin yuklandi: {name}")
            return True, None
        return False, "Plugin ichida 'router' obyekti topilmadi"
    except Exception as e:
        return False, f"{e}\n{traceback.format_exc()}"


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Salom! Men o'z-o'zimga yangi funksiyalar qo'sha oladigan botman.\n\n"
        "Admin menga oddiy matn bilan yangi funksiya haqida yozsa, "
        "men Gemini yordamida kod yozib, darhol o'zimga qo'shib olaman.\n\n"
        "/plugins — qo'shilgan funksiyalar ro'yxati\n"
        "/newfeature <tavsif> — yangi funksiya so'rash"
    )


@dp.message(Command("plugins"))
async def cmd_plugins(message: Message):
    if not loaded_plugins:
        await message.answer("Hozircha qo'shilgan qo'shimcha funksiyalar yo'q.")
        return
    text = "Qo'shilgan funksiyalar:\n" + "\n".join(f"• {name}" for name in loaded_plugins)
    await message.answer(text)


@dp.message(Command("newfeature"))
async def cmd_newfeature(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Bu buyruq faqat admin uchun.")
        return

    description = message.text.replace("/newfeature", "", 1).strip()
    if not description:
        await message.answer(
            "Funksiyani tavsiflab yozing, masalan:\n"
            "/newfeature Foydalanuvchi /vaqt deb yozsa, hozirgi vaqtni qaytaradigan handler qo'sh"
        )
        return
    await handle_feature_request(message, description)


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_admin_text(message: Message):
    """Admin oddiy matn yozsa, buni ham yangi funksiya so'rovi deb qabul qilamiz."""
    if not is_admin(message.from_user.id):
        return
    await handle_feature_request(message, message.text)


async def handle_feature_request(message: Message, description: str):
    status_msg = await message.answer("⏳ Gemini kod yozmoqda...")

    try:
        plugin_name, code = await generate_plugin_code(description)
    except Exception as e:
        await status_msg.edit_text(f"❌ Gemini xatosi: {e}")
        return

    plugin_path = PLUGINS_DIR / f"{plugin_name}.py"
    plugin_path.write_text(code, encoding="utf-8")

    ok, error = await load_plugin(plugin_name)

    if ok:
        preview = code if len(code) < 1500 else code[:1500] + "\n..."
        await status_msg.edit_text(
            f"✅ Yangi funksiya qo'shildi: {plugin_name}\n\n"
            f"Kod:\n<pre>{preview}</pre>",
            parse_mode="HTML",
        )
    else:
        plugin_path.unlink(missing_ok=True)
        await status_msg.edit_text(
            f"❌ Kodda xatolik bor, funksiya qo'shilmadi:\n{error[:1500]}"
        )


async def main():
    await load_all_plugins()
    logger.info("Bot ishga tushdi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
