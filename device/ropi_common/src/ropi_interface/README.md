# ropi_interface

관제 서버와 모든 로봇이 공유하는 ROS interface 패키지다. 이 패키지의 action 정의가 바뀌면 서버, Pinky, JetCobot을 모두 다시 빌드해야 한다.

## 이 패키지가 관리하는 것

| 파일 | 용도 |
| --- | --- |
| `msg/PinkyStatus.msg` | IF-COM-005 Pinky 운영 telemetry 상태 topic |
| `msg/GuidePhaseSnapshot.msg` | IF-GUI-007 안내 runtime phase snapshot topic |
| `srv/GuideCommand.srv` | IF-GUI-004 안내 session control service |
| `action/NavigateToGoal.action` | 관제 서버가 Pinky에게 목적지 이동을 요청할 때 사용 |
| `action/ArmManipulation.action` | 관제 서버가 JetCobot에게 적재/하역 동작을 요청할 때 사용 |
| `action/ExecutePatrolPath.action` | 관제 서버가 Pinky에게 순찰 경로 실행을 요청할 때 사용 |

## 이 패키지가 관리하지 않는 것

- Pinky 제조사 전용 service는 여기서 관리하지 않는다.
- `pinky_interfaces`, LED, LCD, lamp, emotion 같은 제조사 기능은 `~/pinky_pro` 쪽 책임이다.
- 특정 시나리오 팀만 쓰는 임시 메시지를 이 패키지에 바로 추가하지 않는다.

## 관제 연동 action 이름

서버와 로봇 코드는 아래 이름 규칙을 기준으로 연결된다.

```text
/ropi/control/<pinky_id>/navigate_to_goal
/ropi/control/<pinky_id>/guide_command
/ropi/control/<pinky_id>/guide_phase_snapshot
/ropi/arm/<arm_id>/execute_manipulation
```

예시는 다음과 같다.

```text
/ropi/control/pinky2/navigate_to_goal
/ropi/control/pinky1/guide_command
/ropi/control/pinky1/guide_phase_snapshot
/ropi/arm/arm1/execute_manipulation
/ropi/arm/arm2/execute_manipulation
```

## 안내 runtime interface 기준

- `GuideCommand.srv`는 관제가 Pinky에게 보내는 `IF-GUI-004` 명령이다.
- 허용 command는 `WAIT_TARGET_TRACKING`, `START_GUIDANCE`만 둔다.
- `START_GUIDANCE`는 `target_track_id`를 `int32`로 전달하고, 목적지는 `destination_id`와 `destination_pose`로 전달한다.
- 안내 시작 이후 `WAIT_REIDENTIFY`, 재개, 종료 판단은 Pinky/AI runtime 책임이다.
- Pinky는 `GuidePhaseSnapshot.msg`로 `IF-GUI-007` phase를 계속 발행한다.
- `GuideTrackingUpdate.msg` 기반의 IF-GUI-005/006 tracking bridge는 retired 되었으므로 이 패키지에서 export하지 않는다.

## 빌드 방법

```bash
cd ~/roscamp-repo-3/device/ropi_common
colcon build --packages-select ropi_interface
source install/setup.bash
```

다른 워크스페이스를 빌드하기 전에 반드시 이 워크스페이스를 먼저 source해야 한다.

## 수정 규칙

- action 필드를 바꾸기 전에 관제 팀과 로봇 팀이 같이 합의해야 한다.
- 기존 필드 이름을 바꾸면 서버 action client와 로봇 action server가 동시에 깨진다.
- 새 action이 필요한 경우, 먼저 서버에서 어떤 command로 호출할지 정하고 추가한다.
- 시나리오별 내부 데이터는 가능하면 각 패키지의 config/parameter로 처리하고, 공통 interface로 올리는 것은 마지막 선택지로 둔다.
