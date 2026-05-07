from ui.kiosk_ui.guide_progress_state import (
    build_guide_progress_view_state,
    guide_warning_message_for_reason,
)


def test_guide_progress_view_state_keeps_wait_target_tracking_before_running_label():
    state = build_guide_progress_view_state(
        phase="WAIT_TARGET_TRACKING",
        task_status="RUNNING",
    )

    assert state.robot_state_label == "대상 확인 중"
    assert state.status_message == "로봇이 안내 대상을 확인하고 있습니다."
    assert state.header_title == "안내를 준비하고 있습니다"
    assert state.header_subtitle == "로봇이 안내 대상을 확인하는 중입니다."
    assert state.active_stage_index == 2
    assert state.progress_fill_width == 260
    assert state.start_driving_enabled is False
    assert state.cancel_enabled is None


def test_guide_progress_view_state_enables_start_when_target_ready():
    state = build_guide_progress_view_state(
        phase="READY_TO_START_GUIDANCE",
        task_status="RUNNING",
    )

    assert state.robot_state_label == "대상 확인 완료"
    assert state.status_message == "안내 시작을 누르면 로봇이 목적지까지 안내합니다."
    assert state.header_title == "안내를 시작할 수 있습니다"
    assert state.header_subtitle == "확인된 안내 대상을 기준으로 주행을 시작합니다."
    assert state.active_stage_index == 2
    assert state.start_driving_enabled is True


def test_guide_progress_view_state_collapses_guidance_running_to_handoff_complete():
    state = build_guide_progress_view_state(
        phase="GUIDANCE_RUNNING",
        task_status="RUNNING",
    )

    assert state.robot_state_label == "인계 완료"
    assert state.status_message == "안내를 시작했습니다. 로봇을 따라 이동해주세요."
    assert state.header_title == "안내를 시작했습니다"
    assert state.header_subtitle == "이제 로봇을 따라 목적지로 이동해주세요."
    assert state.active_stage_index == 4
    assert state.progress_fill_width == 520
    assert state.start_driving_enabled is False
    assert state.cancel_enabled is False


def test_guide_progress_view_state_collapses_wait_reidentify_to_handoff_complete():
    state = build_guide_progress_view_state(
        phase="WAIT_REIDENTIFY",
        task_status="RUNNING",
    )

    assert state.robot_state_label == "인계 완료"
    assert state.status_message == "안내를 시작했습니다. 로봇을 따라 이동해주세요."
    assert state.header_title == "안내를 시작했습니다"
    assert state.active_stage_index == 4
    assert state.start_driving_enabled is False
    assert state.cancel_enabled is False


def test_guide_progress_view_state_disables_actions_for_terminal_status():
    state = build_guide_progress_view_state(
        phase="GUIDANCE_CANCELLED",
        task_status="CANCELLED",
    )

    assert state.robot_state_label == "안내 취소"
    assert state.status_message == "안내가 취소되었습니다."
    assert state.header_title == "안내가 중단되었습니다"
    assert state.header_subtitle == "필요하면 직원에게 도움을 요청해 주세요."
    assert state.active_stage_index == 4
    assert state.progress_fill_width == 520
    assert state.start_driving_enabled is False
    assert state.cancel_enabled is False


def test_guide_warning_message_maps_known_rejection_reasons():
    assert (
        guide_warning_message_for_reason("GUIDE_RUNTIME_NOT_READY")
        == "안내 ROS 런타임이 준비되지 않았습니다."
    )
    assert (
        guide_warning_message_for_reason("GUIDE_COMMAND_TRANSPORT_ERROR")
        == "로봇 안내 명령을 보낼 수 없습니다. 직원에게 문의해 주세요."
    )
    assert (
        guide_warning_message_for_reason("UNKNOWN_REASON")
        == "안내 주행 시작이 거부되었습니다."
    )
