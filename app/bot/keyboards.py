from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать фото", callback_data="menu:generate")],
            [
                InlineKeyboardButton(text="Мой баланс", callback_data="menu:balance"),
                InlineKeyboardButton(text="Купить генерации", callback_data="menu:buy"),
            ],
            [
                InlineKeyboardButton(
                    text="Реферальная система", callback_data="menu:referral"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Поддержка", url="https://t.me/+nwcnXFSvb_Q4NmYy"
                ),
            ],
            [InlineKeyboardButton(text="Смотреть идеи", callback_data="menu:ideas")],
        ]
    )


def buy_packages_keyboard(packages: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{count} генераций", callback_data=f"buy:{count}")]
        for count in packages
    ]
    buttons.append([InlineKeyboardButton(text="Вернуться в меню", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pay_button(url: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=url)],
            [
                InlineKeyboardButton(
                    text="Проверить оплату",
                    callback_data=f"pay:check:{payment_id}",
                )
            ],
        ]
    )


def ideas_button(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в канал", url=channel_url)],
            [InlineKeyboardButton(text="Назад в меню", callback_data="menu:back")],
        ]
    )


def buy_now_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить генерации", callback_data="menu:buy")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="menu:back")],
        ]
    )


def result_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сгенерировать ещё", callback_data="menu:generate")],
            [InlineKeyboardButton(text="Вернуться в меню", callback_data="menu:back")],
        ]
    )


def balance_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить генерации", callback_data="menu:buy")],
            [InlineKeyboardButton(text="Вернуться в меню", callback_data="menu:back")],
        ]
    )


def referral_keyboard(share_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Поделиться",
                    switch_inline_query=share_text,
                )
            ],
            [InlineKeyboardButton(text="Назад в меню", callback_data="menu:back")],
        ]
    )
