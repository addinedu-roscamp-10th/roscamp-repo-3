#!/usr/bin/env python3

from pathlib import Path
import sys
import time

# 현재 파일 위치를 기준으로 프로젝트 루트 찾기
# 예: /home/addinedu/A_Ros2_project/test/integration/test_ui_server_heartbeat.py
# -> /home/addinedu/A_Ros2_project
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 프로젝트 루트를 import 검색 경로에 추가
# 그래야 ui.utils.network.tcp_client 같은 내부 모듈 import 가능
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# UI 쪽 TCP 요청 함수 import
from ui.utils.network.tcp_client import send_request


def main() -> int:
    # heartbeat 총 시도 횟수
    total = 5

    # heartbeat 간격(초)
    interval_sec = 2

    # 성공 횟수 카운터
    success_count = 0

    # total번 반복
    for i in range(total):
        # 서버에 HEARTBEAT 요청 전송
        # check_db=True 이므로 서버가 가능하면 DB 상태도 같이 확인
        result = send_request("HEARTBEAT", {"check_db": True})

        # 각 회차 결과 출력
        print(f"[{i+1}/{total}] ui-server-db heartbeat:", result)

        # 성공 조건:
        # 1) 서버 응답 ok == True
        # 2) 응답 안의 db.ok == True
        if result.get("ok") and result.get("db", {}).get("ok", False):
            success_count += 1

        # 다음 heartbeat 전까지 잠시 대기
        time.sleep(interval_sec)

    # 전체 성공 횟수 출력
    print(f"result: {success_count}/{total} success")

    # 전부 성공하면 종료 코드 0, 하나라도 실패하면 1
    return 0 if success_count == total else 1


if __name__ == "__main__":
    # main() 반환값을 프로그램 종료 코드로 사용
    raise SystemExit(main())