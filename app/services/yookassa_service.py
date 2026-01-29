from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from yookassa import Configuration, Payment


def _payment_to_dict(payment: Any) -> dict[str, Any]:
    if isinstance(payment, dict):
        return payment
    try:
        return dict(payment)
    except Exception:
        pass
    data: dict[str, Any] = {}
    for key in ("id", "status", "metadata", "confirmation", "amount", "description"):
        value = getattr(payment, key, None)
        if value is not None:
            data[key] = value
    return data


class YooKassaService:
    def __init__(self, shop_id: str, secret_key: str, return_url: str) -> None:
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key
        self._return_url = return_url

    async def create_payment(
        self,
        amount: int,
        currency: str,
        description: str,
        user_id: int,
        generations: int,
    ) -> dict[str, Any]:
        idempotence_key = str(uuid.uuid4())
        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "confirmation": {"type": "redirect", "return_url": self._return_url},
            "capture": True,
            "description": description,
            "metadata": {"user_id": str(user_id), "generations": str(generations)},
        }

        def _create() -> dict[str, Any]:
            try:
                payment = Payment.create(payload, idempotence_key)
                return _payment_to_dict(payment)
            except Exception:
                logging.exception("YooKassa create_payment failed")
                raise

        return await asyncio.to_thread(_create)

    async def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        def _fetch() -> dict[str, Any]:
            try:
                payment = Payment.find_one(payment_id)
                return _payment_to_dict(payment)
            except Exception:
                logging.exception("YooKassa fetch_payment failed: %s", payment_id)
                raise

        return await asyncio.to_thread(_fetch)
