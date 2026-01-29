from __future__ import annotations

from app.repositories.users import UserRepo


class ReferralService:
    def __init__(self, user_repo: UserRepo) -> None:
        self._user_repo = user_repo

    async def grant_referral_bonus(self, new_user_id: int, referrer_id: int) -> bool:
        already = await self._user_repo.is_referral_bonus_granted(new_user_id)
        if already:
            return False
        await self._user_repo.add_generations(referrer_id, 2)
        await self._user_repo.set_referral_bonus_granted(new_user_id)
        return True
