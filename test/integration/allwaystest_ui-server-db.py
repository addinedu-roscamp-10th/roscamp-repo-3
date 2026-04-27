from pathlib import Path
import sys
import time
from collections import deque

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def heartbeat_ok() -> bool:
    try:
        result = send_request("HEARTBEAT", {"check_db": True})
        return result.get("ok") and result.get("db", {}).get("ok", False)
    except Exception:
        return False


def main() -> int:
    interval_sec = 1
    window_sec = 60
    fail_threshold_sec = 10

    # 최근 60초 결과 저장: True=성공, False=실패
    history = deque(maxlen=window_sec)

    while True:
        ok = heartbeat_ok()
        history.append(ok)

        fail_count = sum(1 for x in history if not x)

        print(
            f"heartbeat={ok}, "
            f"window={len(history)}s, "
            f"fail={fail_count}s/{window_sec}s"
        )

        if len(history) == window_sec and fail_count >= fail_threshold_sec:
            print("FAIL: 최근 1분 동안 연결 끊김이 10초 이상 발생")
            return 1

        time.sleep(interval_sec)


if __name__ == "__main__":
    raise SystemExit(main())