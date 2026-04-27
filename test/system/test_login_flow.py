#!/usr/bin/env python3

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def main() -> int:
    response = send_request(
        "LOGIN",
        {
            "login_id": "VIS001",
            "password": "1234",
            "role": "visitor",
        },
    )

    if not response.get("ok"):
        print("System login test failed:", response)
        return 1

    session = response["payload"]
    assert session["user_id"]
    assert session["name"]
    assert session["role"] == "visitor"
    print("System login test passed:", session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
