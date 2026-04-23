# roscamp-repo-3

ROS2와 AI를 활용한 자율주행 로봇개발자 부트캠프 3팀 저장소.
로피(ROPI): 요양보호사 보조 로봇 시스템.

## Transport Runtime Setup

현재 기준 운반 전용 GUI와 메인 제어 서버는 같은 머신에서 실행하고,
DB는 원격 머신에 연결하는 구성을 기준으로 한다.

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
