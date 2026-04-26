# ropi_patrol

`pinky3` 순찰/낙상 감지 시나리오 패키지다. Pinky 카메라 영상을 낙상 감지 서버로 보내고, 서버에서 받은 alarm 상태에 따라 순찰 navigation을 중지하거나 재개한다.

## 역할

- Pinky 카메라 프레임을 UDP로 낙상 감지 서버에 전송한다.
- 낙상 감지 서버의 TCP alarm 메시지를 수신한다.
- alarm 상태를 `/fall_alarm` topic으로 발행한다.
- alarm이 켜지면 현재 Nav2 goal을 취소한다.
- alarm이 꺼지면 중단된 goal부터 다시 순찰을 시작한다.
- 모든 waypoint를 완료하면 순찰을 종료한다.

## 주요 파일

| 파일 | 용도 |
| --- | --- |
| `ropi_patrol/fallen_detection_client_tcp.py` | 카메라 전송, TCP alarm 수신, 순찰 navigation 메인 노드 |
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
| Pinky3 -> 낙상 서버 | UDP | 카메라 JPEG 프레임 전송 |
| 낙상 서버 -> Pinky3 | TCP | `{"alarm": true}` 또는 `{"alarm": false}` 수신 |
| Pinky3 내부 | ROS topic | `/fall_alarm`에 `std_msgs/msg/Bool` 발행 |

## 현재 config

운영 값은 `config/pinky3/patrol.yaml`에서 관리한다.

| 값 | 의미 |
| --- | --- |
| `server_ip` | 낙상 감지 서버 IP |
| `udp_port` | 이미지 전송 UDP 포트 |
| `tcp_port` | alarm 수신 TCP 포트 |
| `alarm_topic` | alarm topic 이름 |
| `waypoints` | 순찰 경로 |
| `send_fps` | 카메라 전송 FPS |
| `nav_check_interval_sec` | Nav2 상태 확인 주기 |

`waypoints`는 ROS parameter 제약 때문에 dict list가 아니라 문자열 배열로 관리한다. 형식은 `"x,y,yaw_deg"`이다.

```yaml
fallen_detection_client_tcp:
  ros__parameters:
    server_ip: "낙상 감지 서버 IP"
    udp_port: 5005
    tcp_port: 6000
    alarm_topic: "/fall_alarm"
    send_fps: 10.0
    waypoints:
      - "0.95,-0.06,0.0"
      - "0.95,0.27,0.0"
```

## 팀 작업 규칙

- 순찰 waypoint를 코드에 직접 추가하지 말고 `config/pinky3/patrol.yaml`에 반영한다.
- 낙상 서버 IP와 포트는 로봇마다 달라질 수 있으므로 코드 상수로 고정하지 않는다.
- `/fall_alarm` topic 이름을 바꾸면 부저/LED 노드도 같이 맞춰야 한다.
- Nav2 map/parameter는 `ropi_nav_config/config/nav2_params.yaml`과 `ropi_nav_config/maps/`에서 관리한다.
- GPIO, LED, 카메라 권한 문제를 해결하기 위해 제조사 `~/pinky_pro` 코드를 수정하지 않는다.
