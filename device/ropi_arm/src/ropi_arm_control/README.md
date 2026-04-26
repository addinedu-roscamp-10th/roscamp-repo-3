# ropi_arm_control

`jetcobot1`, `jetcobot2`에서 공통으로 사용하는 arm action server 패키지다. 두 로봇은 코드가 거의 같으므로 패키지를 둘로 복사하지 않고, 하나의 패키지를 robot별 parameter로 실행한다.

## 로봇 매핑

| 로봇 | arm id | 관제 action 이름 |
| --- | --- | --- |
| `jetcobot1` | `arm1` | `/ropi/arm/arm1/execute_manipulation` |
| `jetcobot2` | `arm2` | `/ropi/arm/arm2/execute_manipulation` |

관제 서버는 `arm_id`를 기준으로 action 이름을 만든다. `arm1`, `arm2` 값을 임의로 바꾸면 배송 orchestration이 깨진다.

## 주요 파일

| 파일 | 용도 |
| --- | --- |
| `ropi_arm_control/arm1_node.py` | JetCobot arm action server |
| `launch/arm_control.launch.py` | robot별 config를 읽어 노드 실행 |
| `config/jetcobot1/arm.yaml` | jetcobot1 실행 parameter |
| `config/jetcobot2/arm.yaml` | jetcobot2 실행 parameter |

## 실행 전 준비

```bash
source /opt/ros/jazzy/setup.bash
source ~/roscamp-repo-3/device/install/setup.bash
```

각 로봇에서는 자기 robot id로 실행한다.

```bash
ros2 launch ropi_arm_control arm_control.launch.py robot_id:=jetcobot1
ros2 launch ropi_arm_control arm_control.launch.py robot_id:=jetcobot2
```

노드를 직접 실행할 수도 있다.

```bash
ros2 run ropi_arm_control jet_arm_node --ros-args -p arm_id:=arm1 -p port:=/dev/ttyJETCOBOT
ros2 run ropi_arm_control jet_arm_node --ros-args -p arm_id:=arm2 -p port:=/dev/ttyJETCOBOT
```

## 현재 parameter

| 파라미터 | 기본값 | 의미 |
| --- | --- | --- |
| `arm_id` | `arm1` | 관제 action 이름에 들어가는 arm 식별자 |
| `port` | `/dev/ttyJETCOBOT` | MyCobot serial port |
| `baud` | `1000000` | serial baudrate |

## 현재 동작 한계

- 현재 motion sequence는 테스트용 단일 동작에 가깝다.
- `transfer_direction`, `item_id`, `robot_slot_id`는 action goal로 받지만 실제 동작 분기에는 아직 충분히 반영되지 않았다.
- `quantity`도 현재는 1개 처리 기준으로 동작한다.
- `pymycobot` 경로가 로봇 환경에 강하게 묶여 있으므로, JetCobot 실제 환경에서 먼저 검증해야 한다.

## 다음 리팩터링 방향

다음 단계에서는 motion sequence를 코드 안 리스트로 고정하지 말고 config나 별도 motion module로 분리하는 것이 좋다.

```text
ropi_arm_control/
  config/jetcobot1/arm.yaml
  config/jetcobot2/arm.yaml
  config/motions/load.yaml
  config/motions/unload.yaml
```

최소한 아래 분기는 명확히 해야 한다.

| 입력 | 의미 |
| --- | --- |
| `transfer_direction=TO_ROBOT` | 선반/테이블에서 Pinky로 적재 |
| `transfer_direction=FROM_ROBOT` | Pinky에서 목적지로 하역 |
| `item_id` | 집을 물건 종류 |
| `robot_slot_id` | Pinky 적재 위치 |
| `quantity` | 처리 수량 |

## 팀 작업 규칙

- `arm_id`는 관제 계약이므로 임의 변경하지 않는다.
- jetcobot2 코드를 별도 패키지로 복사하지 않는다.
- 로봇별 차이는 `config/jetcobot1`, `config/jetcobot2`에 둔다.
- action 정의는 `ropi_common/src/ropi_interface/action/ArmManipulation.action`에서만 관리한다.
- serial port가 다르면 코드가 아니라 `arm.yaml`의 `port` 값을 바꾼다.
