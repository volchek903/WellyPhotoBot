from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramForbiddenError

from app.bot.handlers import AppContext, build_router
from app.config import load_settings
from app.db import init_db
from app.repositories.payments import PaymentRepo
from app.repositories.users import UserRepo
from app.services.balance_service import BalanceService
from app.services.generation_service import GenerationService
from app.services.kie_client import KieClient
from app.services.referral_service import ReferralService
from app.services.yookassa_service import YooKassaService


async def poll_payments(ctx: AppContext, bot: Bot) -> None:
    interval = ctx.settings.yookassa_poll_interval_seconds
    while True:
        pending = await ctx.payment_repo.list_pending()
        for payment_record in pending:
            payment_id = payment_record["payment_id"]
            payment = await ctx.yookassa_service.fetch_payment(payment_id)
            status = payment.get("status")
            if status == "succeeded":
                updated = await ctx.payment_repo.mark_succeeded(payment_id)
                if updated:
                    user_id = int(payment_record["user_id"])
                    generations = int(payment_record["generations"])
                    await ctx.balance_service.add_generations(user_id, generations)
                    try:
                        await bot.send_message(
                            user_id,
                            "Оплата прошла успешно\n\n"
                            "Генерации уже доступны.\n"
                            "Можем продолжать создавать образы.",
                        )
                    except TelegramForbiddenError as exc:
                        logging.warning("payment notify forbidden for user=%s: %s", user_id, exc)
                continue
            if status and status != payment_record.get("status"):
                await ctx.payment_repo.update_status(payment_id, status)
        await asyncio.sleep(interval)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    await init_db(settings.database_path)

    user_repo = UserRepo(settings.database_path)
    payment_repo = PaymentRepo(settings.database_path)
    balance_service = BalanceService(user_repo)
    referral_service = ReferralService(user_repo)
    kie_client = KieClient(
        api_key=settings.kie_api_key,
        api_base_url=settings.kie_api_base_url,
        file_base_url=settings.kie_file_base_url,
        model=settings.kie_model,
        resolution=settings.kie_resolution,
        aspect_ratio=settings.kie_aspect_ratio,
        output_format=settings.kie_output_format,
        poll_interval_seconds=settings.kie_poll_interval_seconds,
        max_poll_seconds=settings.kie_max_poll_seconds,
    )
    generation_service = GenerationService(
        kie_client,
        user_repo,
        telegram_photo_max_bytes=settings.telegram_photo_max_bytes,
    )
    yookassa_service = YooKassaService(
        shop_id=settings.yookassa_shop_id,
        secret_key=settings.yookassa_secret_key,
        return_url=settings.yookassa_return_url,
    )

    ctx = AppContext(
        settings=settings,
        user_repo=user_repo,
        payment_repo=payment_repo,
        balance_service=balance_service,
        referral_service=referral_service,
        generation_service=generation_service,
        yookassa_service=yookassa_service,
    )

    bot = Bot(settings.bot_token)
    bot.ctx = ctx

    dp = Dispatcher()
    dp.include_router(build_router())

    asyncio.create_task(poll_payments(ctx, bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
