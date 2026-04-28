#!/usr/bin/env python3

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def run_ui_server_connection_check() -> tuple[dict, dict]:
    heartbeat = send_request("HEARTBEAT", {})
    login = send_request(
        "LOGIN",
        {
            "login_id": "1",
            "password": "1234",
            "role": "visitor",
        },
    )

    return heartbeat, login


def main() -> int:
    heartbeat, login = run_ui_server_connection_check()

    print("ui-server heartbeat test:", heartbeat)
    print("ui-server login test:", login)

    return 0 if heartbeat.get("ok") and login.get("ok") else 1


def test_ui_server_connection_reports_heartbeat_and_login_success(patched_ui_endpoint):
    heartbeat, login = run_ui_server_connection_check()

    assert heartbeat["ok"] is True
    assert heartbeat["payload"]["message"] == "메인 서버 연결 정상"

    assert login["ok"] is True
    assert login["payload"]["user_id"]
    assert login["payload"]["name"]
    assert login["payload"]["role"] == "visitor"


if __name__ == "__main__":
    raise SystemExit(main())
