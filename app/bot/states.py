from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    waiting_photos = State()
    waiting_prompt = State()


class BuyStates(StatesGroup):
    waiting_quantity = State()
