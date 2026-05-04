import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QLabel

from ui.utils.session.session_manager import SessionManager, UserSession


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_task_monitor_page_tracks_patrol_events_and_fall_marker():
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)

    try:
        assert page.task_table.objectName() == "taskMonitorTable"
        assert page.empty_state_label.text() == "수신된 작업 이벤트가 없습니다."

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "2001",
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "phase": "MOVE_TO_WAYPOINT",
                    "assigned_robot_id": "pinky3",
                    "cancellable": True,
                },
            }
        )

        assert page.task_table.rowCount() == 1
        assert page.detail_task_id_label.text() == "2001"
        assert page.detail_task_type_label.text() == "PATROL"
        assert page.detail_task_status_label.text() == "RUNNING"
        assert page.detail_phase_label.text() == "MOVE_TO_WAYPOINT"
        assert page.detail_robot_label.text() == "pinky3"

        page.apply_stream_event(
            {
                "event_type": "ACTION_FEEDBACK_UPDATED",
                "payload": {
                    "task_id": "2001",
                    "feedback_summary": "MOVING / 남은 거리 1.25m",
                    "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
                },
            }
        )

        assert page.detail_feedback_label.text() == "MOVING / 남은 거리 1.25m"
        assert page.detail_pose_label.text() == "x=1.20, y=0.40, yaw=0.00"

        page.apply_stream_event(
            {
                "event_type": "ALERT_CREATED",
                "payload": {
                    "task_id": "2001",
                    "result_seq": 44,
                    "frame_id": "frame-44",
                    "fall_streak_ms": 1200,
                    "evidence_image_id": "fall-2001-44",
                    "evidence_image_available": True,
                    "zone_name": "3층 복도",
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                },
            }
        )

        assert page.fall_alert_panel.isHidden() is False
        assert page.fall_alert_task_label.text() == "2001"
        assert page.evidence_image_id_label.text() == "fall-2001-44"
        assert page.evidence_image_btn.isEnabled() is True
        assert page.resume_patrol_btn.isEnabled() is True
        assert "3층 복도" in page.fall_marker_label.text()
        assert "x=0.93" in page.fall_marker_label.text()

        page._handle_patrol_resume_finished(
            True,
            {
                "result_code": "ACCEPTED",
                "result_message": "순찰을 재개했습니다.",
                "task_id": "2001",
                "task_type": "PATROL",
                "task_status": "RUNNING",
                "phase": "FOLLOW_PATROL_PATH",
                "assigned_robot_id": "pinky3",
            },
        )

        assert page.detail_phase_label.text() == "FOLLOW_PATROL_PATH"
        assert page.resume_patrol_btn.isEnabled() is False
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_exposes_cancel_action_by_task_type_and_status(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))
    page = TaskMonitorPage(autostart_stream=False)
    started_payloads = []
    monkeypatch.setattr(
        page,
        "_start_task_cancel",
        lambda payload: started_payloads.append(payload),
    )

    try:
        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "1001",
                    "task_type": "DELIVERY",
                    "task_status": "RUNNING",
                    "phase": "MOVING_TO_DESTINATION",
                    "assigned_robot_id": "pinky2",
                    "cancellable": True,
                },
            }
        )

        assert page.cancel_task_btn.text() == "작업 취소"
        assert page.cancel_task_btn.isEnabled() is True

        page._request_task_cancel()

        assert started_payloads == [
            {
                "task_id": "1001",
                "caregiver_id": 7,
                "reason": "operator_cancel",
            }
        ]
        assert page.cancel_task_btn.isEnabled() is False
        assert page.cancel_task_btn.text() == "취소 요청 전송 중..."
        assert "취소 요청 전송 중" in page.cancel_status_label.text()

        page._handle_task_cancel_finished(
            True,
            {
                "result_code": "CANCEL_REQUESTED",
                "result_message": "작업 취소 요청이 접수되었습니다.",
                "reason_code": "USER_CANCEL_REQUESTED",
                "task_id": "1001",
                "task_type": "DELIVERY",
                "task_status": "CANCEL_REQUESTED",
                "phase": "CANCEL_REQUESTED",
                "assigned_robot_id": "pinky2",
                "cancellable": False,
                "cancel_requested": True,
            },
        )

        assert page.detail_task_status_label.text() == "CANCEL_REQUESTED"
        assert page.cancel_task_btn.isEnabled() is False
        assert page.cancel_task_btn.text() == "취소 처리 중"
        assert "USER_CANCEL_REQUESTED" in page.cancel_status_label.text()

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "2001",
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "phase": "FOLLOW_PATROL_PATH",
                    "assigned_robot_id": "pinky3",
                    "cancellable": True,
                },
            }
        )
        page._select_task("2001")

        assert page.cancel_task_btn.text() == "순찰 중단"
        assert page.cancel_task_btn.isEnabled() is True

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "2001",
                    "task_type": "PATROL",
                    "task_status": "COMPLETED",
                    "phase": "COMPLETED",
                    "assigned_robot_id": "pinky3",
                    "cancellable": False,
                },
            }
        )

        assert page.cancel_task_btn.isEnabled() is False
        assert page.cancel_task_btn.text() == "취소 불가"
    finally:
        SessionManager.logout()
        page.shutdown()
        page.close()


def test_task_monitor_page_shows_result_reason_and_message_prominently():
    _app()

    from ui.utils.pages.caregiver.task_monitor_detail_panels import (
        PatrolRuntimePanel,
        TaskResultInfoPanel,
    )
    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)

    try:
        assert isinstance(page.result_info_panel, TaskResultInfoPanel)
        assert isinstance(page.patrol_runtime_section, PatrolRuntimePanel)

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "3001",
                    "task_type": "DELIVERY",
                    "task_status": "FAILED",
                    "phase": "FAILED",
                    "assigned_robot_id": "pinky2",
                    "result_code": "FAILED",
                    "reason_code": "ROS_ACTION_TIMEOUT",
                    "result_message": "목적지 이동 중 action timeout",
                    "cancellable": False,
                },
            }
        )

        assert page.detail_result_code_label.text() == "FAILED"
        assert page.detail_reason_code_label.text() == "ROS_ACTION_TIMEOUT"
        assert page.detail_result_message_label.text() == "목적지 이동 중 action timeout"
        assert page.result_info_panel.objectName() == "taskResultPanelWarning"
        assert page.patrol_runtime_section.isHidden() is True

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "3002",
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "phase": "WAIT_FALL_RESPONSE",
                    "assigned_robot_id": "pinky3",
                    "latest_reason_code": "FALL_DETECTED",
                },
            }
        )
        page._select_task("3002")

        assert page.detail_result_code_label.text() == "-"
        assert page.detail_reason_code_label.text() == "FALL_DETECTED"
        assert page.detail_result_message_label.text() == "-"
        assert page.result_info_panel.objectName() == "taskResultPanel"
        assert page.patrol_runtime_section.isHidden() is False
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_applies_snapshot_and_starts_stream_from_watermark(
    monkeypatch,
):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)
    started_last_seq_values = []
    monkeypatch.setattr(
        page,
        "_start_task_event_stream",
        lambda *, last_seq=0: started_last_seq_values.append(last_seq),
    )

    try:
        page._handle_snapshot_loaded(
            True,
            {
                "result_code": "ACCEPTED",
                "last_event_seq": 12,
                "tasks": [
                    {
                        "task_id": 2001,
                        "task_type": "PATROL",
                        "task_status": "RUNNING",
                        "result_code": "REJECTED",
                        "reason_code": "NO_ELIGIBLE_PINKY",
                        "result_message": "순찰 가능한 로봇이 없습니다.",
                        "phase": "WAIT_FALL_RESPONSE",
                        "assigned_robot_id": "pinky3",
                        "patrol_map": {
                            "map_id": "map_test11_0423",
                            "frame_id": "map",
                            "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
                            "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
                        },
                        "patrol_path": {
                            "frame_id": "map",
                            "waypoint_count": 3,
                            "current_waypoint_index": 1,
                            "poses": [
                                {"x": 0.1665755137108074, "y": -0.4496830900440016, "yaw": 1.57},
                                {"x": 1.6946025435218914, "y": 0.0043433854992070454, "yaw": 0.0},
                            ],
                        },
                        "latest_feedback": {
                            "feedback_summary": "MOVING / 남은 거리 1.25m",
                            "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
                        },
                        "latest_alert": {
                            "alert_id": 17,
                            "result_seq": 44,
                            "frame_id": "frame-44",
                            "fall_streak_ms": 1200,
                            "evidence_image_id": "fall-2001-44",
                            "evidence_image_available": True,
                            "zone_name": "3층 복도",
                            "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                        },
                    }
                ],
            },
        )

        assert page.task_table.rowCount() == 1
        assert page.detail_task_id_label.text() == "2001"
        assert page.detail_result_code_label.text() == "REJECTED"
        assert page.detail_reason_code_label.text() == "NO_ELIGIBLE_PINKY"
        assert page.detail_result_message_label.text() == "순찰 가능한 로봇이 없습니다."
        assert page.detail_feedback_label.text() == "MOVING / 남은 거리 1.25m"
        assert page.evidence_image_id_label.text() == "fall-2001-44"
        assert "3층 복도" in page.fall_marker_label.text()
        assert page.patrol_map_overlay.map_loaded is True
        assert page.patrol_map_overlay.route_pixel_points == [(18, 46), (94, 24)]
        assert page.patrol_map_overlay.current_waypoint_index == 1
        assert page.patrol_map_overlay.robot_pixel_point is not None
        assert page.patrol_map_overlay.fall_alert_pixel_point == (56, 15)
        assert started_last_seq_values == [12]
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_snapshot_failure_falls_back_to_full_stream(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)
    started_last_seq_values = []
    monkeypatch.setattr(
        page,
        "_start_task_event_stream",
        lambda *, last_seq=0: started_last_seq_values.append(last_seq),
    )

    try:
        page._handle_snapshot_loaded(False, "timeout")

        assert "초기 상태" in page.stream_status_label.text()
        assert started_last_seq_values == [0]
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_exposes_manual_refresh_reconnect_and_update_time(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)
    snapshot_statuses = []
    reconnect_last_seq_values = []
    stopped_streams = []

    monkeypatch.setattr(
        page,
        "_start_snapshot_load",
        lambda *, status_text="초기 상태 조회 중": snapshot_statuses.append(status_text),
    )
    monkeypatch.setattr(
        page,
        "_stop_task_event_stream_thread",
        lambda: stopped_streams.append(True),
    )
    monkeypatch.setattr(
        page,
        "_start_task_event_stream",
        lambda *, last_seq=0: reconnect_last_seq_values.append(last_seq),
    )

    try:
        assert page.refresh_snapshot_btn.text() == "새로고침"
        assert page.reconnect_stream_btn.text() == "스트림 재연결"
        assert page.last_update_label.text() == "마지막 업데이트: -"
        assert page.findChild(QFrame, "pageTimeCard") is page.time_card

        page.refresh_snapshot()
        assert snapshot_statuses == ["수동 새로고침 중"]

        page._last_event_seq = 44
        page.reconnect_task_event_stream()
        assert stopped_streams == [True]
        assert reconnect_last_seq_values == [44]
        assert "재연결" in page.stream_status_label.text()
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_updates_watermark_and_last_update_label(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)
    started_last_seq_values = []
    monkeypatch.setattr(
        page,
        "_start_task_event_stream",
        lambda *, last_seq=0: started_last_seq_values.append(last_seq),
    )

    try:
        page._handle_snapshot_loaded(
            True,
            {
                "result_code": "ACCEPTED",
                "last_event_seq": 12,
                "tasks": [],
            },
        )

        assert page._last_event_seq == 12
        assert started_last_seq_values == [12]
        assert "snapshot" in page.last_update_label.text()
        assert page.refresh_snapshot_btn.isEnabled() is True

        page._handle_task_event_batch(
            {
                "batch_end_seq": 21,
                "events": [
                    {
                        "event_type": "TASK_UPDATED",
                        "payload": {
                            "task_id": "2001",
                            "task_type": "PATROL",
                            "task_status": "RUNNING",
                        },
                    }
                ],
            }
        )

        assert page._last_event_seq == 21
        assert "event" in page.last_update_label.text()
        assert "21" in page.stream_status_label.text()

        page._handle_task_event_stream_failed("connection lost")
        assert "이벤트 스트림 중단" in page.stream_status_label.text()
        assert page.reconnect_stream_btn.isEnabled() is True
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_starts_fall_evidence_lookup_from_selected_alert(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)
    started_payloads = []
    monkeypatch.setattr(
        page,
        "_start_fall_evidence_image_lookup",
        lambda payload: started_payloads.append(payload),
    )

    try:
        page.apply_stream_event(
            {
                "event_type": "ALERT_CREATED",
                "payload": {
                    "task_id": "2001",
                    "alert_id": "17",
                    "result_seq": 541,
                    "frame_id": "frame-541",
                    "evidence_image_id": "fall_evidence_pinky3_541",
                    "evidence_image_available": True,
                    "zone_name": "3층 복도",
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                },
            }
        )

        page.open_fall_evidence_dialog()

        assert started_payloads == [
            {
                "consumer_id": "ui-admin-task-monitor",
                "task_id": "2001",
                "alert_id": "17",
                "evidence_image_id": "fall_evidence_pinky3_541",
                "result_seq": 541,
            }
        ]
        assert page.evidence_image_btn.text() == "조회 중..."
    finally:
        page.shutdown()
        page.close()


def test_task_monitor_page_shows_fall_evidence_dialog_on_ok_response():
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = TaskMonitorPage(autostart_stream=False)

    try:
        page._handle_fall_evidence_finished(
            True,
            {
                "result_code": "OK",
                "task_id": "2001",
                "alert_id": "17",
                "evidence_image_id": "fall_evidence_pinky3_541",
                "result_seq": 541,
                "frame_id": "frame-541",
                "frame_ts": "2026-04-30T06:09:38Z",
                "image_format": "jpeg",
                "image_encoding": "base64",
                "image_data": "/9j/AA==",
                "image_width_px": 640,
                "image_height_px": 480,
                "detections": [],
            },
        )

        assert page._fall_evidence_dialog is not None
        assert page._fall_evidence_dialog.objectName() == "fallEvidenceImageDialog"
        assert (
            page._fall_evidence_dialog.findChild(QLabel, "fallEvidenceImageIdLabel").text()
            == "fall_evidence_pinky3_541"
        )
    finally:
        page.shutdown()
        if page._fall_evidence_dialog is not None:
            page._fall_evidence_dialog.close()
        page.close()


def test_patrol_resume_dialog_builds_pat_002_payload():
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import PatrolResumeDialog

    dialog = PatrolResumeDialog(task_id="2001")

    try:
        assert dialog.isModal() is True
        assert dialog.findChild(QFrame, "patrolResumeFormPanel") is not None

        dialog.member_id_input.setText("301")
        dialog.action_memo_input.setPlainText("119 신고 후 병원 이송")

        assert dialog.build_payload(caregiver_id=7) == {
            "task_id": "2001",
            "caregiver_id": 7,
            "member_id": 301,
            "action_memo": "119 신고 후 병원 이송",
        }
    finally:
        dialog.close()


def test_task_monitor_page_starts_patrol_resume_from_modal_payload(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))
    page = TaskMonitorPage(autostart_stream=False)
    started_payloads = []

    try:
        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": "2001",
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "phase": "WAIT_FALL_RESPONSE",
                    "assigned_robot_id": "pinky3",
                },
            }
        )
        dialog = page._create_patrol_resume_dialog()
        dialog.member_id_input.setText("301")
        dialog.action_memo_input.setPlainText("119 신고 후 병원 이송")
        monkeypatch.setattr(
            page,
            "_start_patrol_resume_task",
            lambda payload: started_payloads.append(payload),
        )

        assert page.fall_alert_panel.isHidden() is False
        assert page.resume_patrol_btn.isEnabled() is True

        page._handle_patrol_resume_dialog_accepted(dialog)

        assert started_payloads == [
            {
                "task_id": "2001",
                "caregiver_id": 7,
                "member_id": 301,
                "action_memo": "119 신고 후 병원 이송",
            }
        ]
        assert page.resume_patrol_btn.text() == "재개 요청 전송 중..."
    finally:
        SessionManager.logout()
        page.shutdown()
        page.close()
