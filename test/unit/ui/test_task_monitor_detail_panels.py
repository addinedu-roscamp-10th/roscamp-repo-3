import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_result_info_panel_renders_result_reason_message_and_warning_state():
    _app()

    from ui.utils.pages.caregiver.task_monitor_detail_panels import (
        TaskResultInfoPanel,
    )

    panel = TaskResultInfoPanel()

    try:
        panel.render(
            {
                "task_status": "FAILED",
                "result_code": "FAILED",
                "reason_code": "ROS_ACTION_TIMEOUT",
                "result_message": "목적지 이동 중 action timeout",
            }
        )

        assert panel.result_code_label.text() == "FAILED"
        assert panel.reason_code_label.text() == "ROS_ACTION_TIMEOUT"
        assert panel.result_message_label.text() == "목적지 이동 중 action timeout"
        assert panel.objectName() == "taskResultPanelWarning"

        panel.render(
            {
                "task_status": "RUNNING",
                "latest_reason_code": "FALL_DETECTED",
            }
        )

        assert panel.result_code_label.text() == "-"
        assert panel.reason_code_label.text() == "FALL_DETECTED"
        assert panel.result_message_label.text() == "-"
        assert panel.objectName() == "taskResultPanel"
    finally:
        panel.close()


def test_patrol_runtime_panel_renders_map_marker_actions_and_hidden_state():
    _app()

    from ui.utils.pages.caregiver.task_monitor_detail_panels import PatrolRuntimePanel

    panel = PatrolRuntimePanel()

    try:
        panel.render(
            {
                "task_id": "2001",
                "task_type": "PATROL",
                "phase": "WAIT_FALL_RESPONSE",
                "patrol_map": {
                    "map_id": "map_0504",
                    "frame_id": "map",
                    "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_0504.yaml",
                    "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_0504.pgm",
                },
                "fall_alert": {
                    "result_seq": 44,
                    "frame_id": "frame-44",
                    "fall_streak_ms": 1200,
                    "evidence_image_id": "fall-2001-44",
                    "evidence_image_available": True,
                    "zone_name": "3층 복도",
                    "alert_pose": {"x": 0.6, "y": 0.1, "yaw": 0.0},
                },
            },
            can_resume=True,
            evidence_available=True,
        )

        assert panel.isHidden() is False
        assert panel.alert_panel.isHidden() is False
        assert panel.fall_alert_task_label.text() == "2001"
        assert panel.evidence_image_id_label.text() == "fall-2001-44"
        assert panel.evidence_image_btn.isEnabled() is True
        assert panel.resume_patrol_btn.isEnabled() is True
        assert "3층 복도" in panel.fall_marker_label.text()
        assert "x=0.60" in panel.fall_marker_label.text()
        assert panel.patrol_map_overlay.fall_alert_pixel_point is not None

        panel.render(
            {"task_id": "1001", "task_type": "DELIVERY"},
            can_resume=False,
            evidence_available=False,
        )

        assert panel.isHidden() is True
        assert panel.alert_panel.isHidden() is True
        assert panel.evidence_image_btn.isEnabled() is False
        assert panel.resume_patrol_btn.isEnabled() is False

        panel.render({}, can_resume=False, evidence_available=False)

        assert panel.isHidden() is True
        assert panel.alert_panel.isHidden() is True
        assert panel.evidence_image_btn.isEnabled() is False
        assert panel.resume_patrol_btn.isEnabled() is False
        assert panel.fall_marker_label.text() == "낙상 지점 미수신"
        assert panel.patrol_map_overlay.fall_alert_pixel_point is None
    finally:
        panel.close()


def test_guide_runtime_panel_renders_connection_destination_and_hidden_state():
    _app()

    from ui.utils.pages.caregiver.task_monitor_detail_panels import GuideRuntimePanel

    panel = GuideRuntimePanel()

    try:
        panel.render(
            {
                "task_id": "3001",
                "task_type": "GUIDE",
                "phase": "WAIT_TARGET_TRACKING",
                "guide_detail": {
                    "guide_phase": "WAIT_TARGET_TRACKING",
                    "target_track_id": "track_17",
                    "visitor_id": 4,
                    "visitor_name": "김민수",
                    "relation_name": "아들",
                    "member_id": 1,
                    "resident_name": "김영수",
                    "room_no": "301",
                    "destination_id": "delivery_room_301",
                    "destination_zone_id": "room_301",
                    "destination_zone_name": "301호",
                },
            }
        )

        assert panel.isHidden() is False
        assert panel.guide_phase_label.text() == "WAIT_TARGET_TRACKING"
        assert panel.target_track_id_label.text() == "track_17"
        assert "김민수" in panel.visitor_label.text()
        assert "아들" in panel.visitor_label.text()
        assert "김영수" in panel.resident_label.text()
        assert "301호" in panel.resident_label.text()
        assert "delivery_room_301" in panel.destination_label.text()
        assert "room_301" in panel.destination_label.text()

        panel.render({"task_id": "2001", "task_type": "PATROL"})

        assert panel.isHidden() is True
        assert panel.guide_phase_label.text() == "-"
        assert panel.target_track_id_label.text() == "-"
        assert panel.visitor_label.text() == "-"
        assert panel.resident_label.text() == "-"
        assert panel.destination_label.text() == "-"
    finally:
        panel.close()
