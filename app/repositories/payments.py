from __future__ import annotations

import aiosqlite


class PaymentRepo:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def create_payment(
        self,
        user_id: int,
        amount: int,
        generations: int,
        payment_id: str,
        status: str,
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO payments (user_id, amount, generations, payment_id, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, amount, generations, payment_id, status),
            )
            await db.commit()

    async def update_status(self, payment_id: str, status: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE payments SET status = ? WHERE payment_id = ?",
                (status, payment_id),
            )
            await db.commit()

    async def mark_succeeded(self, payment_id: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "UPDATE payments SET status = 'succeeded' WHERE payment_id = ? AND status != 'succeeded'",
                (payment_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_payment(self, payment_id: str) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM payments WHERE payment_id = ?",
                (payment_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_pending(self) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM payments WHERE status != 'succeeded'"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
