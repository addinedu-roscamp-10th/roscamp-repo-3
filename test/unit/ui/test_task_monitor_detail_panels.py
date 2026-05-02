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
                    "map_id": "map_test11_0423",
                    "frame_id": "map",
                    "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
                    "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
                },
                "fall_alert": {
                    "result_seq": 44,
                    "frame_id": "frame-44",
                    "fall_streak_ms": 1200,
                    "evidence_image_id": "fall-2001-44",
                    "evidence_image_available": True,
                    "zone_name": "3층 복도",
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                },
            },
            can_resume=True,
            evidence_available=True,
        )

        assert panel.alert_panel.isHidden() is False
        assert panel.fall_alert_task_label.text() == "2001"
        assert panel.evidence_image_id_label.text() == "fall-2001-44"
        assert panel.evidence_image_btn.isEnabled() is True
        assert panel.resume_patrol_btn.isEnabled() is True
        assert "3층 복도" in panel.fall_marker_label.text()
        assert "x=0.93" in panel.fall_marker_label.text()
        assert panel.patrol_map_overlay.fall_alert_pixel_point is not None

        panel.render({}, can_resume=False, evidence_available=False)

        assert panel.alert_panel.isHidden() is True
        assert panel.evidence_image_btn.isEnabled() is False
        assert panel.resume_patrol_btn.isEnabled() is False
        assert panel.fall_marker_label.text() == "낙상 지점 미수신"
        assert panel.patrol_map_overlay.fall_alert_pixel_point is None
    finally:
        panel.close()
