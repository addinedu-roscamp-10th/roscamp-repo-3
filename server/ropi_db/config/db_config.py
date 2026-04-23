import os

from dotenv import load_dotenv


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
SERVER_ROOT = os.path.join(PROJECT_ROOT, "server")

# Prefer server-specific env first so the server can be deployed by itself.
load_dotenv(os.path.join(SERVER_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "192.168.0.76"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "care_user"),
    "password": os.getenv("DB_PASSWORD", "1234"),
    "database": os.getenv("DB_NAME", "care_service"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
}

__all__ = ["DB_CONFIG"]
