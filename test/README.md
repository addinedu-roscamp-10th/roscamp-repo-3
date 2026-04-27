# test

프로젝트 테스트는 실행 범위와 책임 기준으로 나눈다.

- `unit/`: DB/ROS 실환경 없이 빠르게 도는 단위 테스트
- `integration/`: UI, server, DB 연결처럼 외부 구성 요소가 필요한 확인
- `system/`: 실제 실행 흐름에 가까운 smoke/e2e 테스트

`unit/` 하위는 다시 코드 책임 기준으로 나눈다.

- `unit/server/ropi_main_service/application/`: 운반 요청, 운반 workflow, goal pose 설정, runtime readiness
- `unit/server/ropi_main_service/ros/`: ROS action client, ROS service UDS server
- `unit/server/ropi_main_service/ipc/`: UDS client/protocol/config
- `unit/server/ropi_main_service/transport/`: TCP server/protocol
- `unit/server/ropi_main_service/contracts/`: IF-COM/IF-DEL 인터페이스 계약
- `unit/device/`: device workspace/package 구조 계약
- `unit/ui/`: UI 쪽 network client 단위 테스트

`integration/` 정리 규칙:

- `test_*.py`: `pytest`가 수집하는 정식 통합 테스트
- `check_*.py`: 사람이 직접 실행하는 단건 연결 점검 스크립트
- `monitor_*.py`: 일정 시간 동안 상태를 관찰하는 수동 모니터링 스크립트

현재 `integration/` 루트 대표 파일:

- `test_if_com_007_runtime_wireup.py`: server-ROS runtime wire-up 통합 테스트
- `test_runtime_ui_server.py`: UI-server-DB 실제 런타임 통합 테스트
- `test_server_db_connection.py`: server에서 DB 직접 연결 확인
- `test_ui_server_connection.py`: UI 기준 server 연결 확인 겸 자동 테스트
- `test_ui_server_db_connection.py`: UI 기준 server-DB 연결 확인 겸 자동 테스트
- `monitor_ui_server_db_1min.py`: UI 기준 server-DB 1분 모니터링
