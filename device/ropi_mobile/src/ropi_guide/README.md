# ropi_guide

`pinky1` 안내 시나리오에서 사람/대상 추적을 담당하는 패키지다. Pinky 카메라 영상을 UDP로 외부 인식 서버에 보내고, 서버가 돌려준 detection 결과를 바탕으로 속도 명령을 발행한다.

## 역할

- Pinky 카메라 프레임을 JPEG로 압축한다.
- 인식 서버로 이미지를 UDP 전송한다.
- 인식 서버의 결과를 UDP로 수신한다.
- detection 결과를 ROS topic으로 발행한다.
- 대상 위치에 따라 `cmd_vel` 명령을 발행한다.
- LCD가 사용 가능하면 추적 상태를 화면 색상으로 표시한다.

## 주요 파일

| 파일 | 용도 |
| --- | --- |
| `ropi_guide/tracking_node.py` | 안내/추적 메인 노드 |
| `launch/guide.launch.py` | 현재 실행용 launch 파일 |
| `package.xml`, `setup.py` | ROS 패키지 메타데이터 |

## 실행 전 준비

이 패키지는 Pinky 카메라와 `pinkylib` 사용을 전제로 한다. 일반 개발 PC에서는 카메라, LCD, Pinky 하드웨어 의존성 때문에 그대로 실행되지 않을 수 있다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/install/setup.bash
```

실행은 현재 launch 기준으로 한다.

```bash
ros2 launch ropi_guide guide.launch.py robot_id:=pinky1
```

또는 노드만 직접 실행할 수 있다. 이 경우 `server_ip`는 반드시 직접 넘겨야 한다.

```bash
ros2 run ropi_guide guide --ros-args -p server_ip:=192.168.4.15
```

## 현재 파라미터

`tracking_node.py`는 이미 많은 값을 ROS parameter로 받는다.

| 파라미터 | 의미 |
| --- | --- |
| `server_ip` | 인식 서버 IP |
| `server_video_port` | 카메라 프레임을 보낼 UDP 포트 |
| `result_port` | detection 결과를 받을 UDP 포트 |
| `jpeg_quality` | JPEG 압축 품질 |
| `cam_width`, `cam_height` | 카메라 프레임 크기 |
| `detection_topic` | detection 결과 발행 topic |
| `cmd_vel_topic` | 속도 명령 topic |
| `center_dead_band` | 좌우 오차 무시 범위 |
| `target_bbox_area` | 목표 거리 기준 bbox 면적 |
| `max_linear_x`, `max_angular_z` | 속도 제한 |

## 현재 config/주의점

- 로봇별 설정은 `config/pinky1/tracking.yaml`에서 관리한다.
- launch 파일은 `config/<robot_id>/tracking.yaml`을 읽어 노드에 전달한다.
- 현재 `cmd_vel_topic`은 `/cmd_vel`이다.
- Nav2도 `/cmd_vel`을 사용하는 경우 tracking과 navigation이 동시에 속도 명령을 내릴 수 있다.

따라서 `pinky1`에서 안내 모드와 navigation 모드를 동시에 켤지, 안내 모드에서는 tracking만 직접 `/cmd_vel`을 사용할지 먼저 정해야 한다.

## 설정 예시

```yaml
tracking_node:
  ros__parameters:
    server_ip: "관제 또는 인식 서버 IP"
    server_video_port: 5005
    result_port: 6006
    detection_topic: "tracking"
    cmd_vel_topic: "/cmd_vel"
```

## 팀 작업 규칙

- 새 IP, 포트, 튜닝값을 코드에 바로 추가하지 말고 `config/pinky1/tracking.yaml`에 반영한다.
- `cmd_vel_topic`을 바꿀 때는 Pinky navigation과 충돌하는지 확인한다.
- 인식 서버 프로토콜을 바꾸면 송신 이미지 형식과 수신 JSON 형식을 README에 같이 남긴다.
- Pinky 제조사 코드나 `~/pinky_pro` 내부 파일을 수정해서 문제를 해결하지 않는다.
