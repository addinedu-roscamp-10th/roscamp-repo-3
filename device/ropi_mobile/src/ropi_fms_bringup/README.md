# ropi_fms_bringup 운영 기록

이 패키지는 FMS 교통정리 실험을 위해 실제 Pinky 로봇에서 `map_0504` 기반 Nav2 주행을 띄우는 bringup 패키지다.

현재 기준은 다음과 같다.

- ROS_DOMAIN_ID: `99`
- 테스트 로봇:
  - `pinky1`: `192.168.0.7`
  - `pinky3`: `192.168.0.44`
- 공통 맵: `ropi_nav_config/maps/map_0504.yaml`
- 주행 방식: 단순 `DRIVE` 태스크 중심 FMS 실험
- 실제 로봇 드라이버: `pinky_bringup` legacy Dynamixel driver

## 실행 명령

로봇에서 실행한다.

```bash
cd ~/roscamp-repo-3/device
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
colcon build --symlink-install --packages-up-to ropi_fms_bringup
source install/setup.bash

export ROS_DOMAIN_ID=99
export ROS_LOCALHOST_ONLY=0

ros2 launch ropi_fms_bringup pinky_fms.launch.py robot_id:=pinky1
```

`pinky3`에서는 `robot_id:=pinky3`로 실행한다.

## 2026-05-26 pinky1 bringup 장애 기록

### 증상

`pinky1`에서 `ropi_fms_bringup pinky_fms.launch.py`를 실행했을 때 다음 문제가 같이 발생했다.

```text
sllidar_node process has died, exit code 255
Error, unexpected error, code: 80008004
```

```text
controller_server: Couldn't load critics!
Original error: No critics defined for FollowPath
```

```text
ros2_control_node: no ros2_control tag
```

또한 로그의 노드명이 `pinky1.pinky1.controller_server`처럼 보이고, costmap이 `/pinky1/pinky1/map`을 구독하는 namespace 중첩도 있었다.

### 원인

원인은 한 가지가 아니라 실제 로봇 환경과 launch 가정이 여러 군데에서 어긋난 것이었다.

1. `pinky_navigation/bringup_launch.xml`이 namespace를 한 번 push하고, 그 안에서 포함되는 `localization_launch.xml`, `navigation_launch.xml`도 namespace를 다시 push했다.
   그래서 `/pinky1/pinky1/...`처럼 namespace가 중첩됐다.

2. 기존 FMS launch는 `ros2_control_node`와 `controller_manager` 기반을 가정했다.
   하지만 현재 실제 Pinky 이미지의 `pinky_pro`는 `ros2_control` 기반이 아니라 `pinky_bringup` 파이썬 Dynamixel driver 기반이다.
   이 로봇의 URDF에는 `ros2_control` 태그가 없으므로 `ros2_control_node`는 정상 기동할 수 없다.

3. `pinky_controllers_fms.yaml`은 `/**:` wildcard root를 가진 파일인데, 여기에 `RewrittenYaml(root_key=robot_id)`를 적용하면 `/pinky1//**/`처럼 잘못된 YAML path가 만들어질 수 있다.

4. 실제 `pinky1`의 LiDAR 포트는 `/dev/ttyS0`였다.
   `/dev/ttyAMA0`로 실행하면 `sllidar_node`가 `80008004` 에러로 죽었다.

5. Nav2 params 파일은 top-level node key 형태다.
   그대로 `/pinky1/controller_server` 같은 namespaced node에 넘기면 `controller_plugins`, `FollowPath.critics` 등이 적용되지 않는다.
   그 결과 `No critics defined for FollowPath`가 발생했다.

6. `RewrittenYaml`을 vendor XML include 사이에서 재사용하거나, 바깥 launch argument 이름을 vendor와 같은 `params_file`로 두면 두 번째 include에서 이미 감긴 임시 YAML을 다시 감싸 `pinky1.pinky1.controller_server` 형태가 된다.

7. 현재 `pinky_bringup` driver는 `geometry_msgs/msg/Twist` 기반 `cmd_vel`을 구독한다.
   따라서 Nav2 쪽 `enable_stamped_cmd_vel`은 `false`여야 한다.

### 해결 내용

`pinky_fms.launch.py`를 실제 로봇 이미지에 맞게 바꿨다.

- `ros2_control_node`, controller spawner 제거
- `pinky_bringup`의 `bringup`, `battery_publisher`를 robot namespace 아래에서 실행
- LiDAR 기본 포트를 `/dev/ttyS0`로 변경
- vendor `bringup_launch.xml` 대신 `localization_launch.xml`, `navigation_launch.xml`을 직접 include
- 바깥에서 `PushROSNamespace(robot_id)`를 한 번만 적용하고, vendor XML에는 `namespace: ""` 전달
- Nav2 params는 `nav2_params_file` 인자로 받고, vendor XML의 child arg `params_file`과 이름 충돌을 피함
- localization/navigation include마다 별도 `RewrittenYaml(root_key=robot_id)`를 사용
- `nav2_params_fms.yaml`의 `enable_stamped_cmd_vel`을 모두 `false`로 변경

관련 커밋:

```text
81b6f38 fix: 핑키 FMS bringup 실제 로봇 환경 반영
```

## 검증 결과

로컬에서 확인한 항목:

```bash
uv run --with ruff ruff check device/ropi_mobile/src/ropi_fms_bringup

cd device
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
colcon build --symlink-install --packages-up-to ropi_fms_bringup
source install/setup.bash
colcon test --packages-select ropi_fms_bringup --event-handlers console_direct+
```

결과:

```text
11 passed
```

`pinky1`에서도 동일하게 build/test를 통과했다.

실제 launch에서 확인한 정상 로그:

```text
SLLidar health status : OK.
Pinky Bringup with Dynamixel has been started successfully.
Controller Server has FollowPath controllers available.
lifecycle_manager_navigation: Managed nodes are active
```

실행 중 ROS 그래프 확인:

```bash
ros2 node list | grep '^/pinky1/' | sort
ros2 param get /pinky1/controller_server FollowPath.critics
ros2 param get /pinky1/velocity_smoother enable_stamped_cmd_vel
ros2 topic info -v /pinky1/scan
ros2 topic info -v /pinky1/cmd_vel
```

확인된 값:

- `/pinky1/controller_server`의 `FollowPath.critics`가 정상 로드됨
- `/pinky1/velocity_smoother enable_stamped_cmd_vel`은 `False`
- `/pinky1/scan`은 `sllidar_node`가 publish하고 `amcl`이 subscribe
- `/pinky1/cmd_vel` 타입은 `geometry_msgs/msg/Twist`
- 주요 노드는 `/pinky1/...` namespace 아래에 존재

## 재발 방지 체크리스트

FMS bringup이 실패하면 아래를 먼저 확인한다.

1. namespace가 두 번 감겼는지 확인한다.

```bash
ros2 node list | grep pinky1
ros2 topic list | grep '/pinky1/pinky1'
```

`/pinky1/pinky1/...`이 보이면 vendor launch include 구조나 `RewrittenYaml` 재사용을 의심한다.

2. LiDAR 포트를 확인한다.

```bash
ls -l /dev/ttyS0 /dev/ttyAMA0 2>/dev/null
```

현재 `pinky1` 기준 기본값은 `/dev/ttyS0`다.
다른 로봇에서 포트가 다르면 launch 인자로 override한다.

```bash
ros2 launch ropi_fms_bringup pinky_fms.launch.py \
  robot_id:=pinky3 \
  lidar_serial_port:=/dev/ttyS0
```

3. Nav2 params가 실제 namespaced node에 적용됐는지 확인한다.

```bash
ros2 param get /pinky1/controller_server FollowPath.critics
```

`No critics defined for FollowPath`가 나오면 `nav2_params_file` rewrite 결과가 `/pinky1/controller_server`에 맞게 생성됐는지 확인한다.

4. `cmd_vel` 메시지 타입을 확인한다.

```bash
ros2 topic info -v /pinky1/cmd_vel
```

현재 실제 Pinky driver는 `geometry_msgs/msg/Twist`를 사용한다.
`TwistStamped`로 바뀌면 `pinky_bringup`과 맞지 않는다.

5. `timeout`이나 Ctrl-C로 launch를 끊은 뒤 보이는 `KeyboardInterrupt`, `exit code -2`, 일부 `exit code 1`은 종료 과정에서 나올 수 있다.
초기 bringup 실패로 판단할 때는 그 이전에 `SLLidar health OK`, `Pinky Bringup ... started successfully`, `Managed nodes are active`가 찍혔는지를 먼저 본다.

