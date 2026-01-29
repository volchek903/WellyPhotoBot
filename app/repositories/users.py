from __future__ import annotations

import aiosqlite


class UserRepo:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def get_user(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(
        self, user_id: int, referred_by: int | None, bonus_generations: int
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, bonus_generations, total_generations_used, referred_by)
                VALUES (?, ?, 0, ?)
                """,
                (user_id, bonus_generations, referred_by),
            )
            await db.commit()

    async def add_generations(self, user_id: int, amount: int) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET bonus_generations = bonus_generations + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()

    async def consume_generation(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                UPDATE users
                SET bonus_generations = bonus_generations - 1,
                    total_generations_used = total_generations_used + 1
                WHERE user_id = ? AND bonus_generations > 0
                """,
                (user_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_balance(self, user_id: int) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT bonus_generations FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def set_referral_bonus_granted(self, user_id: int) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET referral_bonus_granted = 1 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

    async def is_referral_bonus_granted(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT referral_bonus_granted FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

    async def count_referrals(self, referrer_id: int) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM users WHERE referred_by = ?",
                (referrer_id,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0
