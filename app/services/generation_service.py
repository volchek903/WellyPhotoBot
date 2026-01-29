from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Sequence

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

from app.bot.keyboards import result_actions_keyboard
from app.repositories.users import UserRepo
from app.services.kie_client import KieClient


class GenerationService:
    def __init__(
        self,
        kie_client: KieClient,
        user_repo: UserRepo,
        telegram_photo_max_bytes: int | None = None,
    ) -> None:
        self._kie_client = kie_client
        self._user_repo = user_repo
        self._locks: set[int] = set()
        self._telegram_photo_max_bytes = telegram_photo_max_bytes

    def is_busy(self, user_id: int) -> bool:
        return user_id in self._locks

    async def generate(
        self,
        bot: Bot,
        user_id: int,
        chat_id: int,
        prompt: str,
        photo_file_ids: Sequence[str],
        status_message_id: int | None = None,
    ) -> None:
        if user_id in self._locks:
            await bot.send_message(chat_id, "⏳ Генерация уже запущена. Дождитесь результата.")
            return
        self._locks.add(user_id)
        try:
            logging.info("generation start user=%s photos=%s", user_id, len(photo_file_ids))
            async with aiohttp.ClientSession() as session:
                image_urls = []
                for file_id in photo_file_ids:
                    logging.info("downloading telegram file_id=%s", file_id)
                    file = await bot.get_file(file_id)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        temp_path = tmp.name
                    await bot.download_file(file.file_path, temp_path)
                    try:
                        upload_path = f"telegram/{user_id}"
                        logging.info("uploading to kie: %s", temp_path)
                        url = await self._kie_client.upload_file(session, temp_path, upload_path)
                        image_urls.append(url)
                        logging.info("uploaded url=%s", url)
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                logging.info("creating kie task")
                task_id = await self._kie_client.create_task(session, prompt, image_urls)
                logging.info("kie task_id=%s", task_id)
                result = await self._kie_client.poll_task(session, task_id)
                logging.info("kie result status=%s urls=%s", result.status, result.image_urls)
                if not result.image_urls:
                    logging.warning("generation failed status=%s", result.status)
                    await self._try_delete_message(bot, chat_id, status_message_id)
                    await bot.send_message(
                        chat_id,
                        "К сожалению, это изображение не подходит для обработки. "
                        "Попробуй загрузить другое фото",
                    )
                    return

                image_url = result.image_urls[0]
                await self._send_generated_image(bot, chat_id, session, image_url)
                await self._try_delete_message(bot, chat_id, status_message_id)
                consumed = await self._user_repo.consume_generation(user_id)
                if not consumed:
                    await bot.send_message(
                        chat_id,
                        "⚠️ Генерация готова, но списание не удалось. Проверьте баланс.",
                    )
        except Exception:
            logging.exception("generation error user=%s", user_id)
            await bot.send_message(chat_id, "⚠️ Ошибка генерации. Попробуйте ещё раз позже.")
        finally:
            logging.info("generation finish user=%s", user_id)
            self._locks.discard(user_id)

    async def _try_delete_message(
        self, bot: Bot, chat_id: int, message_id: int | None
    ) -> None:
        if not message_id:
            return
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            logging.warning("failed to delete status message id=%s", message_id)

    async def _send_generated_image(
        self,
        bot: Bot,
        chat_id: int,
        session: aiohttp.ClientSession,
        image_url: str,
    ) -> None:
        if await self._should_send_as_document(session, image_url):
            logging.info("sending generated image as document url=%s", image_url)
            await self._send_file_from_url(
                bot, chat_id, session, image_url, as_document=True
            )
            return
        try:
            logging.info("sending generated image as photo url=%s", image_url)
            await bot.send_photo(
                chat_id,
                photo=image_url,
                caption="Готово ✨\nХочешь попробовать другой стиль или сохранить этот образ?",
                reply_markup=result_actions_keyboard(),
            )
        except TelegramBadRequest as exc:
            logging.warning("send_photo failed, falling back to document: %s", exc)
            await self._send_file_from_url(bot, chat_id, session, image_url, as_document=True)

    async def _should_send_as_document(
        self,
        session: aiohttp.ClientSession,
        image_url: str,
    ) -> bool:
        if not self._telegram_photo_max_bytes:
            return False
        try:
            async with session.head(image_url, allow_redirects=True) as resp:
                if resp.status >= 400:
                    return False
                content_length = resp.headers.get("Content-Length")
                if not content_length:
                    return False
                return int(content_length) > self._telegram_photo_max_bytes
        except Exception:
            logging.warning("failed to check image size for %s", image_url)
            return False

    async def _send_file_from_url(
        self,
        bot: Bot,
        chat_id: int,
        session: aiohttp.ClientSession,
        image_url: str,
        *,
        as_document: bool,
    ) -> None:
        temp_path = None
        try:
            temp_path = await self._download_to_temp(session, image_url)
            input_file = FSInputFile(temp_path)
            if as_document:
                await bot.send_document(
                    chat_id,
                    document=input_file,
                    caption="Готово ✨\nХочешь попробовать другой стиль или сохранить этот образ?",
                    reply_markup=result_actions_keyboard(),
                )
            else:
                await bot.send_photo(
                    chat_id,
                    photo=input_file,
                    caption="Готово ✨\nХочешь попробовать другой стиль или сохранить этот образ?",
                    reply_markup=result_actions_keyboard(),
                )
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    async def _download_to_temp(
        self,
        session: aiohttp.ClientSession,
        image_url: str,
    ) -> str:
        suffix = Path(image_url).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
        async with session.get(image_url) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Failed to download image: {resp.status}")
            with open(temp_path, "wb") as file_handle:
                while True:
                    chunk = await resp.content.read(1024 * 64)
                    if not chunk:
                        break
                    file_handle.write(chunk)
        return temp_path
