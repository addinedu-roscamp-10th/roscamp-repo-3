# Device 워크스페이스 가이드

이 디렉터리는 실제 로봇에서 실행되는 ROS 패키지를 관리한다. 최상위 프로젝트 README와 별개로, 로봇/시나리오 팀이 어떤 코드를 어디에 두고 어떻게 실행해야 하는지 설명한다.

## 기본 원칙

- `pinky_pro` 제조사 코드는 이 레포에 넣지 않는다.
- 각 Pinky 로봇은 기존처럼 홈 디렉터리의 `~/pinky_pro`를 사용한다.
- 이 레포는 제조사 코드를 수정하는 대신, 우리 프로젝트용 패키지와 설정을 overlay 워크스페이스로 얹는다.
- 관제 서버와 로봇 사이의 공통 action 정의는 `ropi_common/src/ropi_interface` 하나만 정본으로 둔다.
- 로봇별 IP, 포트, topic, waypoint 같은 운영 값은 각 패키지의 `config/<robot_id>/*.yaml`에서 관리한다.

## 로봇 배정

| 로봇 | 담당 시나리오 | 레포 내 패키지 |
| --- | --- | --- |
| `pinky1` | 안내 | `device/ropi_mobile/src/tracking` |
| `pinky2` | 운반 | `device/ropi_mobile/src/pinky_delivery` |
| `pinky3` | 순찰 | `device/ropi_mobile/src/fallen_detection` |
| `jetcobot1` | 운반 arm1 | `device/ropi_arm/src/jet_arm_control` |
| `jetcobot2` | 운반 arm2 | `device/ropi_arm/src/jet_arm_control` |

## 디렉터리 구조

```text
device/
  ropi_common/
    src/ropi_interface/       # 관제 서버와 모든 로봇이 공유하는 ROS action 정의
  ropi_mobile/
    src/ropi_pinky_config/    # ~/pinky_pro의 pinky_navigation을 감싸는 우리 설정 패키지
    src/pinky_delivery/       # pinky2 운반 시나리오
    src/tracking/             # pinky1 안내 시나리오
    src/fallen_detection/     # pinky3 순찰/낙상 감지 시나리오
  ropi_arm/
    src/jet_arm_control/      # jetcobot1, jetcobot2 공용 arm action server
```

## Pinky 로봇 빌드 순서

Pinky 로봇에서는 제조사 워크스페이스를 먼저 source하고, 그 위에 이 레포의 공통/모바일 워크스페이스를 올린다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash

cd ~/roscamp-repo-3/device/ropi_common
colcon build
source install/setup.bash

cd ~/roscamp-repo-3/device/ropi_mobile
colcon build
source install/setup.bash
```

Pinky navigation은 `ropi_pinky_config`로 실행한다. 이 launch가 `~/pinky_pro` 안의 `pinky_navigation` launch를 include하면서 우리 레포의 map과 Nav2 parameter를 넘긴다.

```bash
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky1
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky2
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky3
```

시나리오 노드는 각 패키지 launch로 실행한다.

```bash
ros2 launch tracking tracking.launch.py robot_id:=pinky1
ros2 launch pinky_delivery pinky_delivery.launch.py robot_id:=pinky2
ros2 launch fallen_detection patrol.launch.py robot_id:=pinky3
```

## JetCobot 로봇 빌드 순서

JetCobot은 제조사 Pinky 워크스페이스가 필요하지 않다. 공통 인터페이스를 먼저 빌드하고 arm 패키지를 빌드한다.

```bash
source /opt/ros/jazzy/setup.bash

cd ~/roscamp-repo-3/device/ropi_common
colcon build
source install/setup.bash

cd ~/roscamp-repo-3/device/ropi_arm
colcon build
source install/setup.bash
```

```bash
ros2 launch jet_arm_control jet_arm.launch.py robot_id:=jetcobot1
ros2 launch jet_arm_control jet_arm.launch.py robot_id:=jetcobot2
```

## 관제 연동 계약

관제 서버는 아래 action 이름으로 로봇을 찾는다. 각 팀은 이 규칙을 깨면 안 된다.

| 기능 | action 이름 |
| --- | --- |
| Pinky 목적지 이동 | `/ropi/control/<pinky_id>/navigate_to_goal` |
| JetCobot 조작 | `/ropi/arm/<arm_id>/execute_manipulation` |

현재 1차 운반 연동 기준 값은 다음과 같다.

| 대상 | 값 |
| --- | --- |
| 배송 Pinky | `pinky2` |
| 픽업 arm | `arm1` |
| 도착지 arm | `arm2` |

## 각 팀이 먼저 읽어야 할 README

- 운반 Pinky 팀: `device/ropi_mobile/src/pinky_delivery/README.md`
- 안내 팀: `device/ropi_mobile/src/tracking/README.md`
- 순찰 팀: `device/ropi_mobile/src/fallen_detection/README.md`
- JetCobot 팀: `device/ropi_arm/src/jet_arm_control/README.md`
- Pinky map/parameter 담당: `device/ropi_mobile/src/ropi_pinky_config/README.md`
- 관제/로봇 action 계약 담당: `device/ropi_common/src/ropi_interface/README.md`

## 지금 상태에서 주의할 점

- `pinky_delivery`는 `mobile_controller_test.py`가 실제 관제 연동에 성공한 실행 경로다.
- `transport_control_node.py`는 현재 정식 운용 경로가 아니므로, 검증 전까지 메인 실행 파일로 바꾸면 안 된다.
- `tracking`, `pinky_delivery`, `fallen_detection`의 운영 값은 각 패키지의 `config/<robot_id>/*.yaml`로 분리되어 있다.
- 새 IP, 포트, waypoint, action 이름을 코드에 직접 추가하지 말고 config와 launch를 통해 주입한다.
