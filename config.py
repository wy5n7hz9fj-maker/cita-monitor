import os
from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", required=True)
TELEGRAM_CHAT_ID = get_env("TELEGRAM_CHAT_ID", required=True)

PROVINCE = get_env("PROVINCE", "Barcelona")
OFFICE = get_env("OFFICE", "Rambla Guipúscoa")
PROCEDURE = get_env("PROCEDURE", "TOMA DE HUELLAS (EXPEDICIÓN DE TARJETA)")
NIE = get_env("NIE", required=True)
FULL_NAME = get_env("FULL_NAME", required=True)

CHECK_INTERVAL_SECONDS = int(get_env("CHECK_INTERVAL_SECONDS", "90"))
HEARTBEAT_EVERY_HOURS = int(get_env("HEARTBEAT_EVERY_HOURS", "12"))
HEADLESS = get_env("HEADLESS", "true").lower() == "true"
