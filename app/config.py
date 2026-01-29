from __future__ import annotations

import os
from dataclasses import dataclass


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _get_int(name: str, default: int | None = None) -> int:
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return int(value)


def _get_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


@dataclass(slots=True)
class Settings:
    bot_token: str
    database_path: str
    price_per_generation: int

    kie_api_key: str
    kie_api_base_url: str
    kie_file_base_url: str
    kie_model: str
    kie_resolution: str
    kie_aspect_ratio: str
    kie_output_format: str
    kie_poll_interval_seconds: int
    kie_max_poll_seconds: int

    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_return_url: str
    yookassa_poll_interval_seconds: int
    ideas_channel_url: str | None
    telegram_photo_max_bytes: int | None


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        bot_token=_get_env("BOT_TOKEN"),
        database_path=os.getenv("DATABASE_PATH", "data/app.db"),
        price_per_generation=_get_int("PRICE_PER_GENERATION", 50),
        kie_api_key=_get_env("KIE_API_KEY"),
        kie_api_base_url=os.getenv("KIE_API_BASE_URL", "https://api.kie.ai"),
        kie_file_base_url=os.getenv("KIE_FILE_BASE_URL", "https://kieai.redpandaai.co"),
        kie_model=os.getenv("KIE_MODEL", "nano-banana-pro"),
        kie_resolution=os.getenv("KIE_RESOLUTION", "4K"),
        kie_aspect_ratio=os.getenv("KIE_ASPECT_RATIO", "1:1"),
        kie_output_format=os.getenv("KIE_OUTPUT_FORMAT", "png"),
        kie_poll_interval_seconds=_get_int("KIE_POLL_INTERVAL_SECONDS", 5),
        kie_max_poll_seconds=_get_int("KIE_MAX_POLL_SECONDS", 300),
        yookassa_shop_id=_get_env("YOOKASSA_SHOP_ID"),
        yookassa_secret_key=_get_env("YOOKASSA_SECRET_KEY"),
        yookassa_return_url=_get_env("YOOKASSA_RETURN_URL"),
        yookassa_poll_interval_seconds=_get_int("YOOKASSA_POLL_INTERVAL_SECONDS", 15),
        ideas_channel_url=os.getenv("IDEAS_CHANNEL_URL"),
        telegram_photo_max_bytes=_get_optional_int("TELEGRAM_PHOTO_MAX_BYTES"),
    )
from dotenv import load_dotenv
