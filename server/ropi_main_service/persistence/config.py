import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

# Prefer server-specific env first so the server can be deployed by itself.
load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

_REQUIRED_ENV_KEYS = {
    "host": "DB_HOST",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
    "database": "DB_NAME",
}


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": _get_int_env("DB_PORT", 3306),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "connect_timeout": _get_int_env("DB_CONNECT_TIMEOUT", 5),
    "read_timeout": _get_int_env("DB_READ_TIMEOUT", 5),
    "write_timeout": _get_int_env("DB_WRITE_TIMEOUT", 5),
}


def get_db_config() -> dict:
    config = dict(DB_CONFIG)
    missing = []

    for field_name, env_name in _REQUIRED_ENV_KEYS.items():
        value = str(config.get(field_name) or "").strip()
        if not value:
            missing.append(env_name)
            continue
        config[field_name] = value

    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"DB 연결 설정이 비어 있습니다: {missing_list}. "
            "루트 또는 server/.env를 확인하세요."
        )

    return config


__all__ = ["DB_CONFIG", "get_db_config"]
