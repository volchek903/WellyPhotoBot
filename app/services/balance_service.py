from __future__ import annotations

from app.repositories.users import UserRepo


class BalanceService:
    def __init__(self, user_repo: UserRepo) -> None:
        self._user_repo = user_repo

    async def get_balance(self, user_id: int) -> int:
        return await self._user_repo.get_balance(user_id)

    async def add_generations(self, user_id: int, amount: int) -> None:
        await self._user_repo.add_generations(user_id, amount)

    async def consume_generation(self, user_id: int) -> bool:
        return await self._user_repo.consume_generation(user_id)
