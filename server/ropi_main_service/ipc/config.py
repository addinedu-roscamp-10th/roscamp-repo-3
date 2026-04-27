import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_ROS_SERVICE_SOCKET_PATH = "/tmp/ropi_control_ros_service.sock"
DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT = 1.0


def get_ros_service_ipc_config() -> dict:
    socket_path = str(
        os.getenv("ROPI_ROS_SERVICE_SOCKET_PATH", DEFAULT_ROS_SERVICE_SOCKET_PATH)
    ).strip()
    if not socket_path:
        raise RuntimeError(
            "ROPI_ROS_SERVICE_SOCKET_PATH가 비어 있습니다. "
            "루트 또는 server/.env를 확인하세요."
        )

    timeout_raw = str(
        os.getenv(
            "ROPI_ROS_SERVICE_SOCKET_TIMEOUT",
            str(DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT),
        )
    ).strip()
    if not timeout_raw:
        timeout_raw = str(DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT)

    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise RuntimeError(
            "ROPI_ROS_SERVICE_SOCKET_TIMEOUT는 숫자여야 합니다."
        ) from exc

    return {
        "socket_path": socket_path,
        "timeout": timeout,
    }


__all__ = [
    "DEFAULT_ROS_SERVICE_SOCKET_PATH",
    "DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT",
    "get_ros_service_ipc_config",
]
