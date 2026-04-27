#!/usr/bin/env python3

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def main() -> int:
    heartbeat = send_request("HEARTBEAT", {})
    print("ui-server heartbeat test:", heartbeat)

    login = send_request(
        "LOGIN",
        {
            "login_id": "VIS001",
            "password": "1234",
            "role": "visitor",
        },
    )
    print("ui-server login test:", login)

    return 0 if heartbeat.get("ok") and login.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
