from __future__ import annotations

from dataclasses import dataclass, replace


TASK_TYPE_LABELS = {
    "GUIDE": "안내",
    "DELIVERY": "운반",
    "PATROL": "순찰",
}

STATUS_LABELS = {
    "RUNNING": "진행 중",
    "WAITING_DISPATCH": "배정 대기",
    "COMPLETED": "완료",
    "FAILED": "실패",
    "CANCEL_REQUESTED": "취소 요청",
}

PHASE_LABELS = {
    "WAITING_DISPATCH": "작업 배정 대기",
    "MOVE_TO_PICKUP": "픽업지 이동",
    "DELIVERY_PICKUP": "물품 적재",
    "DELIVERY_DESTINATION": "목적지 이동",
    "HANDOVER_WAITING": "전달 대기",
    "RETURN_TO_DOCK": "복귀 중",
    "WAIT_TARGET_TRACKING": "안내 대상 확인",
    "READY_TO_START_GUIDANCE": "안내 시작 준비",
    "GUIDANCE_RUNNING": "안내 주행 중",
    "PATROL_RUNNING": "순찰 중",
    "WAIT_FALL_RESPONSE": "낙상 의심 확인",
    "TASK_COMPLETED": "작업 완료",
}

SEVERITY_LABELS = {
    "INFO": "정보",
    "WARNING": "주의",
    "ERROR": "오류",
    "CRITICAL": "긴급",
}

TASK_DEFAULTS = {
    "GUIDE": {
        "title": "방문객 안내",
        "robot": "ROPI 1",
        "destination": "303호",
        "phase": "GUIDANCE_RUNNING",
        "summary": "방문객을 303호까지 안내 중",
        "tone": "blue",
        "location": "복도1",
        "status": "안내 주행 중",
    },
    "DELIVERY": {
        "title": "의료키트 운반",
        "robot": "ROPI 2",
        "destination": "303호",
        "phase": "HANDOVER_WAITING",
        "summary": "목적지 도착 후 전달 대기",
        "tone": "green",
        "location": "303호",
        "status": "전달 대기",
    },
    "PATROL": {
        "title": "야간 순찰",
        "robot": "ROPI 3",
        "destination": "복도3",
        "phase": "PATROL_RUNNING",
        "summary": "복도3 순찰 구간 확인 중",
        "tone": "amber",
        "location": "복도3",
        "status": "순찰 중",
    },
}


@dataclass(frozen=True)
class DemoKpi:
    title: str
    value: str
    hint: str
    tone: str


@dataclass(frozen=True)
class DemoRobot:
    internal_id: str
    display_id: str
    mission: str
    task_name: str
    status: str
    location: str
    battery_percent: int
    task_id: str
    tone: str


@dataclass(frozen=True)
class DemoMapMarker:
    internal_id: str
    display_id: str
    x: float
    y: float
    yaw: float
    yaw_deg: float
    mission: str
    status: str
    tone: str


@dataclass(frozen=True)
class DemoTask:
    title: str
    task_id: str
    task_type: str
    robot_display_id: str
    phase: str
    phase_code: str
    destination: str
    tone: str
    status: str = "RUNNING"
    summary: str = ""
    created_at: str = "2026.05.12 14:32"
    updated_at: str = "2026.05.12 14:32"


@dataclass(frozen=True)
class DemoTimelineEvent:
    time_text: str
    occurred_at: str
    task_id: str
    title: str
    detail: str
    tone: str


@dataclass(frozen=True)
class DemoAlertLog:
    event_id: str
    severity: str
    event_type: str
    task_id: str
    robot_display_id: str
    title: str
    message: str
    occurred_at: str
    detail_rows: tuple[tuple[str, str], ...]
    tone: str


@dataclass(frozen=True)
class DemoSnapshot:
    status_chip: str
    last_updated: str
    kpis: tuple[DemoKpi, ...]
    robots: tuple[DemoRobot, ...]
    map_markers: tuple[DemoMapMarker, ...]
    tasks: tuple[DemoTask, ...]
    timeline: tuple[DemoTimelineEvent, ...]
    alerts: tuple[DemoAlertLog, ...]


def display_task_type(task_type: str) -> str:
    return TASK_TYPE_LABELS.get(task_type, task_type)


def display_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def display_phase(phase: str) -> str:
    return PHASE_LABELS.get(phase, phase)


def display_severity(severity: str) -> str:
    return SEVERITY_LABELS.get(severity, severity)


def build_admin_demo_snapshot() -> DemoSnapshot:
    tasks = (
        DemoTask(
            "방문객 안내",
            "#1031",
            "GUIDE",
            "ROPI 1",
            "안내 주행 중",
            "GUIDANCE_RUNNING",
            "303호",
            "blue",
            summary="방문객을 303호까지 안내 중",
        ),
        DemoTask(
            "의료키트 운반",
            "#1032",
            "DELIVERY",
            "ROPI 2",
            "전달 대기",
            "HANDOVER_WAITING",
            "303호",
            "green",
            summary="목적지 도착 후 전달 대기",
        ),
        DemoTask(
            "야간 순찰",
            "#1033",
            "PATROL",
            "ROPI 3",
            "낙상 의심 확인",
            "WAIT_FALL_RESPONSE",
            "복도3",
            "amber",
            summary="복도3 낙상 의심 상황 확인 필요",
        ),
    )
    timeline = (
        DemoTimelineEvent(
            "14:32",
            "2026.05.12 14:32",
            "1033",
            "ROPI 3 낙상 의심 감지",
            "복도3 evidence 저장",
            "amber",
        ),
        DemoTimelineEvent(
            "14:28",
            "2026.05.12 14:28",
            "1032",
            "ROPI 2 의료키트 목적지 도착",
            "303호 전달 대기",
            "green",
        ),
        DemoTimelineEvent(
            "14:21",
            "2026.05.12 14:21",
            "1031",
            "ROPI 1 안내 주행 시작",
            "복도1에서 303호로 이동",
            "blue",
        ),
    )
    alerts = (
        DemoAlertLog(
            "EV-1033",
            "WARNING",
            "순찰 낙상 의심",
            "#1033",
            "ROPI 3",
            "순찰 낙상 의심",
            "복도3에서 낙상 의심 이벤트를 확인 중입니다.",
            "2026.05.12 14:32",
            (
                ("작업 ID", "#1033"),
                ("담당 ROPI", "ROPI 3"),
                ("현재 단계", "낙상 의심 확인"),
                ("위치", "복도3"),
            ),
            "amber",
        ),
        DemoAlertLog(
            "EV-1032",
            "INFO",
            "운반 목적지 도착",
            "#1032",
            "ROPI 2",
            "운반 목적지 도착",
            "ROPI 2가 303호에 도착해 의료키트 전달을 대기 중입니다.",
            "2026.05.12 14:28",
            (
                ("작업 ID", "#1032"),
                ("담당 ROPI", "ROPI 2"),
                ("현재 단계", "전달 대기"),
                ("목적지", "303호"),
            ),
            "green",
        ),
    )
    return DemoSnapshot(
        status_chip="운영 정상",
        last_updated="2026.05.12 14:32",
        kpis=(
            DemoKpi("운영 중 ROPI", "3/3", "안내, 운반, 순찰 동시 운영", "teal"),
            DemoKpi("진행 작업", "3", "로봇 수행 중", "green"),
            DemoKpi("완료 작업", "8", "오늘 누적 처리", "blue"),
            DemoKpi("주의", "1", "순찰 낙상 의심 확인 필요", "amber"),
        ),
        robots=(
            DemoRobot(
                "pinky1",
                "ROPI 1",
                "방문객 안내",
                "안내",
                "안내 주행 중",
                "복도1",
                92,
                "#1031",
                "blue",
            ),
            DemoRobot(
                "pinky2",
                "ROPI 2",
                "의료키트 운반",
                "운반",
                "전달 대기",
                "303호",
                78,
                "#1032",
                "green",
            ),
            DemoRobot(
                "pinky3",
                "ROPI 3",
                "야간 순찰",
                "순찰",
                "낙상 의심 확인",
                "복도3",
                86,
                "#1033",
                "amber",
            ),
        ),
        map_markers=(
            DemoMapMarker(
                "pinky1",
                "ROPI 1",
                0.78,
                0.04,
                0.18,
                10.0,
                "안내",
                "주행 중",
                "blue",
            ),
            DemoMapMarker(
                "pinky2",
                "ROPI 2",
                0.40,
                -0.36,
                -0.48,
                -27.0,
                "운반",
                "전달 대기",
                "green",
            ),
            DemoMapMarker(
                "pinky3",
                "ROPI 3",
                1.36,
                -0.46,
                2.10,
                120.0,
                "순찰",
                "확인 필요",
                "amber",
            ),
        ),
        tasks=tasks,
        timeline=timeline,
        alerts=alerts,
    )


class DemoAdminStore:
    def __init__(self, snapshot: DemoSnapshot | None = None):
        self._snapshot = snapshot or build_admin_demo_snapshot()
        self._subscribers: list[callable] = []
        self._next_task_number = 1034
        self._next_event_number = 2001

    @property
    def snapshot(self) -> DemoSnapshot:
        return self._snapshot

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def create_task(self, task_type: str) -> DemoTask:
        task_type = task_type if task_type in TASK_DEFAULTS else "DELIVERY"
        defaults = TASK_DEFAULTS[task_type]
        task_id = f"#{self._next_task_number}"
        self._next_task_number += 1
        current_time = "2026.05.12 14:35"
        task = DemoTask(
            defaults["title"],
            task_id,
            task_type,
            defaults["robot"],
            display_phase(defaults["phase"]),
            defaults["phase"],
            defaults["destination"],
            defaults["tone"],
            "RUNNING",
            defaults["summary"],
            current_time,
            current_time,
        )
        alert = self._build_request_alert(task, current_time)
        event = DemoTimelineEvent(
            "14:35",
            current_time,
            task_id.lstrip("#"),
            f"{task.robot_display_id} {display_task_type(task.task_type)} 작업 생성",
            f"{task.destination} {task.phase}",
            task.tone,
        )
        robots = tuple(
            replace(
                robot,
                task_name=display_task_type(task.task_type),
                status=defaults["status"],
                location=defaults["location"],
                task_id=task.task_id,
                tone=task.tone,
            )
            if robot.display_id == task.robot_display_id
            else robot
            for robot in self._snapshot.robots
        )
        self._snapshot = replace(
            self._snapshot,
            last_updated=current_time,
            robots=robots,
            tasks=(task,) + self._snapshot.tasks,
            timeline=(event,) + self._snapshot.timeline,
            alerts=(alert,) + self._snapshot.alerts,
        )
        self._notify()
        return task

    def _build_request_alert(self, task: DemoTask, current_time: str) -> DemoAlertLog:
        event_id = f"EV-{self._next_event_number}"
        self._next_event_number += 1
        return DemoAlertLog(
            event_id,
            "INFO",
            "작업 생성",
            task.task_id,
            task.robot_display_id,
            "작업 생성",
            f"{task.robot_display_id}에 {display_task_type(task.task_type)} 작업을 배정했습니다.",
            current_time,
            (
                ("작업 ID", task.task_id),
                ("작업 유형", display_task_type(task.task_type)),
                ("담당 ROPI", task.robot_display_id),
                ("현재 단계", task.phase),
                ("목적지", task.destination),
            ),
            task.tone,
        )

    def _notify(self) -> None:
        for callback in tuple(self._subscribers):
            callback(self._snapshot)


def forbidden_internal_tokens() -> tuple[str, ...]:
    return ("pinky", "jetcobot", "arm1", "arm2")


def forbidden_raw_enum_tokens() -> tuple[str, ...]:
    return (
        "DELIVERY",
        "PATROL",
        "GUIDE",
        "RUNNING",
        "WAITING_DISPATCH",
        "COMPLETED",
        "FAILED",
        "WARNING",
        "ERROR",
        "CRITICAL",
    )


def visible_snapshot_texts(snapshot: DemoSnapshot) -> list[str]:
    texts: list[str] = [
        snapshot.status_chip,
        snapshot.last_updated,
    ]
    for kpi in snapshot.kpis:
        texts.extend((kpi.title, kpi.value, kpi.hint))
    for robot in snapshot.robots:
        texts.extend(
            (
                robot.display_id,
                robot.mission,
                robot.task_name,
                robot.status,
                robot.location,
                f"{robot.battery_percent}%",
                robot.task_id,
            )
        )
    for marker in snapshot.map_markers:
        texts.extend((marker.display_id, marker.mission, marker.status))
    for task in snapshot.tasks:
        texts.extend(
            (
                task.title,
                task.task_id,
                display_task_type(task.task_type),
                task.robot_display_id,
                display_status(task.status),
                task.phase,
                display_phase(task.phase_code),
                task.destination,
                task.summary,
            )
        )
    for event in snapshot.timeline:
        texts.extend((event.time_text, event.task_id, event.title, event.detail))
    for alert in snapshot.alerts:
        texts.extend(
            (
                alert.event_id,
                display_severity(alert.severity),
                alert.event_type,
                alert.task_id,
                alert.robot_display_id,
                alert.title,
                alert.message,
            )
        )
        for key, value in alert.detail_rows:
            texts.extend((key, value))
    return texts

