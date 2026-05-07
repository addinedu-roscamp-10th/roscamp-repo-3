# 관제 서버 실행 가이드

이 문서는 실제 관제 서버에 이 레포를 배포한 뒤 서버 프로세스를 실행하는 명령어를 정리한다.

관제 서버에는 `~/pinky_pro`가 필요 없다. 관제 서버의 ROS 브릿지는 로봇을 직접 구동하지 않고, 이 레포의 `ropi_interface` action/service 타입만 사용해서 ROS graph에 명령을 보낸다.

관제 서버에서 상시 실행할 프로세스는 아래 3개다.

- ROS 브릿지: `ropi-ros-service`
- Control Service: `ropi-control-server`
- 영상 미디어 게이트웨이: `ropi-media-gateway`

## 전제

- ROS 2 Jazzy가 설치되어 있어야 한다.
- `uv`, `colcon`을 사용할 수 있어야 한다.
- DB 접속 정보와 서버 포트 설정은 레포 루트의 `.env`에 둔다.
- 아래 예시는 레포 경로가 `/home/addinedu/dev/roscamp-repo-3`인 경우다. 실제 서버 경로가 다르면 `cd` 경로만 바꾼다.

## 코드 갱신

```bash
cd /home/addinedu/dev/roscamp-repo-3
git pull
uv sync
```

## `.env` 기본값

레포 루트의 `.env`에 아래 값을 맞춘다.

```env
DB_HOST=<DB 서버 IP>
DB_PORT=3306
DB_USER=<DB 사용자>
DB_PASSWORD=<DB 비밀번호>
DB_NAME=<DB 이름>
DB_CHARSET=utf8mb4

CONTROL_SERVER_HOST=0.0.0.0
CONTROL_SERVER_PORT=5050
CONTROL_SERVER_TIMEOUT=3.0

ROPI_ROS_SERVICE_SOCKET_PATH=/tmp/ropi_control_ros_service.sock
ROPI_ROS_SERVICE_SOCKET_TIMEOUT=2.0

PATROL_PATH_TIMEOUT_SEC=180

AI_SERVER_HOST=192.168.0.89

VISION_GATEWAY_LISTEN_HOST=0.0.0.0
VISION_GATEWAY_LISTEN_PORT=5005
VISION_GATEWAY_AI_PORT=5005
VISION_GATEWAY_RECV_BUFFER=16MiB
VISION_GATEWAY_SEND_BUFFER=16MiB

AI_FALL_STREAM_ENABLED=true
AI_FALL_STREAM_PORT=6000
AI_FALL_STREAM_CONSUMER_ID=control_service_ai_fall
AI_FALL_STREAM_LAST_SEQ=0
```

`AI_SERVER_HOST`는 영상 미디어 게이트웨이, 낙상 추론 TCP 구독, 낙상 증거사진 조회가 같은 AI 서버를 바라볼 때 공통으로 쓰는 기본 IP다. 기능별로 다른 AI 서버를 써야 하면 아래 값을 개별로 추가해 공통값을 덮어쓴다.

```env
VISION_GATEWAY_AI_HOST=<영상 UDP를 받을 AI 서버 IP>
AI_FALL_STREAM_HOST=<낙상 추론 TCP push AI 서버 IP>
AI_FALL_EVIDENCE_HOST=<낙상 증거사진 조회 AI 서버 IP>
AI_FALL_EVIDENCE_PORT=6000
```

`PATROL_PINKY_ID`와 `AI_FALL_STREAM_PINKY_ID`는 기본 `.env`에 두지 않는다. 둘 다 단일 Pinky 문제를 좁혀 볼 때 쓰는 개발/디버그 옵션이다. 현재 phase 1 코드의 순찰 fallback 로봇은 `pinky3`이므로, 명시적으로 고정해 테스트할 때만 아래 값을 둔다.

```env
# 순찰 배정 로봇을 강제로 고정해야 할 때만 사용한다.
PATROL_PINKY_ID=pinky3

# PAT-005 TCP 구독을 특정 Pinky 결과로만 제한해야 할 때만 사용한다.
AI_FALL_STREAM_PINKY_ID=pinky3
```

`VISION_GATEWAY_RECV_BUFFER`, `VISION_GATEWAY_SEND_BUFFER`는 `16MiB`, `8MB`, `64KiB` 같은 단위를 지원한다. 기존 `VISION_GATEWAY_RECV_BUFFER_BYTES`, `VISION_GATEWAY_SEND_BUFFER_BYTES`도 동작하지만 하위 호환용이다.

관제 서버 방화벽에서 최소한 아래 포트를 열어둔다.

- `CONTROL_SERVER_PORT`: 외부 클라이언트가 Control Service에 접속하는 TCP 포트
- `VISION_GATEWAY_LISTEN_PORT`: 로봇 영상 프레임을 받는 UDP 포트

PAT-005 낙상 추론 결과 구독은 별도 실행 명령이 없다. `AI_FALL_STREAM_ENABLED=true`이면 `ropi-control-server`가 시작될 때 AI 서버의 TCP `6000`번 포트로 구독을 연결한다.

## ROS 인터페이스 빌드

관제 서버에서는 `ropi_interface`만 빌드하면 된다. `pinky_pro`를 source하지 않는다.

```bash
cd /home/addinedu/dev/roscamp-repo-3/device
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select ropi_interface
source /home/addinedu/dev/roscamp-repo-3/device/install/setup.bash
```

빌드 확인:

```bash
source /opt/ros/jazzy/setup.bash
source /home/addinedu/dev/roscamp-repo-3/device/install/setup.bash
python3 -c "from ropi_interface.action import ExecutePatrolPath; from ropi_interface.msg import GuidePhaseSnapshot; from ropi_interface.srv import FallResponseControl; print('ropi_interface ok')"
```

안내 `IF-GUI-007` phase snapshot은 `ropi-ros-service`가 ROS topic을 구독하고, `ropi-control-server`가 기본적으로 `get_runtime_status(include_guide=True)`를 polling해서 DB와 UI push로 수렴한다. 필요하면 `GUIDE_PHASE_SNAPSHOT_POLL_ENABLED=false`로 poller를 끌 수 있고, polling 주기는 `GUIDE_PHASE_SNAPSHOT_POLL_INTERVAL_SEC`로 조정한다.

## 실행 순서

아래 3개 명령은 각각 별도 터미널에서 실행한다.

### 1. ROS 브릿지

```bash
cd /home/addinedu/dev/roscamp-repo-3
source /opt/ros/jazzy/setup.bash
source /home/addinedu/dev/roscamp-repo-3/device/install/setup.bash
uv run ropi-ros-service
```

정상 실행 시 아래처럼 UDS 경로가 출력된다.

```text
ROPI ROS Service listening on /tmp/ropi_control_ros_service.sock
```

### 1-1. 개별 ROS action 테스트

운반 전체 태스크를 만들지 않고 Pinky 주행 또는 Jetcobot 팔 action만 따로 보낼 때는 `ropi-ros-action-test`를 사용한다. Control Service와 DB는 필요 없고, `ropi-ros-service`와 테스트할 대상 action server만 떠 있으면 된다.

도움말과 UDS 확인:

```bash
cd /home/addinedu/dev/roscamp-repo-3
uv run ropi-ros-action-test --help
test -S /tmp/ropi_control_ros_service.sock && echo "ROS bridge UDS ok"
```

대상별 readiness 확인:

```bash
# Pinky 주행 action만 확인한다.
uv run ropi-ros-action-test status --pinky-id pinky2

# arm action만 확인한다. Pinky 주행 노드가 없어도 이 확인은 가능하다.
uv run ropi-ros-action-test status --arm-id arm1
uv run ropi-ros-action-test status --arm-id arm2

# arm1, arm2를 한 번에 확인한다.
uv run ropi-ros-action-test status --arm-id arm1 --arm-id arm2
```

Pinky 주행 action 전송:

```bash
# --pose 형식은 x,y,yaw[,frame_id]다. yaw는 radian이다.
uv run ropi-ros-action-test nav \
  --pinky-id pinky2 \
  --task-id manual_nav_001 \
  --nav-phase DELIVERY_PICKUP \
  --pose "1.0,2.0,0.0" \
  --timeout-sec 120

# degree 단위 yaw가 필요하면 key-value 형식을 쓴다.
uv run ropi-ros-action-test nav \
  --pinky-id pinky2 \
  --task-id manual_nav_002 \
  --nav-phase RETURN_TO_DOCK \
  --pose "x=0.0,y=0.0,yaw_deg=180,frame_id=map"
```

Jetcobot 팔 action 전송:

```bash
# pickup-side arm: 물품을 Pinky 적재 슬롯으로 올린다.
uv run ropi-ros-action-test arm \
  --arm-id arm1 \
  --task-id manual_arm_load_001 \
  --transfer-direction TO_ROBOT \
  --item-id 1 \
  --quantity 1 \
  --robot-slot-id robot_slot_a1

# destination-side arm: Pinky 적재 슬롯에서 물품을 내린다.
uv run ropi-ros-action-test arm \
  --arm-id arm2 \
  --task-id manual_arm_unload_001 \
  --transfer-direction FROM_ROBOT \
  --item-id 1 \
  --quantity 1 \
  --robot-slot-id robot_slot_a1
```

### 2. Control Service

```bash
cd /home/addinedu/dev/roscamp-repo-3
uv run ropi-control-server --host "$CONTROL_SERVER_HOST" --port "$CONTROL_SERVER_PORT"
```

PAT-005 연결이 켜져 있으면 정상 로그에는 AI 서버 접속 시도, subscribe accepted, push batch 수신 내역이 출력된다.

### 3. 영상 미디어 게이트웨이

```bash
cd /home/addinedu/dev/roscamp-repo-3
uv run ropi-media-gateway
```

## 빠른 점검

서버 프로세스 실행 전:

```bash
cd /home/addinedu/dev/roscamp-repo-3
uv sync

cd /home/addinedu/dev/roscamp-repo-3/device
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select ropi_interface
source /home/addinedu/dev/roscamp-repo-3/device/install/setup.bash
```

서버 프로세스 실행 후:

```bash
ss -lntup | grep -E ':5050|:5005'
test -S /tmp/ropi_control_ros_service.sock && echo "ROS bridge UDS ok"
```

## 자주 나는 문제

- `ropi_interface` import 실패: 관제 서버에서 `device` 워크스페이스를 빌드/source하지 않은 상태다.
- Control Service 접속 실패: `CONTROL_SERVER_HOST`, `CONTROL_SERVER_PORT`, 서버 방화벽을 확인한다.
- DB 오류: `.env`의 DB 접속 정보와 DB 서버 방화벽을 확인한다.
- 영상이 AI 서버로 가지 않음: `ropi-media-gateway` 실행 여부, UDP 포트, AI 서버 IP, 방화벽을 확인한다.
- 낙상 감지 TCP push가 보이지 않음: `AI_FALL_STREAM_ENABLED=true`, `AI_SERVER_HOST`, `AI_FALL_STREAM_PORT=6000`을 확인한다. 단일 로봇 필터를 걸었으면 `AI_FALL_STREAM_PINKY_ID`와 AI 서버가 보내는 `pinky_id`가 같은지 확인한다.
- ROS 브릿지 UDS 오류: `ROPI_ROS_SERVICE_SOCKET_PATH`가 ROS 브릿지와 Control Service에서 같은 값인지 확인한다.
