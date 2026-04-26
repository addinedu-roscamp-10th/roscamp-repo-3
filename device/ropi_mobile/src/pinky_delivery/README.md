# pinky_delivery

`pinky2` 운반 시나리오에서 Pinky 이동을 담당하는 패키지다. 현재 관제 연동에 성공한 실행 파일은 `mobile_controller_test.py`이며, 이 파일이 관제 서버의 navigation action 요청을 받아 Nav2로 목적지 이동을 수행한다.

## 현재 기준 실행 파일

| 파일 | 상태 |
| --- | --- |
| `pinky_delivery/mobile_controller_test.py` | 현재 관제 연동 성공 경로 |
| `pinky_delivery/transport_control_node.py` | 이전/실험용 코드, 정식 운용 경로로 확정하지 않음 |

`transport_control_node.py`를 삭제하지 않은 이유는 팀 구현 맥락과 테스트 코드를 보존하기 위해서다. 다만 관제에서 실제로 호출하는 Pinky action server는 `mobile_controller_test.py` 기준으로 정리한다.

## 관제와의 계약

관제 서버는 Pinky 이동 요청을 아래 action 이름으로 보낸다.

```text
/ropi/control/pinky2/navigate_to_goal
```

이 이름은 서버 코드와 맞물려 있으므로 임의로 바꾸면 안 된다. 나중에 `pinky1`, `pinky3`도 같은 action server 구조를 쓰게 되면 아래 규칙을 따른다.

```text
/ropi/control/<pinky_id>/navigate_to_goal
```

## 현재 발행하는 토픽

| 토픽 | 타입 | 용도 |
| --- | --- | --- |
| `/transport/amr_status` | `std_msgs/msg/String` | `IDLE`, `MOVING`, `ARRIVED`, `FAILED` 상태 발행 |
| `/transport/current_goal` | `geometry_msgs/msg/PoseStamped` | 현재 이동 목표 발행 |

## 실행 전 준비

Pinky 제조사 navigation이 먼저 떠 있어야 한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/ropi_common/install/setup.bash
source ~/roscamp-repo-3/device/ropi_mobile/install/setup.bash

ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky2
```

다른 터미널에서 action server를 실행한다. 기본 실행은 launch를 사용한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/ropi_common/install/setup.bash
source ~/roscamp-repo-3/device/ropi_mobile/install/setup.bash

ros2 launch pinky_delivery pinky_delivery.launch.py robot_id:=pinky2
```

노드만 직접 실행할 수도 있다. 이 경우 config가 자동으로 들어가지 않으므로 필요한 parameter를 직접 넘겨야 한다.

```bash
ros2 run pinky_delivery mobile_controller_test --ros-args \
  -p robot_id:=pinky2 \
  -p action_name:=/ropi/control/pinky2/navigate_to_goal

ros2 run pinky_delivery pinky_navigation_action_server
```

## 현재 config

운영 값은 `config/pinky2/delivery.yaml`에서 관리한다.

| 값 | 현재 위치 |
| --- | --- |
| `pinky2` | `robot_id` |
| `/ropi/control/pinky2/navigate_to_goal` | `action_name` |
| `/transport/amr_status` | `status_topic` |
| `/transport/current_goal` | `current_goal_topic` |
| `0.5` | `state_publish_period_sec` |

새 로봇 ID나 action 이름이 필요하면 코드가 아니라 config와 launch argument를 수정한다.

## 팀 작업 규칙

- 관제 연동 테스트는 `mobile_controller_test.py` 기준으로 진행한다.
- action 이름을 바꿔야 하면 관제 팀과 먼저 맞춘다.
- `NavigateToGoal.action` 필드는 `ropi_common/src/ropi_interface`에서 관리하므로 이 패키지 안에서 임의로 복사하거나 수정하지 않는다.
- Nav2 map/parameter는 `ropi_pinky_config/config/pinky2`, `ropi_pinky_config/maps/pinky2`에서 관리한다.
- 배송 로직이 arm 동작까지 포함되어야 하면 Pinky 코드에서 직접 arm을 호출하기보다 관제 서버의 orchestration 흐름과 맞춰야 한다.
