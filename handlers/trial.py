from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select

from database.db import async_session
from database.models import Panel, Service, User
from panels import get_panel_adapter
from utils.helpers import format_date
from utils.texts import get_setting, t

router = Router()

@router.message(F.text == t("user_menu_test"))
async def give_trial(message: Message):
    enabled = await get_setting("free_trial_enabled", "0")
    if enabled != "1":
        await message.answer(t("free_trial_disabled"))
        return

    async with async_session() as session:
        u_res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = u_res.scalar_one_or_none()
        if not user:
            return

        if user.free_trial_used:
            await message.answer(t("free_trial_used"))
            return

        p_res = await session.execute(select(Panel).where(Panel.is_active == True).limit(1))
        panel = p_res.scalar_one_or_none()

    if not panel:
        await message.answer("⚠️ در حال حاضر امکان ارائه سرویس تست وجود ندارد.")
        return

    days = int(await get_setting("free_trial_days", "1"))
    gb = float(await get_setting("free_trial_gb", "1"))

    adapter = get_panel_adapter(panel)
    username = f"trial_{message.from_user.id}_{int(datetime.utcnow().timestamp())}"
    await message.answer("⏳ در حال ساخت سرویس تست رایگان...")

    success, sub_link, config_data = await adapter.create_user(username=username, traffic_gb=gb, duration_days=days)

    if not success:
        await message.answer("❌ خطا در ساخت سرویس تست. لطفا با پشتیبانی تماس بگیرید.")
        return

    expires = datetime.utcnow() + timedelta(days=days)
    async with async_session() as session:
        u = await session.get(User, user.id)
        u.free_trial_used = True
        srv = Service(
            user_id=u.id,
            panel_id=panel.id,
            username=username,
            subscription_url=sub_link,
            config_data=config_data,
            traffic_gb=gb,
            duration_days=days,
            expires_at=expires,
            is_trial=True
        )
        session.add(srv)
        await session.commit()

    text = (
        f"🎁 <b>{t('free_trial_success')}</b>\n\n"
        f"📊 حجم: {gb} GB\n"
        f"⏱️ مدت: {days} روز\n"
        f"📅 انقضا: {format_date(expires)}\n\n"
        f"🔗 لینک اتصال:\n<code>{sub_link or config_data}</code>"
    )
    await message.answer(text)
