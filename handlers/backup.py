import os
import shutil
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext

from config import config
from utils.decorators import owner_only
from utils.keyboards import owner_main_kb, back_kb
from utils.states import OwnerStates
from utils.texts import t

router = Router()

async def create_backup_file() -> str:
    if not os.path.exists(config.BACKUP_DIR):
        os.makedirs(config.BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"pablovpn_backup_{timestamp}.db"
    backup_filepath = os.path.join(config.BACKUP_DIR, backup_filename)
    if os.path.exists(config.DATABASE_PATH):
        shutil.copyfile(config.DATABASE_PATH, backup_filepath)
        return backup_filepath
    return ""

@router.message(F.text == "💾 بکاپ و ریستور")
@owner_only
async def backup_menu(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "💾 <b>مدیریت بکاپ و مهاجرت دیتابیس</b>\n\n"
        "📥 برای دریافت بکاپ روی /get_backup کلیک کنید.\n"
        "📤 برای ریستور کردن اطلاعات دیتابیس قبلی روی /restore کلیک کنید."
    )
    await message.answer(text)

@router.message(F.text == "/get_backup")
@owner_only
async def send_backup(message: Message):
    filepath = await create_backup_file()
    if filepath and os.path.exists(filepath):
        doc = FSInputFile(filepath)
        await message.answer_document(doc, caption="💾 فایل کامل بکاپ پایگاه داده PabloVPN")
    else:
        await message.answer("❌ فایلی برای بکاپ یافت نشد!")

@router.message(F.text == "/restore")
@owner_only
async def start_restore(message: Message, state: FSMContext):
    await state.set_state(OwnerStates.waiting_restore_file)
    await message.answer("📤 لطفا فایل دیتابیس با پسوند <code>.db</code> را ارسال کنید:", reply_markup=back_kb())

@router.message(OwnerStates.waiting_restore_file, F.document)
@owner_only
async def apply_restore(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.endswith(".db"):
        await message.answer("❌ فقط ارسال فایل با پسوند .db مجاز است.")
        return

    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, config.DATABASE_PATH)
    await state.clear()
    await message.answer("✅ دیتابیس با موفقیت بازگردانی (Restore) شد!", reply_markup=owner_main_kb())
