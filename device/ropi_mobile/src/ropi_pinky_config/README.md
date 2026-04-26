# ropi_pinky_config

Pinky Pro 제조사 navigation 패키지를 우리 프로젝트 설정으로 감싸는 wrapper 패키지다. 제조사 코드인 `~/pinky_pro`를 레포 안으로 복사하지 않고, 이 패키지가 map과 Nav2 parameter 경로만 넘긴다.

## 왜 이 패키지가 필요한가

- Pinky 로봇에는 이미 `~/pinky_pro`가 세팅되어 있다.
- 제조사 코드 전체를 우리 레포에서 관리하면 충돌과 업데이트 문제가 커진다.
- 우리 프로젝트에서 실제로 바꿔야 하는 값은 대부분 map, `nav2_params.yaml`, `mapper_params.yaml`이다.
- 그래서 제조사 `pinky_navigation` launch는 그대로 쓰고, 우리 설정 파일만 이 레포에서 형상관리한다.

## 관리하는 파일

```text
ropi_pinky_config/
  launch/pinky_nav.launch.py
  config/pinky1/nav2_params.yaml
  config/pinky1/mapper_params.yaml
  config/pinky2/nav2_params.yaml
  config/pinky2/mapper_params.yaml
  config/pinky3/nav2_params.yaml
  config/pinky3/mapper_params.yaml
  maps/pinky1/map.yaml
  maps/pinky1/pinklab.png
  maps/pinky2/map.yaml
  maps/pinky2/pinklab.png
  maps/pinky3/map.yaml
  maps/pinky3/pinklab.png
```

현재 `pinky1`, `pinky2`, `pinky3`의 map/parameter는 같은 기준 파일에서 복사된 초기값이다. 각 팀이 실제 로봇에서 튜닝한 값이 생기면 해당 로봇 폴더만 바꿔야 한다.

## 실행 전 source 순서

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/ropi_common/install/setup.bash
source ~/roscamp-repo-3/device/ropi_mobile/install/setup.bash
```

## 실행 방법

```bash
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky1
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky2
ros2 launch ropi_pinky_config pinky_nav.launch.py robot_id:=pinky3
```

필요하면 직접 파일 경로를 지정할 수 있다.

```bash
ros2 launch ropi_pinky_config pinky_nav.launch.py \
  robot_id:=pinky2 \
  params_file:=/absolute/path/to/nav2_params.yaml \
  map:=/absolute/path/to/map.yaml
```

## 내부 동작

`pinky_nav.launch.py`는 `~/pinky_pro`에서 제공하는 아래 launch를 include한다.

```text
pinky_navigation/launch/bringup_launch.xml
```

그리고 다음 값을 넘긴다.

| launch argument | 기본 경로 |
| --- | --- |
| `params_file` | `ropi_pinky_config/config/<robot_id>/nav2_params.yaml` |
| `map` | `ropi_pinky_config/maps/<robot_id>/map.yaml` |
| `use_sim_time` | `False` |

## 팀별 수정 규칙

- 안내 팀은 `pinky1` 폴더만 수정한다.
- 운반 팀은 `pinky2` 폴더만 수정한다.
- 순찰 팀은 `pinky3` 폴더만 수정한다.
- 제조사 `~/pinky_pro/src/pinky_pro/pinky_navigation` 안의 파일을 직접 수정해서 문제를 해결하지 않는다.
- 새 map을 만들면 `map.yaml` 안의 image 경로가 실제 이미지 파일을 가리키는지 확인한다.
