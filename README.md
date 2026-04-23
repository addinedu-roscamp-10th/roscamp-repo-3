# roscamp-repo-3

ROS2와 AI를 활용한 자율주행 로봇개발자 부트캠프 3팀 저장소.
로피(ROPI): 요양보호사 보조 로봇 시스템.

## Transport Runtime Setup

현재 기준 운반 전용 GUI와 메인 제어 서버는 같은 머신에서 실행하고,
DB는 원격 머신에 연결하는 구성을 기준으로 한다.

### Phase 1 Assumptions

- 1차 구현에서는 관제 스케줄링을 아직 두지 않는다.
- 운반 작업은 즉시 `pinky2`에 할당되는 정책으로 가정한다.
- 따라서 `IF-DEL-001` 응답의 `assigned_pinky_id`는 현재 `pinky2`로 고정된다.
- 다음 공통 이동 연동은 `IF-COM-007`을 `/ropi/control/pinky2/navigate_to_goal` 기준으로 붙인다.

### 1. 환경 동기화

```bash
uv sync
```

### 2. `.env` 준비

루트 `.env`에 아래 값이 필요하다.

```env
DB_HOST=<remote-db-host>
DB_PORT=3306
DB_USER=<db-user>
DB_PASSWORD=<db-password>
DB_NAME=<db-name>
DB_CHARSET=utf8mb4

CONTROL_SERVER_HOST=127.0.0.1
CONTROL_SERVER_PORT=5050
CONTROL_SERVER_TIMEOUT=3.0
HEARTBEAT_INTERVAL_MS=3000
ROPI_ROS_SERVICE_SOCKET_PATH=/tmp/ropi_control_ros_service.sock
ROPI_ROS_SERVICE_SOCKET_TIMEOUT=1.0
```

- `DB_HOST`는 원격 DB 머신 주소를 넣는다.
- 로컬에서 GUI와 서버를 같이 띄울 때는 `CONTROL_SERVER_HOST=127.0.0.1`을 유지한다.

### 3. 실행

서버:

```bash
uv run ropi-control-server
```

관리자 UI:

```bash
uv run ropi-admin-ui
```

사용자 UI:

```bash
uv run ropi-user-ui
```

### 4. 확인

서버 도움말:

```bash
./.venv/bin/ropi-control-server --help
```

현재 환경에서는 로컬 서버 실행, GUI 모듈 import, 원격 DB heartbeat/read 경로까지 확인했다.

### 5. 테스트

단위 테스트:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --group dev pytest test/unit -q
```

운반 런타임 통합 테스트:

```bash
QT_QPA_PLATFORM=offscreen PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --group dev pytest test/integration/test_runtime_ui_server.py -q
```
