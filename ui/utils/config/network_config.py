import os

from dotenv import load_dotenv

from ui.utils.core.paths import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env")

CONTROL_SERVER_HOST = os.getenv("CONTROL_SERVER_HOST", "127.0.0.1")
CONTROL_SERVER_PORT = int(os.getenv("CONTROL_SERVER_PORT", "5050"))
CONTROL_SERVER_TIMEOUT = float(os.getenv("CONTROL_SERVER_TIMEOUT", "3.0"))
HEARTBEAT_INTERVAL_MS = int(os.getenv("HEARTBEAT_INTERVAL_MS", "3000"))
