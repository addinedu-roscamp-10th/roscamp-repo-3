# ropi_patrol

`pinky3` 순찰/낙상 감지 시나리오 패키지다. `ropi_camera`가 Pinky 카메라 영상을 IF-COM-008 RUDP 규격으로 전송하고, `fallen_detection_client`가 서버 명령에 따라 순찰 navigation과 낙상 대응 상태를 제어한다.

## 역할

- `ropi_camera`가 Pinky 카메라 프레임을 IF-COM-008 RUDP datagram으로 전송한다.
- `fallen_detection_client`가 `ExecutePatrolPath` action으로 순찰 경로를 실행한다.
- `fallen_detection_client`가 `FallResponseControl` service로 낙상 대응 시작/해제를 받는다.
- alarm 상태를 `/fall_alarm` topic으로 발행한다.
- alarm이 켜지면 현재 Nav2 goal을 취소한다.
- alarm이 꺼지면 중단된 waypoint부터 다시 순찰을 시도한다.

## 주요 파일

| 파일 | 용도 |
| --- | --- |
| `ropi_patrol/fallen_detection_client.py` | PAT-003 순찰 action, PAT-004 낙상 대응 service, Nav2 제어 노드 |
| `ropi_patrol/ropi_camera.py` | 카메라 캡처, JPEG 인코딩, IF-COM-008 RUDP 전송 노드 |
| `ropi_patrol/fallen_alarm_buzzer.py` | `/fall_alarm`을 받아 부저 제어 |
| `ropi_patrol/fallen_alarm.py` | `/fall_alarm` 기반 알람 처리 후보 코드 |
| `ropi_patrol/camera.py` | Picamera2 기반 카메라 래퍼 |
| `ropi_patrol/buzzer.py` | GPIO 부저 제어 |
| `ropi_patrol/led.py`, `ropi_patrol/pinkyled.py` | LED 제어 코드 |

## 실행 전 준비

Pinky navigation이 먼저 떠 있어야 한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/install/setup.bash

ros2 launch ropi_nav_config pinky_nav.launch.py
```

순찰/낙상 감지 클라이언트를 실행한다. 기본 실행은 launch를 사용한다.

```bash
ros2 launch ropi_patrol patrol.launch.py robot_id:=pinky3
```

부저 노드를 별도 터미널에서 실행할 수 있다.

```bash
ros2 run ropi_patrol fallen_alarm_buzzer
```

## 현재 통신 방식

| 방향 | 방식 | 내용 |
| --- | --- | --- |
| Pinky3 `ropi_camera` -> 서버 | Custom UDP datagram (RUDP) | JPEG 프레임을 IF-COM-008 `FRAME_CHUNK` datagram으로 분할 전송 |
| Control Service -> Pinky3 `fallen_detection_client` | ROS2 Action | `/ropi/control/{pinky_id}/execute_patrol_path` 순찰 경로 실행 |
| Control Service -> Pinky3 `fallen_detection_client` | ROS2 Service | `/ropi/control/{pinky_id}/fall_response_control` 낙상 대응 시작/해제 |
| Pinky3 내부 | ROS topic | `/fall_alarm`에 `std_msgs/msg/Bool` 발행 |

### UDP 비전 프레임 스트림 요약

- 이 경로는 ROS2 `sensor_msgs/Image`가 아니라 별도 UDP data plane이다.
- 프레임 1장은 JPEG로 인코딩한 뒤 여러 개의 RUDP datagram으로 나누어 보낸다.
- 현재 revision에서 사용하는 `packet_type`은 `1 = FRAME_CHUNK`뿐이다.
- receiver는 `(stream_name, session_id, frame_id)`를 key로 frame assembly를 수행한다.
- latest-wins 정책이므로 stale frame, duplicate chunk, timeout된 incomplete frame은 폐기한다.

### RUDP header 필드

| 필드 | 타입 | 크기 | 설명 |
| --- | --- | --- | --- |
| `magic` | `bytes[4]` | 4 byte | 고정값 `RUDP` |
| `version` | `u8` | 1 byte | 현재 `1` |
| `packet_type` | `u8` | 1 byte | 현재 `1 = FRAME_CHUNK` |
| `reserved` | `u16` | 2 byte | 현재 `0` 고정 |
| `stream_name` | `bytes[24]` | 24 byte | UTF-8 null padded logical stream 이름 |
| `session_id` | `u32` | 4 byte | 스트림 세션 ID |
| `frame_id` | `u32` | 4 byte | 세션 내 프레임 순번 |
| `ts_us` | `u64` | 8 byte | 캡처 시각 us |
| `chunk_idx` | `u16` | 2 byte | 현재 청크 index |
| `chunk_count` | `u16` | 2 byte | 전체 청크 수 |
| `frame_len` | `u32` | 4 byte | JPEG 전체 길이 |
| `crc32` | `u32` | 4 byte | JPEG 전체 CRC32 |
| `payload` | `bytes` | 가변 | JPEG chunk bytes |

## 현재 config

운영 값은 `config/pinky3/patrol.yaml`에서 관리한다.

| 값 | 의미 |
| --- | --- |
| `server_ip` | `ropi_camera`의 RUDP 대상 서버 IP |
| `udp_port` | RUDP 비전 프레임 전송 포트 |
| `alarm_topic` | alarm topic 이름 |
| `pinky_id` | action/service 이름에 들어가는 Pinky ID |
| `patrol_action_name` | 비어 있으면 `/ropi/control/{pinky_id}/execute_patrol_path` |
| `fall_response_service_name` | 비어 있으면 `/ropi/control/{pinky_id}/fall_response_control` |
| `stream_name` | 24 byte 이하 logical stream 이름 |
| `udp_packet_size` | datagram 총 크기. 기본 권장값 1200 byte |
| `udp_send_buffer_size` | UDP 송신 버퍼 크기. 기본 권장값 4 MiB |
| `session_id` | `0`이면 실행 시 자동 생성되는 RUDP 세션 ID |
| `waypoints` | 서버 path 전환 이후에는 fallback/debug 용도 |
| `send_fps` | 카메라 전송 FPS |
| `nav_check_interval_sec` | Nav2 상태 확인 주기 |

`waypoints`는 ROS parameter 제약 때문에 dict list가 아니라 문자열 배열로 관리한다. 형식은 `"x,y,yaw_deg"`이다.

```yaml
fallen_detection_client:
  ros__parameters:
    alarm_topic: "/fall_alarm"
    pinky_id: "pinky3"
    patrol_action_name: ""
    fall_response_service_name: ""

ropi_camera:
  ros__parameters:
    server_ip: "메인 서버 또는 relay 서버 IP"
    udp_port: 5005
    stream_name: "pinky03_cam"
    udp_packet_size: 1200
    udp_send_buffer_size: 4194304
    session_id: 0
    send_fps: 10.0
```

## 팀 작업 규칙

- 순찰 waypoint의 source of truth는 Control Service가 보내는 PAT-003 `nav_msgs/Path`다.
- `config/pinky3/patrol.yaml`의 `waypoints`는 fallback/debug 용도로만 사용한다.
- 서버 IP와 포트는 로봇마다 달라질 수 있으므로 코드 상수로 고정하지 않는다.
- `stream_name`은 24 byte 이하 UTF-8 문자열이어야 하며 stream별로 겹치지 않게 관리한다.
- `/fall_alarm` topic 이름을 바꾸면 부저/LED 노드도 같이 맞춰야 한다.
- Nav2 map/parameter는 `ropi_nav_config/config/nav2_params.yaml`과 `ropi_nav_config/maps/`에서 관리한다.
- GPIO, LED, 카메라 권한 문제를 해결하기 위해 제조사 `~/pinky_pro` 코드를 수정하지 않는다.
