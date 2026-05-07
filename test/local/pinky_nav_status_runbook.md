# Pinky Status Direct Runbook

이 문서는 `pinky_nav.launch.py`를 쓰지 않고 `ropi_mobile_status_test`의 status publisher만 직접 실행해서 IF-COM-005 Pinky status를 확인하는 절차다.

## 결론

- status 테스트만 할 때는 `pinky_nav.launch.py`가 필요 없다.
- Pinky에서 `pinky_status_runtime_publisher.py`를 직접 실행한다.
- PC에서는 `test/integration/pinky_status_subscriber.py`로 받는다.
- 순찰, 운반, 안내 시나리오는 status가 잘 나오는지 확인한 뒤 별도 터미널에서 실행하면 된다.

## 역할 구분

| 구성 | 역할 | 이번 테스트에서 |
| --- | --- | --- |
| `ropi_mobile_status_test pinky_status_runtime_publisher.py` | `/ropi/robots/<pinky_id>/status` 발행 | 직접 실행 |
| `test/integration/pinky_status_subscriber.py` | typed status 구독 | PC에서 실행 |
| `test/integration/pinky_status_comm_subscriber.py` | JSON status 구독 | 이번 typed status 테스트에는 사용하지 않음 |
| `pinky_nav.launch.py` | navigation bringup | 이번 직접 실행 테스트에는 사용하지 않음 |

## Pinky 터미널 1: 빌드

Pinky가 `device` workspace를 쓰는 경우:

```bash
cd ~/Project/roscamp-repo-3/device
source /opt/ros/jazzy/setup.bash

colcon build --packages-up-to ropi_interface ropi_mobile_status_test
source install/setup.bash
```

만약 Pinky에서 repo root workspace를 쓰는 경우:

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash

colcon build --packages-up-to ropi_interface ropi_mobile_status_test
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

## Pinky 터미널 1: status publisher 직접 실행

순찰 Pinky가 `pinky3`이면:

```bash
ros2 run ropi_mobile_status_test pinky_status_runtime_publisher.py --ros-args -p pinky_id:=pinky3 -p odom_topic:=/odom -p state_topic:=/transport/amr_status -p battery_voltage_topic:=/battery/voltage -p infer_charging_from_pose:=true -p dock_x_min:=0.0 -p dock_x_max:=0.15 -p dock_y_min:=0.4 -p dock_y_max:=1.0
```

운반 Pinky가 `pinky2`이면:

```bash
ros2 run ropi_mobile_status_test pinky_status_runtime_publisher.py --ros-args -p pinky_id:=pinky2 -p odom_topic:=/odom -p state_topic:=/transport/amr_status -p battery_voltage_topic:=/battery/voltage
```

안내 Pinky가 `pinky1`이면:

```bash
ros2 run ropi_mobile_status_test pinky_status_runtime_publisher.py --ros-args -p pinky_id:=pinky1 -p odom_topic:=/odom -p state_topic:=/transport/amr_status -p battery_voltage_topic:=/battery/voltage
```

주의: 메신저에서 복사한 명령에 보이지 않는 특수 공백이 섞이면 `UnknownROSArgsError`가 날 수 있다. 그때는 위 명령을 한 줄로 직접 다시 입력한다.

기대 로그:

```text
[pinky_status_runtime_publisher]: Using Odometry source topic: /odom
[pinky_status_runtime_publisher]: Using battery voltage source topic: /battery/voltage
[pinky_status_runtime_publisher]: Using state source topic: /transport/amr_status
[pinky_status_runtime_publisher]: Publishing IF-COM-005 Pinky status on /ropi/robots/pinky3/status
```

충전소 사각형 판정은 현재 dock 구역 기준이다.

```text
x: 0.0 ~ 0.15
y: 0.4 ~ 1.0
```

이 구역 안에 pose가 들어오면 `docked=True`, `charging=CHARGING`으로 추론한다. 밖으로 나가면 `docked=False`, `charging=NOT_CHARGING`으로 돌아간다.

## Pinky 터미널 2: Pinky 내부 확인

새 터미널에서 같은 workspace를 source한다.

```bash
cd ~/Project/roscamp-repo-3/device
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

topic 확인:

```bash
ros2 topic list -t | grep -E "odom|battery|amr|ropi/robots"
```

status 1회 확인:

```bash
ros2 topic echo /ropi/robots/pinky3/status --once
```

소스 topic 확인:

```bash
ros2 topic echo /battery/voltage --once
ros2 topic echo /odom --once
```

task topic 연결 확인:

```bash
ros2 topic info /ropi/robots/pinky3/active_task_id -v
ros2 topic echo /ropi/robots/pinky3/active_task_id
```

순찰 goal이 정상 수신되면 `active_task_id`에 task id가 발행된다. 순찰이 바로 실패하면 빈 문자열이 곧바로 발행되어 PC subscriber에서 놓칠 수 있다.

## PC 터미널: subscriber 확인

PC에서:

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

필요하면 PC에서 interface를 다시 빌드한다.

```bash
colcon build --packages-select ropi_interface
source install/setup.bash
```

순찰 Pinky `pinky3` 구독:

```bash
uv run python test/integration/pinky_status_subscriber.py --ros-args -p pinky_id:=pinky3
```

운반 Pinky `pinky2` 구독:

```bash
uv run python test/integration/pinky_status_subscriber.py --ros-args -p pinky_id:=pinky2
```

기대 로그:

```text
IF-COM-005 status received: id=pinky3, state=IDLE, task=-, charging=NOT_CHARGING, docked=False, battery=0.0%/6.66V, pose=(..., ..., ...deg), fail=-
```

간단히 `ros2 topic echo`로도 확인할 수 있다.

```bash
ros2 topic echo /ropi/robots/pinky3/status --once
```

## 상태 변화만 빠르게 테스트

주행 명령 없이 state mapping만 확인할 수 있다.

Pinky 터미널 2:

```bash
ros2 topic pub /transport/amr_status std_msgs/msg/String "{data: MOVING}" -1
```

PC subscriber 기대:

```text
state=EXECUTING
```

정지 상태:

```bash
ros2 topic pub /transport/amr_status std_msgs/msg/String "{data: ARRIVED}" -1
```

PC subscriber 기대:

```text
state=IDLE
```

## 시나리오도 같이 실행해야 하나?

status 자체 테스트에는 필요 없다.

실제 순찰, 운반, 안내 중에 status가 바뀌는지 확인하려면 다음처럼 실행한다.

1. Pinky 터미널 1에서 status publisher 직접 실행
2. PC 터미널에서 subscriber 실행
3. Pinky의 다른 터미널에서 시나리오 launch 실행

순찰 예시:

```bash
ros2 run ropi_mobile_status_test pinky_status_runtime_publisher.py --ros-args -p pinky_id:=pinky3 -p odom_topic:=/odom -p state_topic:=/transport/amr_status -p battery_voltage_topic:=/battery/voltage -p infer_charging_from_pose:=true -p dock_x_min:=0.0 -p dock_x_max:=0.15 -p dock_y_min:=0.4 -p dock_y_max:=1.0
```

다른 Pinky 터미널:

```bash
ros2 launch ropi_patrol patrol.launch.py robot_id:=pinky3
```

운반 예시:

```bash
ros2 run ropi_mobile_status_test pinky_status_runtime_publisher.py --ros-args -p pinky_id:=pinky2 -p odom_topic:=/odom -p state_topic:=/transport/amr_status -p battery_voltage_topic:=/battery/voltage
```

다른 Pinky 터미널:

```bash
ros2 launch ropi_delivery ropi_delivery.launch.py robot_id:=pinky2
```

## 문제 확인

`ros2: command not found`:

```bash
source /opt/ros/jazzy/setup.bash
```

패키지가 안 보일 때:

```bash
ros2 pkg list | grep ropi_mobile_status_test
ros2 pkg executables ropi_mobile_status_test
```

status topic이 없을 때:

```bash
ros2 topic list -t | grep /ropi/robots
```

PC에서 topic 이름은 보이는데 type을 못 읽을 때:

```bash
cd ~/roscamp-repo-3
source /opt/ros/jazzy/setup.bash
colcon build --packages-select ropi_interface
source install/setup.bash
ros2 daemon stop
ros2 daemon start
```

PC subscriber가 계속 `No IF-COM-005 Pinky status snapshot received yet`만 출력할 때:

```bash
echo $ROS_DOMAIN_ID
ros2 topic list -t | grep /ropi/robots
```

Pinky와 PC의 `ROS_DOMAIN_ID`가 같아야 한다.

배터리 값이 0이거나 안 바뀔 때:

```bash
ros2 topic info /battery/voltage
ros2 topic echo /battery/voltage --once
```

`/battery/voltage`가 살아 있으면 voltage는 status에 들어온다. battery percent는 별도 percent topic이나 voltage-to-percent 변환 코드가 없으면 기본값으로 남을 수 있다.
