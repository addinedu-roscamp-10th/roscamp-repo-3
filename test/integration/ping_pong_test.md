# 간이 통신 Bring-up 테스트 플랜

## 1. 목적

이 문서는 **첫 통신 연결 확인용 간이 테스트 플랜**이다.  
목표는 복잡한 기능 검증이 아니라, 각 컴포넌트 사이에서 **메시지가 최소한 오가고**, 마지막에 **GUI에 상태가 렌더링되는지** 빠르게 확인하는 것이다.

이 문서의 truth source는 `interface_spec_ko.md`이지만, 여기서 수행하는 테스트는 **정식 프로덕트 기능 검증**이 아니라 **초기 bring-up용 smoke test**다.

---

## 2. 범위

이 문서에서 확인하는 것은 아래 두 가지뿐이다.

- 1:1 `ping/pong` 수준의 연결 확인
- `GUI -> 서버 -> DB/로봇 -> 서버 -> GUI 렌더링` 최소 1건

이 문서에서 확인하지 않는 것은 아래와 같다.

- 실제 로봇 주행 / manipulation
- 실제 AI 추론 품질
- task lifecycle 정확성
- DB 영속화 상세 검증
- 재연결 / replay / 장애 복구 / 장시간 soak test

---

## 3. 테스트 원칙

- 이 문서의 `ping/pong`은 **정식 업무 메시지**가 아니라 초기 연결 확인용 임시 메시지다.
- 로봇은 실제 동작할 필요가 없다.
  - synthetic status 메시지 1건을 보내거나,
  - 테스트용 응답 메시지 1건을 반환하면 된다.
- 대표 장비 1대 기준으로 먼저 붙인다.
  - Pinky는 `pinky_01`
  - Jetcobot은 `jetcobot_01`
- 다른 장비는 ID만 바꿔 같은 방식으로 반복한다.

---

## 4. 1:1 Ping/Pong 테스트

| 번호 | Name | 목적 | Protocol | Input | Output |
| --- | --- | --- | --- | --- | --- |
| PP-01 | GUI - Control Service | GUI와 서버 사이 기본 연결 확인 | TCP | GUI에서 `ping` 요청 전송 | 서버가 `pong` 또는 동등한 정상 응답 반환 |
| PP-02 | Control Service - DB | 서버와 DB 사이 기본 연결 확인 | TCP | 서버에서 DB 연결 확인용 `ping` 또는 단순 조회 전송 | DB 응답 성공, 서버가 DB reachable 상태로 판단 |
| PP-03 | Control Service - AI Service | 서버와 AI 서비스 사이 기본 연결 확인 | TCP 또는 UDP | 서버에서 AI 서비스로 `ping` 전송 | AI 서비스가 `pong` 또는 동등한 정상 응답 반환 |
| PP-04 | Control Service - Pinky-01 | 서버와 Pinky 대표 1대 사이 기본 연결 확인 | ROS/UDP 또는 테스트용 임시 메시지 | 서버에서 Pinky 연결 확인 요청 또는 Pinky가 synthetic status 1건 송신 | 서버가 Pinky online 또는 reachable 상태로 판단 |
| PP-05 | Control Service - Jetcobot-01 | 서버와 Jetcobot 대표 1대 사이 기본 연결 확인 | ROS/UDP 또는 테스트용 임시 메시지 | 서버에서 Jetcobot 연결 확인 요청 또는 Jetcobot이 synthetic status 1건 송신 | 서버가 Jetcobot online 또는 reachable 상태로 판단 |

메모:

- `PP-04`, `PP-05`는 실제 로봇 제어가 아니라 **연결 확인용 status 수신**만 보면 된다.
- 실제 구현이 request/response보다 topic publish에 가깝더라도, 이 단계에서는 **서버가 메시지를 1건이라도 정상 수신했는지**를 합격 기준으로 둔다.

### 4-1. 예시 Payload

메모:

- `PP-01`, `PP-02`, `PP-03`의 예시는 **임시 bring-up 메시지 예시**다.
- `PP-04`, `PP-05`의 예시는 `interface_spec_ko.md`의 상태 메시지 필드명을 최대한 맞춘 **synthetic status 예시**다.

`PP-01` GUI -> Control Service `ping` 요청 예시:

```json
{
  "type": "PING",
  "source": "desktop_gui",
  "target": "control_service",
  "request_id": "pp-01-001",
  "timestamp": "2026-04-23T10:00:00+09:00"
}
```

`PP-01` Control Service -> GUI `pong` 응답 예시:

```json
{
  "type": "PONG",
  "source": "control_service",
  "target": "desktop_gui",
  "request_id": "pp-01-001",
  "status": "ok",
  "timestamp": "2026-04-23T10:00:00+09:00"
}
```

`PP-02` Control Service -> DB 단순 조회 예시:

```sql
SELECT 1 AS ping;
```

`PP-02` DB -> Control Service 응답 예시:

```json
[
  {
    "ping": 1
  }
]
```

`PP-03` Control Service -> AI Service `ping` 요청 예시:

```json
{
  "type": "PING",
  "source": "control_service",
  "target": "ai_service",
  "request_id": "pp-03-001",
  "timestamp": "2026-04-23T10:01:00+09:00"
}
```

`PP-03` AI Service -> Control Service `pong` 응답 예시:

```json
{
  "type": "PONG",
  "source": "ai_service",
  "target": "control_service",
  "request_id": "pp-03-001",
  "status": "ok",
  "timestamp": "2026-04-23T10:01:00+09:00"
}
```

`PP-04` Pinky -> Control Service synthetic status 예시:

```yaml
pinky_id: "pinky_01"
pinky_state: "IDLE"
active_task_id: ""
charging_state: "NOT_CHARGING"
docked: false
battery_percent: 82.3
battery_voltage: 24.8
fault_code: ""
pose:
  header:
    stamp:
      sec: 1776915600
      nanosec: 0
    frame_id: "map"
  pose:
    position:
      x: 1.2
      y: 2.4
      z: 0.0
    orientation:
      x: 0.0
      y: 0.0
      z: 0.0
      w: 1.0
timestamp:
  sec: 1776915600
  nanosec: 0
```

`PP-05` Jetcobot -> Control Service synthetic status 예시:

```yaml
arm_id: "jetcobot_01"
station_role: "PICKUP"
arm_state: "READY"
active_task_id: ""
active_transfer_direction: ""
active_item_id: ""
active_robot_slot_id: ""
fault_code: ""
timestamp:
  sec: 1776915660
  nanosec: 0
```

---

## 5. 최소 통합 테스트

이 테스트는 실제 서비스 플로우 전체를 검증하려는 것이 아니라,  
**GUI에서 시작한 확인 요청이 서버를 거쳐 DB와 로봇 상태를 확인하고 다시 GUI에 표시되는지**만 본다.

| 번호 | Name | Description | Input | Output |
| --- | --- | --- | --- | --- |
| IT-01 | GUI 상태 점검 및 렌더링 | GUI에서 점검 시작 요청을 보내면 서버가 DB 연결 상태와 로봇 상태를 확인한 뒤 결과를 다시 GUI에 반영하는지 확인 | GUI에서 네트워크/연결 점검 시작 요청 전송. 서버는 DB 확인 1건, Pinky 또는 Jetcobot 상태 메시지 1건 이상 수신 | GUI 화면에 서버/DB/로봇 상태가 `정상`, `오프라인`, `오류` 중 하나로 렌더링됨 |

권장 흐름:

1. GUI가 서버에 점검 시작 요청을 보낸다.
2. 서버가 DB 연결 확인을 수행한다.
3. 서버가 Pinky 또는 Jetcobot에서 상태 메시지 1건을 받는다.
4. 서버가 결과를 GUI에 전달한다.
5. GUI가 각 대상을 상태값으로 렌더링한다.

메모:

- 이 테스트는 대표 로봇 1대만으로 먼저 수행해도 된다.
- Pinky와 Jetcobot을 둘 다 붙일 수 있으면 둘 다 표시하고, 아니면 먼저 붙는 한 대만으로 통과시켜도 된다.

### 5-1. 예시 Payload

`IT-01` GUI -> Control Service 점검 시작 요청 예시:

```json
{
  "type": "CHECK_START",
  "request_id": "it-01-001",
  "requested_by": "desktop_gui",
  "targets": [
    "control_service",
    "db",
    "pinky_01",
    "jetcobot_01"
  ],
  "timestamp": "2026-04-23T10:05:00+09:00"
}
```

`IT-01` Control Service -> GUI 점검 결과 응답 예시:

```json
{
  "type": "CHECK_RESULT",
  "request_id": "it-01-001",
  "overall_status": "정상",
  "results": [
    {
      "component": "control_service",
      "status": "정상"
    },
    {
      "component": "db",
      "status": "정상"
    },
    {
      "component": "pinky_01",
      "status": "정상",
      "detail": {
        "battery_percent": 82.3,
        "pose": {
          "x": 1.2,
          "y": 2.4,
          "theta_deg": 0.0
        }
      }
    },
    {
      "component": "jetcobot_01",
      "status": "정상",
      "detail": {
        "arm_state": "READY"
      }
    }
  ],
  "timestamp": "2026-04-23T10:05:03+09:00"
}
```

`IT-01` GUI 렌더링 예시 상태:

```json
{
  "server": "정상",
  "db": "정상",
  "pinky_01": "정상",
  "jetcobot_01": "정상"
}
```

---

## 6. 합격 기준

- `PP-01` ~ `PP-05` 중 대상별 테스트에서 요청 또는 synthetic message 1건 이상이 정상 수신된다.
- 서버는 각 대상에 대해 최소한 `reachable`, `online`, `offline`, `error` 중 하나의 상태를 결정할 수 있다.
- `IT-01`에서 GUI가 서버/DB/로봇 상태를 화면에 표시한다.
- 이 과정에서 프로세스 crash, 세션 즉시 종료, 메시지 파싱 실패가 발생하지 않는다.

---

## 7. 실행 순서

1. `PP-01`
2. `PP-02`
3. `PP-03`
4. `PP-04`
5. `PP-05`
6. `IT-01`

---

## 8. 결과 기록 형식

| Test ID | 실행 일시 | 실행자 | 결과 | 비고 |
| --- | --- | --- | --- | --- |
| PP-01 | YYYY-MM-DD hh:mm | 이름 | PASS / FAIL | 응답 시간, 로그 위치 등 |
