# ropi_nav_config

Pinky Pro 제조사 navigation 패키지를 우리 프로젝트 설정으로 감싸는 wrapper 패키지다. 제조사 코드인 `~/pinky_pro`를 레포 안으로 복사하지 않고, 이 패키지가 map과 Nav2 parameter 경로만 넘긴다.

## 왜 이 패키지가 필요한가

- Pinky 로봇에는 이미 `~/pinky_pro`가 세팅되어 있다.
- 제조사 코드 전체를 우리 레포에서 관리하면 충돌과 업데이트 문제가 커진다.
- 우리 프로젝트에서 실제로 바꿔야 하는 값은 대부분 map, `nav2_params.yaml`, `mapper_params.yaml`이다.
- 그래서 제조사 `pinky_navigation` launch는 그대로 쓰고, 우리 설정 파일만 이 레포에서 형상관리한다.

## 관리하는 파일

```text
ropi_nav_config/
  launch/pinky_nav.launch.py
  config/nav2_params.yaml
  config/mapper_params.yaml
  maps/map_0504.yaml
  maps/map_0504.pgm
  maps/map_test12_0506.yaml
  maps/map_test12_0506.pgm
```

기본 launch map은 `map_0504`다. 운반팀은 별도 기준 맵인 `map_test12_0506`을 사용하므로 Pinky2 운반 실험/운영 시 launch argument로 해당 map을 명시한다. 로봇별 폴더를 만들지 않고 map 파일을 공통 `maps/` 아래에서 관리한다.

## 실행 전 source 순서

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/setup.bash
source ~/roscamp-repo-3/device/install/setup.bash
```

## 실행 방법

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py
```

필요하면 직접 파일 경로를 지정할 수 있다.

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py \
  params_file:=/absolute/path/to/nav2_params.yaml \
  map:=/absolute/path/to/map_0504.yaml
```

운반팀 맵으로 Pinky2를 실행할 때:

```bash
ros2 launch ropi_nav_config pinky_nav.launch.py \
  robot_id:=pinky2 \
  map:=/absolute/path/to/map_test12_0506.yaml
```

## 내부 동작

`pinky_nav.launch.py`는 `~/pinky_pro`에서 제공하는 아래 launch를 include한다.

```text
pinky_navigation/launch/bringup_launch.xml
```

그리고 다음 값을 넘긴다.

| launch argument | 기본 경로 |
| --- | --- |
| `params_file` | `ropi_nav_config/config/nav2_params.yaml` |
| `map` | `ropi_nav_config/maps/map_0504.yaml` |
| `use_sim_time` | `False` |

## 팀별 수정 규칙

- map과 navigation parameter는 공통 패키지에서 관리하고, 시나리오별 차이는 launch argument로 선택한다. 운반은 `map_test12_0506`, 순찰/안내 기본은 `map_0504`를 사용한다.
- 안내, 운반, 순찰 시나리오별 설정은 각 시나리오 패키지의 `config/`에서 관리한다.
- 제조사 `~/pinky_pro/src/pinky_pro/pinky_navigation` 안의 파일을 직접 수정해서 문제를 해결하지 않는다.
- 새 map을 만들면 map `.yaml` 안의 `image` 경로가 같은 폴더의 실제 `.pgm` 파일을 가리키는지 확인한다.
