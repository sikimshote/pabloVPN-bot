from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from database.db import async_session
from database.models import Plan, Panel, Service, User, Transaction
from panels import get_panel_adapter
from utils.keyboards import plans_kb
from utils.helpers import format_date
from utils.texts import t

router = Router()

@router.message(F.text == t("user_menu_buy"))
async def list_available_plans(message: Message):
    async with async_session() as session:
        res = await session.execute(
            select(Plan).where(Plan.is_active == True).order_by(Plan.order)
        )
        plans = res.scalars().all()

    if not plans:
        await message.answer("⚠️ در حال حاضر هیچ پلنی برای فروش فعال نیست.")
        return

    await message.answer("🛒 لطفا پلن مورد نظر خود را انتخاب کنید:", reply_markup=plans_kb(plans))

@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery):
    plan_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        p_res = await session.execute(select(Plan).where(Plan.id == plan_id))
        plan = p_res.scalar_one_or_none()
        u_res = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = u_res.scalar_one_or_none()

    if not plan or not user:
        await callback.answer("خطا در بارگذاری اطلاعات پلن!", show_alert=True)
        return

    if user.balance < plan.price:
        needed = plan.price - user.balance
        await callback.message.answer(
            t("insufficient_balance", balance=int(user.balance), needed=int(needed))
        )
        await callback.answer()
        return

    async with async_session() as session:
        panel_res = await session.execute(select(Panel).where(Panel.id == plan.panel_id))
        panel_obj = panel_res.scalar_one_or_none()

    if not panel_obj:
        await callback.answer("❌ پنل متصل به این پلن در دسترس نیست!", show_alert=True)
        return

    panel_adapter = get_panel_adapter(panel_obj)
    username = f"u{user.telegram_id}_{int(datetime.utcnow().timestamp())}"
    
    await callback.message.answer("⏳ در حال ایجاد کانفیگ اختصاصی شما...")
    success, sub_link, config_data = await panel_adapter.create_user(
        username=username,
        traffic_gb=plan.traffic_gb,
        duration_days=plan.duration_days
    )

    if not success:
        await callback.message.answer("❌ متاسفانه در ساخت سرویس مشکلی پیش آمد. لطفا با پشتیبانی تماس بگیرید.")
        await callback.answer()
        return

    expires = datetime.utcnow() + timedelta(days=plan.duration_days)

    async with async_session() as session:
        u = await session.get(User, user.id)
        u.balance -= plan.price

        srv = Service(
            user_id=u.id,
            plan_id=plan.id,
            panel_id=panel_obj.id,
            username=username,
            subscription_url=sub_link,
            config_data=config_data,
            traffic_gb=plan.traffic_gb,
            duration_days=plan.duration_days,
            expires_at=expires
        )
        session.add(srv)

        tx = Transaction(
            user_id=u.id,
            amount=plan.price,
            type="purchase",
            method="wallet",
            status="approved"
        )
        session.add(tx)
        await session.commit()

    text = t(
        "service_info",
        name=username,
        traffic=plan.traffic_gb,
        days=plan.duration_days,
        expires=format_date(expires),
        link=sub_link or config_data
    )
    await callback.message.answer(f"🎉 <b>خرید با موفقیت انجام شد!</b>\n\n{text}")
    await callback.answer()
