from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    balance_actions_keyboard,
    buy_now_button,
    buy_packages_keyboard,
    ideas_button,
    main_menu,
    pay_button,
    referral_keyboard,
)
from app.bot.states import BuyStates, GenerationStates
from app.config import Settings
from app.repositories.payments import PaymentRepo
from app.repositories.users import UserRepo
from app.services.balance_service import BalanceService
from app.services.generation_service import GenerationService
from app.services.referral_service import ReferralService
from app.services.yookassa_service import YooKassaService


@dataclass(slots=True)
class AppContext:
    settings: Settings
    user_repo: UserRepo
    payment_repo: PaymentRepo
    balance_service: BalanceService
    referral_service: ReferralService
    generation_service: GenerationService
    yookassa_service: YooKassaService


def build_router() -> Router:
    router = Router()

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        ctx: AppContext = message.bot.ctx
        user_id = message.from_user.id
        args = (message.text or "").split()
        referrer_id = _parse_referrer(args[1] if len(args) > 1 else "")

        user = await ctx.user_repo.get_user(user_id)
        if user is None:
            await ctx.user_repo.create_user(user_id, referrer_id, bonus_generations=1)
            if referrer_id and referrer_id != user_id:
                await _try_grant_referral_bonus(message.bot, ctx, user_id, referrer_id)
        await message.answer(
            "✨ Добро пожаловать в Welly\n"
            "Здесь ты можешь создать стильные AI-фото — как для соцсетей, так и для себя\n"
            "📸 Просто загрузи фото\n"
            "Я сделаю из него новый образ\n"
            "🎁 Первое фото — бесплатно",
            reply_markup=main_menu(),
        )

    @router.message(Command("balance"))
    async def balance(message: Message) -> None:
        ctx: AppContext = message.bot.ctx
        user_id = message.from_user.id
        balance_value = await ctx.balance_service.get_balance(user_id)
        await message.answer(
            f"💰 Ваш баланс:\n🔹 Доступно генераций: {balance_value}",
            reply_markup=main_menu(),
        )

    @router.message(Command("generate"))
    async def generate(message: Message, state: FSMContext) -> None:
        await state.set_state(GenerationStates.waiting_photos)
        await state.update_data(photos=[])
        await message.answer(
            "📷 Пришли 1 или 2 фото, а затем отправь текстовый промпт.",
            reply_markup=main_menu(),
        )

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Окей, отменил ✋", reply_markup=main_menu())

    @router.message(GenerationStates.waiting_photos, F.photo)
    async def on_photo(message: Message, state: FSMContext) -> None:
        ctx: AppContext = message.bot.ctx
        data = await state.get_data()
        photos = list(data.get("photos", []))
        photo = message.photo[-1]
        photos.append(photo.file_id)
        if len(photos) > 2:
            await state.clear()
            await message.answer("Можно загрузить только 1 или 2 фотографии. Начни заново 🙌")
            return

        await state.update_data(photos=photos)
        caption = (message.caption or "").strip()
        if caption:
            await state.clear()
            await _start_generation(message, ctx, caption, photos)
            return

        if len(photos) == 1:
            await state.set_state(GenerationStates.waiting_prompt)
            await message.answer(
                "Отлично. Теперь опиши желаемый стиль настроение или образ ✍️"
            )
        else:
            await state.set_state(GenerationStates.waiting_prompt)
            await message.answer(
                "Отлично. Теперь опиши желаемый стиль настроение или образ ✍️"
            )

    @router.message(GenerationStates.waiting_photos, F.text)
    async def on_prompt_without_photo(message: Message) -> None:
        await message.answer("Сначала пришли 1 или 2 фотографии 📸")

    @router.message(GenerationStates.waiting_prompt, F.text)
    async def on_prompt(message: Message, state: FSMContext) -> None:
        ctx: AppContext = message.bot.ctx
        data = await state.get_data()
        photos = list(data.get("photos", []))
        prompt = (message.text or "").strip()
        await state.clear()
        await _start_generation(message, ctx, prompt, photos)

    @router.message(GenerationStates.waiting_prompt, F.photo)
    async def on_extra_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        photos = list(data.get("photos", []))
        if len(photos) >= 2:
            await message.answer("Уже получил 2 фото. Теперь промпт ✍️")
            return
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)
        await message.answer("Фото добавлено ✅ Теперь промпт ✍️")

    @router.message(Command("buy"))
    async def buy(message: Message, state: FSMContext) -> None:
        packages = [5, 10, 100]
        await message.answer(
            "Купить генерации\n\n"
            "Выбери свой тариф и начни создавать уникальные фото прямо сейчас!\n"
            "Каждая генерация - это одно готовое фото в выбранном стиле.\n"
            "Тарифы 💰\n"
            "5 фото - 99 руб\n"
            "10 фото - 169 руб\n"
            "100 фото - 799 руб\n\n"
            "✨ Доступ к образам\n"
            "Оплата — разовая Используй генерации, когда удобно.",
            reply_markup=buy_packages_keyboard(packages),
        )
        await state.set_state(BuyStates.waiting_quantity)

    @router.callback_query(F.data == "menu:balance")
    async def menu_balance(callback: CallbackQuery) -> None:
        await callback.answer()
        ctx: AppContext = callback.bot.ctx
        user_id = callback.from_user.id
        balance_value = await ctx.balance_service.get_balance(user_id)
        await _edit_message(
            callback.message,
            "💳 Твой баланс\n"
            f"Доступно генераций: {balance_value}\n"
            "Ты можешь использовать их в любое время.",
            reply_markup=balance_actions_keyboard(),
        )

    @router.callback_query(F.data == "menu:generate")
    async def menu_generate(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.set_state(GenerationStates.waiting_photos)
        await state.update_data(photos=[])
        await _edit_message(
            callback.message,
            "📸 Пришли 1–2 фотографии, затем напиши короткое описание, каким ты хочешь видеть результат."
        )

    @router.callback_query(F.data == "menu:buy")
    async def menu_buy(callback: CallbackQuery, state: FSMContext) -> None:
        logging.info("menu:buy callback from user %s", callback.from_user.id)
        await callback.answer()
        packages = [5, 10, 100]
        await _edit_message(
            callback.message,
            "Купить генерации\n\n"
            "Выбери свой тариф и начни создавать уникальные фото прямо сейчас!\n"
            "Каждая генерация - это одно готовое фото в выбранном стиле.\n"
            "Тарифы 💰\n"
            "5 фото - 99 руб\n"
            "10 фото - 169 руб\n"
            "100 фото - 799 руб\n\n"
            "✨ Доступ к образам\n"
            "Оплата — разовая Используй генерации, когда удобно.",
            reply_markup=buy_packages_keyboard(packages),
        )
        await state.set_state(BuyStates.waiting_quantity)

    @router.callback_query(F.data == "menu:ideas")
    async def menu_ideas(callback: CallbackQuery) -> None:
        await callback.answer()
        ctx: AppContext = callback.bot.ctx
        if not ctx.settings.ideas_channel_url:
            await _edit_message(
                callback.message,
                "Ссылка на канал ещё не настроена 😕",
                reply_markup=main_menu(),
            )
            return
        await _edit_message(
            callback.message,
            "💡 Идеи и вдохновение — в нашем Telegram‑канале.",
            reply_markup=ideas_button(ctx.settings.ideas_channel_url),
        )

    @router.callback_query(F.data == "menu:referral")
    async def menu_referral(callback: CallbackQuery) -> None:
        await callback.answer()
        bot_username = (await callback.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{callback.from_user.id}"
        invited_count = await callback.bot.ctx.user_repo.count_referrals(callback.from_user.id)
        earned_generations = invited_count * 2
        share_text = (
            "Попробуй бота для генерации фото 🤖\n"
            "По моей ссылке ты получишь бонус, а мне начислят +2 генерации:\n"
            f"{ref_link}"
        )
        await _edit_message(
            callback.message,
            "Реферальная система\n\n"
            "🎁 Хочешь ещё генераций бесплатно?\n"
            "Ты можешь получать генерации, просто делясь ботом\n"
            "🔹 1 друг = +2 генерации 🔹 Без ограничений\n"
            "твоя личная ссылка:\n"
            f"{ref_link}\n\n"
            "📈 Твой результат:\n"
            f"👥 Приглашено: {invited_count} человека 🎁 Получено генераций: {earned_generations}",
            reply_markup=referral_keyboard(share_text),
        )

    @router.callback_query(F.data == "menu:back")
    async def menu_back(callback: CallbackQuery) -> None:
        await callback.answer()
        await _edit_message(
            callback.message,
            "Выбирай действие ниже 👇",
            reply_markup=main_menu(),
        )

    @router.message(BuyStates.waiting_quantity, F.text)
    async def buy_custom(message: Message, state: FSMContext) -> None:
        count_text = (message.text or "").strip()
        if not count_text.isdigit():
            await message.answer("Введите число, например 5 🙂")
            return
        count = int(count_text)
        price = _get_package_price(count, message.bot.ctx.settings)
        if price is None:
            await message.answer("Доступны пакеты: 5, 10 или 100 генераций ✨")
            return
        await state.clear()
        await _create_payment(message, message.from_user.id, count)

    @router.callback_query(F.data.startswith("buy:"))
    async def buy_package(callback: CallbackQuery, state: FSMContext) -> None:
        logging.info("buy package callback: %s from user %s", callback.data, callback.from_user.id)
        await state.clear()
        count = int(callback.data.split(":")[1])
        await callback.answer()
        await _create_payment(callback.message, callback.from_user.id, count)

    @router.callback_query(F.data.startswith("pay:check:"))
    async def pay_check(callback: CallbackQuery) -> None:
        payment_id = callback.data.split("pay:check:", 1)[1]
        await callback.answer("Проверяю оплату…")
        await _check_payment_status(
            callback.message,
            payment_id,
            callback.from_user.id,
        )

    @router.callback_query()
    async def unknown_callback(callback: CallbackQuery) -> None:
        await callback.answer("Кнопка не распознана. Попробуйте ещё раз.", show_alert=False)

    return router


def _parse_referrer(arg: str) -> int | None:
    if arg.startswith("ref_"):
        raw = arg.replace("ref_", "", 1)
        if raw.isdigit():
            return int(raw)
    return None


async def _try_grant_referral_bonus(
    bot: Bot, ctx: AppContext, new_user_id: int, referrer_id: int
) -> None:
    granted = await ctx.referral_service.grant_referral_bonus(new_user_id, referrer_id)
    if granted:
        await bot.send_message(
            referrer_id,
            "🎉 У вас новый реферал!\nВам начислено +2 генерации фото.",
        )


async def _start_generation(
    message: Message,
    ctx: AppContext,
    prompt: str,
    photos: list[str],
) -> None:
    prompt = prompt.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым ✍️")
        return
    if len(photos) not in {1, 2}:
        await message.answer("Нужно отправить 1 или 2 фотографии 📸")
        return
    balance_value = await ctx.balance_service.get_balance(message.from_user.id)
    if balance_value <= 0:
        await message.answer(
            "Генерации закончились ✨\n"
            "Ты можешь купить новый пакет и продолжить.",
            reply_markup=buy_now_button(),
        )
        return
    status_message = await message.answer(
        "⏳ Создаю образ…\n"
        "Это может занять до 1 минуты.\n"
        "Я стараюсь получить максимально качественный результат ✨"
    )
    asyncio.create_task(
        ctx.generation_service.generate(
            bot=message.bot,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            prompt=prompt,
            photo_file_ids=photos,
            status_message_id=status_message.message_id,
        )
    )


async def _create_payment(message: Message, user_id: int, count: int) -> None:
    ctx: AppContext = message.bot.ctx
    price = _get_package_price(count, ctx.settings)
    if price is None:
        await message.answer("Доступны пакеты: 5, 10 или 100 генераций ✨")
        return
    try:
        payment = await ctx.yookassa_service.create_payment(
            amount=price,
            currency="RUB",
            description=f"Покупка {count} генераций",
            user_id=user_id,
            generations=count,
        )
    except Exception:
        await message.answer("Не удалось создать оплату. Попробуйте позже 😔")
        return
    payment_id = payment.get("id")
    status = payment.get("status", "pending")
    confirmation = payment.get("confirmation", {})
    confirmation_url = confirmation.get("confirmation_url")
    if not payment_id or not confirmation_url:
        logging.warning(
            "YooKassa response missing id/confirmation_url: %s",
            {k: payment.get(k) for k in ("id", "status", "confirmation")},
        )
        await message.answer("Не удалось создать оплату. Попробуйте позже 😔")
        return
    await ctx.payment_repo.create_payment(
        user_id=user_id,
        amount=price,
        generations=count,
        payment_id=payment_id,
        status=status,
    )
    await message.answer(
        f"💳 К оплате: {price} ₽ за {count} генераций.",
        reply_markup=pay_button(confirmation_url, payment_id),
    )


def _get_package_price(count: int, settings: Settings) -> int | None:
    prices = {
        5: 99,
        10: 169,
        100: 799,
    }
    return prices.get(count)


async def _check_payment_status(message: Message, payment_id: str, user_id: int) -> None:
    ctx: AppContext = message.bot.ctx
    payment_record = await ctx.payment_repo.get_payment(payment_id)
    if not payment_record:
        await message.answer("Платёж не найден. Попробуйте снова через «Купить генерации».")
        return
    if int(payment_record["user_id"]) != user_id:
        await message.answer("Этот платёж не принадлежит вам.")
        return
    if payment_record.get("status") == "succeeded":
        await message.answer("✅ Оплата уже подтверждена. Проверьте баланс.")
        return
    try:
        payment = await ctx.yookassa_service.fetch_payment(payment_id)
    except Exception:
        await message.answer("Не удалось проверить оплату. Попробуйте позже.")
        return
    status = payment.get("status") or payment_record.get("status") or "pending"
    if status == "succeeded":
        updated = await ctx.payment_repo.mark_succeeded(payment_id)
        if updated:
            generations = int(payment_record["generations"])
            await ctx.balance_service.add_generations(user_id, generations)
            await message.answer(
                "Оплата прошла успешно\n\n"
                "Генерации уже доступны.\n"
                "Можем продолжать создавать образы."
            )
        else:
            await message.answer("✅ Оплата уже подтверждена. Проверьте баланс.")
        return
    if status in {"canceled", "cancelled"}:
        await ctx.payment_repo.update_status(payment_id, status)
        await message.answer("❌ Платёж отменён.")
        return
    if status and status != payment_record.get("status"):
        await ctx.payment_repo.update_status(payment_id, status)
    await message.answer("⏳ Оплата пока не подтверждена. Попробуйте позже.")


async def _edit_message(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=reply_markup)
