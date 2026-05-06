# Pinky Nav Status Runbook

이 문서는 `pinky_nav.launch.py`가 Pinky navigation bringup과 IF-COM-005 status publisher를 함께 띄우는지 확인하는 절차다.

## 결론

- `pinky_nav.launch.py`는 공통 주행 기반을 띄운다.
- 이제 `pinky_nav.launch.py` 실행 시 `pinky_status_runtime_publisher.py`도 같이 실행된다.
- 운반, 순찰, 안내 업무 노드는 별도 시나리오 launch로 실행한다.
- status만 확인할 때는 시나리오 launch가 필요 없다.

## 역할 구분

| 구성 | 역할 | 필요할 때 |
| --- | --- | --- |
| `ropi_nav_config pinky_nav.launch.py` | Pinky navigation bringup, map, Nav2, status publisher | 주행 기반과 status 확인 |
| `ropi_delivery ropi_delivery.launch.py` | 운반 시나리오 action server | 운반 업무 테스트 |
| `ropi_patrol patrol.launch.py` | 순찰/낙상 시나리오 노드 | 순찰 업무 테스트 |
| `ropi_guide guide.launch.py` | 안내 tracking 노드 | 안내 업무 테스트 |

## Pinky 터미널 1: 빌드

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash

git pull origin control_team
colcon build --packages-up-to ropi_nav_config ropi_mobile_status_test
source install/setup.bash
```

실행 파일 확인:

```bash
ros2 pkg executables ropi_mobile_status_test
```

기대:

```text
ropi_mobile_status_test pinky_status_runtime_publisher.py
```

## Pinky 터미널 1: 공통 navigation + status 실행

기본 운반 Pinky:

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky2
```

순찰 Pinky:

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky3
```

안내 Pinky:

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky1
```

기대 로그:

```text
[pinky_status_runtime_publisher]: Using Odometry source topic: /odom
[pinky_status_runtime_publisher]: Using battery voltage source topic: /battery/voltage
[pinky_status_runtime_publisher]: Using state source topic: /transport/amr_status
[pinky_status_runtime_publisher]: Publishing IF-COM-005 Pinky status on /ropi/robots/pinky2/status
```

## Pinky 터미널 2: 발행 확인

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

topic 목록:

```bash
ros2 topic list | grep -E "odom|battery|amr|ropi/robots"
```

직접 확인:

```bash
ros2 topic echo /battery/voltage --once
ros2 topic echo /odom --once
ros2 topic echo /ropi/robots/pinky2/status --once
```

`robot_id:=pinky3`로 실행했다면:

```bash
ros2 topic echo /ropi/robots/pinky3/status --once
```

## PC 터미널: subscriber 확인

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

필요하면 PC에서 interface만 빌드:

```bash
git pull origin control_team
colcon build --packages-select ropi_interface
source install/setup.bash
```

subscriber 실행:

```bash
uv run python test/integration/pinky_status_subscriber.py --ros-args -p pinky_id:=pinky2
```

기대 로그:

```text
IF-COM-005 status received: id=pinky2, state=IDLE, task=-, charging=NOT_CHARGING, docked=False, battery=0.0%/6.66V, pose=(..., ..., ...deg), fail=-
```

## 상태 변화만 빠르게 테스트

주행 명령 없이 상태 변화만 확인할 수 있다.

Pinky 터미널 2:

```bash
ros2 topic pub /transport/amr_status std_msgs/msg/String "{data: MOVING}" -1
```

기대:

```text
state=EXECUTING
```

정지 상태:

```bash
ros2 topic pub /transport/amr_status std_msgs/msg/String "{data: ARRIVED}" -1
```

기대:

```text
state=IDLE
```

## 시나리오 launch도 같이 실행해야 하나?

status만 확인할 때는 실행하지 않아도 된다.

운반, 순찰, 안내 업무 자체를 테스트할 때는 `pinky_nav.launch.py`를 먼저 켠 뒤 해당 시나리오 launch를 추가로 실행한다.

### 운반

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky2
```

다른 터미널:

```bash
ros2 launch ropi_delivery ropi_delivery.launch.py robot_id:=pinky2
```

### 순찰

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky3
```

다른 터미널:

```bash
ros2 launch ropi_patrol patrol.launch.py robot_id:=pinky3
```

### 안내

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py robot_id:=pinky1
```

다른 터미널:

```bash
ros2 launch ropi_guide guide.launch.py robot_id:=pinky1
```

## 문제 확인

패키지가 안 보일 때:

```bash
ros2 pkg list | grep ropi_mobile_status_test
```

status topic이 없을 때:

```bash
ros2 topic list | grep /ropi/robots
```

배터리 값이 0일 때:

```bash
ros2 topic info /battery/voltage
ros2 topic echo /battery/voltage --once
```

PC에서 Pinky topic이 안 보일 때:

```bash
echo $ROS_DOMAIN_ID
```

Pinky와 PC의 `ROS_DOMAIN_ID`가 같아야 한다.
