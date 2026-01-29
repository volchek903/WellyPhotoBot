from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass(slots=True)
class KieTaskResult:
    status: str
    image_urls: list[str]


class KieClient:
    def __init__(
        self,
        api_key: str,
        api_base_url: str,
        file_base_url: str,
        model: str,
        resolution: str,
        aspect_ratio: str,
        output_format: str,
        poll_interval_seconds: int,
        max_poll_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._api_base_url = api_base_url.rstrip("/")
        self._file_base_url = file_base_url.rstrip("/")
        self._model = model
        self._resolution = resolution
        self._aspect_ratio = aspect_ratio
        self._output_format = output_format
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_seconds = max_poll_seconds

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def upload_file(self, session: aiohttp.ClientSession, path: str, upload_path: str) -> str:
        url = f"{self._file_base_url}/api/file-stream-upload"
        filename = os.path.basename(path)
        form = aiohttp.FormData()
        form.add_field("uploadPath", upload_path)
        form.add_field("fileName", filename)
        with open(path, "rb") as file_handle:
            form.add_field("file", file_handle, filename=filename)
            async with session.post(url, data=form, headers=self._headers()) as resp:
                data = await resp.json()
                if resp.status >= 400:
                    logging.warning("kie upload failed: %s %s", resp.status, data)
                    raise RuntimeError(f"Kie upload failed: {resp.status} {data}")
                file_url = (
                    data.get("data", {}).get("downloadUrl")
                    or data.get("data", {}).get("fileUrl")
                    or data.get("data", {}).get("url")
                )
                if not file_url:
                    logging.warning("kie upload missing url: %s", data)
                    raise RuntimeError(f"Kie upload missing file URL: {data}")
                return str(file_url)

    async def create_task(
        self,
        session: aiohttp.ClientSession,
        prompt: str,
        image_urls: list[str],
    ) -> str:
        url = f"{self._api_base_url}/api/v1/jobs/createTask"
        payload = {
            "model": self._model,
            "input": {
                "prompt": prompt,
                "image_input": image_urls,
                "aspect_ratio": self._aspect_ratio,
                "resolution": self._resolution,
                "output_format": self._output_format,
            },
            "config": {"service_mode": "public"},
        }
        async with session.post(url, json=payload, headers=self._headers()) as resp:
            data = await resp.json()
            if resp.status >= 400:
                logging.warning("kie createTask failed: %s %s", resp.status, data)
                raise RuntimeError(f"Kie createTask failed: {resp.status} {data}")
            task_id = data.get("data", {}).get("taskId")
            if not task_id:
                logging.warning("kie createTask missing taskId: %s", data)
                raise RuntimeError(f"Kie createTask missing taskId: {data}")
            return str(task_id)

    async def get_task(self, session: aiohttp.ClientSession, task_id: str) -> dict[str, Any]:
        url = f"{self._api_base_url}/api/v1/jobs/recordInfo"
        async with session.get(url, params={"taskId": task_id}, headers=self._headers()) as resp:
            data = await resp.json()
            if resp.status >= 400:
                logging.warning("kie recordInfo failed: %s %s", resp.status, data)
                raise RuntimeError(f"Kie recordInfo failed: {resp.status} {data}")
            return data

    async def poll_task(self, session: aiohttp.ClientSession, task_id: str) -> KieTaskResult:
        elapsed = 0
        while elapsed <= self._max_poll_seconds:
            data = await self.get_task(session, task_id)
            task_data = data.get("data", {})
            status = str(task_data.get("state") or task_data.get("status") or "")
            if status.lower() in {"success", "succeeded", "complete", "completed"}:
                result_json = task_data.get("resultJson") or {}
                parsed_urls: list[str] | list[Any] = []
                if isinstance(result_json, str):
                    try:
                        import json

                        parsed = json.loads(result_json)
                        if isinstance(parsed, dict):
                            result_json = parsed
                        elif isinstance(parsed, list):
                            parsed_urls = parsed
                            result_json = {}
                        else:
                            result_json = {}
                    except Exception:
                        logging.warning("kie resultJson is not json: %s", result_json)
                        result_json = {}
                if not isinstance(result_json, dict):
                    logging.warning("kie resultJson unexpected type: %s", type(result_json))
                    result_json = {}
                image_urls = (
                    result_json.get("resultUrls")
                    or result_json.get("result_urls")
                    or result_json.get("images")
                    or task_data.get("resultUrls")
                    or task_data.get("result_urls")
                    or []
                )
                if not image_urls and parsed_urls:
                    image_urls = parsed_urls
                if isinstance(image_urls, str):
                    image_urls = [image_urls]
                elif isinstance(image_urls, tuple):
                    image_urls = list(image_urls)
                elif not isinstance(image_urls, list):
                    image_urls = [str(image_urls)]
                return KieTaskResult(status=status, image_urls=list(image_urls))
            if status.lower() in {"failed", "error", "canceled", "cancelled"}:
                return KieTaskResult(status=status, image_urls=[])
            await asyncio.sleep(self._poll_interval_seconds)
            elapsed += self._poll_interval_seconds
        return KieTaskResult(status="timeout", image_urls=[])
