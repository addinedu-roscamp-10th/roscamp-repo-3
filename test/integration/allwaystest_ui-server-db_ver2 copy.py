#!/usr/bin/env python3

from pathlib import Path
import sys
import time
from collections import deque

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def heartbeat_check():
    try:
        result = send_request("HEARTBEAT", {"check_db": True})
        payload = result.get("payload", {})

        server_ok = result.get("ok", False)
        db_ok = payload.get("db", {}).get("ok", False)

        return {
            "server_ok": server_ok,
            "db_ok": db_ok,
            "result": result,
        }
    except Exception as e:
        return {
            "server_ok": False,
            "db_ok": False,
            "result": {"ok": False, "error": str(e)},
        }

def main() -> int:
    interval_sec = 1
    window_sec = 60
    fail_threshold_sec = 10

    history = deque(maxlen=window_sec)

    while True:
        status = heartbeat_check()

        server_ok = status["server_ok"]
        db_ok = status["db_ok"]
        detail = status["result"]

        ok = server_ok and db_ok
        history.append(ok)

        fail_count = sum(1 for x in history if not x)

        print(
            f"server_ok={server_ok}, "
            f"db_ok={db_ok}, "
            f"heartbeat={ok}, "
            f"window={len(history)}s, "
            f"fail={fail_count}s/{window_sec}s, "
            f"detail={detail}"
        )

        if len(history) == window_sec and fail_count >= fail_threshold_sec:
            print("FAIL: 최근 1분 동안 연결 끊김이 10초 이상 발생")
            return 1

        time.sleep(interval_sec)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        raise SystemExit(130)