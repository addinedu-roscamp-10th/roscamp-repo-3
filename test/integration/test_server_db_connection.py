#!/usr/bin/env python3

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.ropi_db.connection import fetch_one, test_connection


def main() -> int:
    success, result = test_connection()
    if not success:
        print("server-db connection test failed:", result)
        return 1

    info = fetch_one(
        """
        SELECT
            DATABASE() AS current_db,
            USER() AS db_user,
            NOW() AS server_time
        """
    )

    print("server-db connection test passed:", result)
    print("server-db query test passed:", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
