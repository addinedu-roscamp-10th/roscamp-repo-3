from dataclasses import dataclass


PROGRESS_FILL_WIDTHS = [90, 170, 260, 420, 520]
TERMINAL_TASK_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}
PRE_DRIVING_PHASES = {
    "WAIT_GUIDE_START_CONFIRM",
    "WAIT_TARGET_TRACKING",
    "READY_TO_START_GUIDANCE",
}
POST_START_GUIDE_PHASES = {
    "GUIDANCE_RUNNING",
    "WAIT_REIDENTIFY",
    "GUIDANCE_FINISHED",
    "GUIDANCE_CANCELLED",
    "GUIDANCE_FAILED",
}


@dataclass(frozen=True)
class GuideProgressViewState:
    robot_state_label: str
    status_message: str
    header_title: str
    header_subtitle: str
    active_stage_index: int
    progress_fill_width: int
    start_driving_enabled: bool | None = None
    cancel_enabled: bool | None = None


def build_guide_progress_view_state(*, phase, task_status):
    normalized_phase = _normalize_token(phase)
    normalized_status = _normalize_token(task_status)
    active_stage_index = _active_stage_index(normalized_phase, normalized_status)
    header_title, header_subtitle = _header_text(normalized_phase, normalized_status)
    return GuideProgressViewState(
        robot_state_label=_status_label(normalized_phase, normalized_status),
        status_message=_status_message(normalized_phase, normalized_status),
        header_title=header_title,
        header_subtitle=header_subtitle,
        active_stage_index=active_stage_index,
        progress_fill_width=PROGRESS_FILL_WIDTHS[
            min(active_stage_index, len(PROGRESS_FILL_WIDTHS) - 1)
        ],
        start_driving_enabled=_start_driving_enabled(
            normalized_phase,
            normalized_status,
        ),
        cancel_enabled=_cancel_enabled(normalized_phase, normalized_status),
    )


def guide_warning_message_for_reason(reason_code):
    messages = {
        "GUIDE_RUNTIME_NOT_READY": "안내 ROS 런타임이 준비되지 않았습니다.",
        "GUIDE_COMMAND_TRANSPORT_ERROR": (
            "로봇 안내 명령을 보낼 수 없습니다. 직원에게 문의해 주세요."
        ),
        "GUIDE_DESTINATION_NAVIGATION_TRANSPORT_ERROR": (
            "안내 목적지 이동을 시작할 수 없습니다. 직원에게 문의해 주세요."
        ),
        "NAV_CONTEXT_NOT_READY": "안내 이동 준비가 아직 완료되지 않았습니다.",
    }
    return messages.get(
        _normalize_token(reason_code), "안내 주행 시작이 거부되었습니다."
    )


def _status_label(phase, task_status):
    if task_status == "CANCELLED":
        return "안내 취소"
    if task_status == "COMPLETED":
        return "안내 완료"
    if task_status == "FAILED":
        return "안내 실패"
    if phase == "WAIT_TARGET_TRACKING":
        return "대상 확인 중"
    if phase == "READY_TO_START_GUIDANCE":
        return "대상 확인 완료"
    if phase in POST_START_GUIDE_PHASES:
        return "인계 완료"
    if task_status == "RUNNING":
        return "안내 중"
    return "안내 준비"


def _status_message(phase, task_status):
    if task_status == "CANCELLED":
        return "안내가 취소되었습니다."
    if task_status == "COMPLETED":
        return "안내가 완료되었습니다."
    if task_status == "FAILED":
        return "안내를 시작하지 못했습니다. 직원에게 도움을 요청해주세요."
    if phase == "WAIT_TARGET_TRACKING":
        return "로봇이 안내 대상을 확인하고 있습니다."
    if phase == "READY_TO_START_GUIDANCE":
        return "안내 시작을 누르면 로봇이 목적지까지 안내합니다."
    if phase in POST_START_GUIDE_PHASES:
        return "안내를 시작했습니다. 로봇을 따라 이동해주세요."
    if task_status == "RUNNING":
        return "로봇을 따라 이동해주세요."
    return "안내 요청 상태를 확인하고 있습니다."


def _header_text(phase, task_status):
    if task_status == "COMPLETED":
        return "목적지에 도착했습니다", "방문 안내가 완료되었습니다."
    if task_status == "CANCELLED":
        return "안내가 중단되었습니다", "필요하면 직원에게 도움을 요청해 주세요."
    if task_status == "FAILED":
        return "안내를 시작하지 못했습니다", "직원에게 도움을 요청해 주세요."
    if phase == "WAIT_TARGET_TRACKING":
        return "안내를 준비하고 있습니다", "로봇이 안내 대상을 확인하는 중입니다."
    if phase == "READY_TO_START_GUIDANCE":
        return (
            "안내를 시작할 수 있습니다",
            "확인된 안내 대상을 기준으로 주행을 시작합니다.",
        )
    if phase in POST_START_GUIDE_PHASES:
        return "안내를 시작했습니다", "이제 로봇을 따라 목적지로 이동해주세요."
    if task_status == "RUNNING":
        return "로봇을 따라 이동해 주세요", "목적지까지 안전하게 안내해 드립니다."
    return "안내 요청을 확인하고 있습니다", "잠시만 기다려 주세요."


def _active_stage_index(phase, task_status):
    if task_status in {"WAITING", "WAITING_DISPATCH"}:
        return 0
    if task_status in {"READY", "ASSIGNED"}:
        return 1
    if task_status in TERMINAL_TASK_STATUSES:
        return 4
    if phase in PRE_DRIVING_PHASES:
        return 2
    if phase in POST_START_GUIDE_PHASES:
        return 4
    if task_status == "RUNNING":
        return 3
    return 0


def _start_driving_enabled(phase, task_status):
    if task_status in TERMINAL_TASK_STATUSES:
        return False
    if phase:
        if phase == "READY_TO_START_GUIDANCE":
            return True
        if phase == "WAIT_TARGET_TRACKING":
            return False
        if phase in POST_START_GUIDE_PHASES:
            return False
        return None
    if task_status == "RUNNING":
        return False
    return None


def _cancel_enabled(phase, task_status):
    if task_status in TERMINAL_TASK_STATUSES:
        return False
    if phase in POST_START_GUIDE_PHASES:
        return False
    return None


def _normalize_token(value):
    return str(value or "").strip().upper()


__all__ = [
    "GuideProgressViewState",
    "POST_START_GUIDE_PHASES",
    "build_guide_progress_view_state",
    "guide_warning_message_for_reason",
]
