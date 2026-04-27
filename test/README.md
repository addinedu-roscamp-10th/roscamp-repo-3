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
