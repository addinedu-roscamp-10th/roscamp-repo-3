#!/usr/bin/env python3

from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.network.tcp_client import send_request


def run_ui_server_db_connection_check(total: int = 5, interval_sec: float = 1.0) -> tuple[int, list[dict]]:
    success_count = 0
    results = []

    for i in range(total):
        result = send_request("HEARTBEAT", {"check_db": True})
        payload = result.get("payload", {})
        results.append(result)

        print(f"[{i+1}/{total}] ui-server-db heartbeat:", result)

        if result.get("ok") and payload.get("db", {}).get("ok", False):
            success_count += 1

        if i != total - 1 and interval_sec > 0:
            time.sleep(interval_sec)

    return success_count, results


def main() -> int:
    total = 5
    success_count, _ = run_ui_server_db_connection_check(total=total)

    print(f"result: {success_count}/{total} success")

    return 0 if success_count == total else 1


def test_ui_server_db_connection_reports_db_status_on_every_heartbeat(patched_ui_endpoint):
    success_count, results = run_ui_server_db_connection_check(total=3, interval_sec=0)

    assert success_count == 3
    assert len(results) == 3

    for result in results:
        assert result["ok"] is True
        assert result["payload"]["db"]["ok"] is True


if __name__ == "__main__":
    raise SystemExit(main())
