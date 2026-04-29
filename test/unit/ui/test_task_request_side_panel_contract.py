import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame


_APP = None
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_task_request_side_panel_composes_named_cards_and_keeps_aliases():
    _app()

    from ui.utils.pages.caregiver.task_request_side_panel import (
        NoticeCard,
        RequestPreviewCard,
        RequestResultCard,
        RobotStatusCard,
        TaskRequestSidePanel,
    )

    panel = TaskRequestSidePanel()

    try:
        assert isinstance(panel.preview_card, RequestPreviewCard)
        assert isinstance(panel.robot_status_card, RobotStatusCard)
        assert isinstance(panel.result_card, RequestResultCard)
        assert isinstance(panel.notice_card, NoticeCard)

        assert panel.preview_card.objectName() == "requestPreviewCard"
        assert panel.robot_status_card.objectName() == "robotStatusCard"
        assert panel.result_card.objectName() == "resultPanel"
        assert panel.notice_card.objectName() == "noticeCard"

        assert panel.preview_caregiver_id is panel.preview_card.preview_caregiver_id
        assert panel.robot_id_label is panel.robot_status_card.robot_id_label
        assert panel.result_code_label is panel.result_card.result_code_label
        assert len(panel.findChildren(QFrame, "sideMetricRow")) >= 14
    finally:
        panel.close()


def test_task_request_side_panel_cards_update_delivery_and_patrol_contexts():
    _app()

    from ui.utils.pages.caregiver.task_request_side_panel import TaskRequestSidePanel

    panel = TaskRequestSidePanel()

    try:
        panel.update_preview(
            {
                "caregiver_id": "7",
                "item_id": "1",
                "item_name": "세면도구 세트",
                "quantity": 2,
                "destination_id": "delivery_room_301",
                "priority": "URGENT",
            }
        )

        assert panel.preview_item_label.text() == "물품"
        assert panel.preview_item.text() == "세면도구 세트"
        assert panel.preview_quantity.text() == "2개"
        assert panel.robot_destination_label.text() == "delivery_room_301"

        panel.update_preview(
            {
                "task_type": "PATROL",
                "caregiver_id": "7",
                "patrol_area_id": "patrol_ward_night_01",
                "patrol_area_name": "야간 병동 순찰",
                "priority": "HIGHEST",
                "assigned_robot_id": "pinky_from_db",
            }
        )

        assert panel.preview_item_label.text() == "순찰 구역"
        assert panel.preview_item.text() == "야간 병동 순찰"
        assert panel.preview_quantity_label.text() == "구역 ID"
        assert panel.preview_destination.text() == "pinky_from_db"
        assert panel.robot_id_label.text() == "pinky_from_db"
        assert panel.robot_destination_text_label.text() == "waypoint"
        assert panel.robot_map_label.text() == "순찰 경로 / waypoint placeholder"

        panel.update_preview(
            {
                "task_type": "PATROL",
                "caregiver_id": "7",
                "patrol_area_id": "patrol_no_robot",
                "patrol_area_name": "로봇 미정 순찰",
                "priority": "NORMAL",
                "assigned_robot_id": None,
            }
        )

        assert panel.preview_destination.text() == "미정"
        assert panel.robot_id_label.text() == "미정"
    finally:
        panel.close()


def test_request_result_card_exposes_cancel_button_by_task_status():
    _app()

    from ui.utils.pages.caregiver.task_request_side_panel import TaskRequestSidePanel

    panel = TaskRequestSidePanel()

    try:
        assert panel.cancel_task_btn.text() == "작업 취소"
        assert panel.cancel_task_btn.isEnabled() is False

        panel.show_delivery_result(
            {
                "result_code": "ACCEPTED",
                "result_message": "작업이 접수되었습니다.",
                "task_id": 1001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
            }
        )

        assert panel.cancel_task_btn.isEnabled() is True
        assert panel.cancel_task_btn.property("task_id") == 1001

        panel.show_delivery_result(
            {
                "result_code": "CANCEL_REQUESTED",
                "result_message": "취소 요청이 접수되었습니다.",
                "task_id": 1001,
                "task_status": "CANCEL_REQUESTED",
                "assigned_robot_id": "pinky2",
                "cancel_requested": True,
            }
        )

        assert panel.cancel_task_btn.isEnabled() is False
        assert panel.cancel_task_btn.text() == "취소 처리 중"
    finally:
        panel.close()


def test_side_panel_updates_task_status_and_feedback_from_push_events():
    _app()

    from ui.utils.pages.caregiver.task_request_side_panel import TaskRequestSidePanel

    panel = TaskRequestSidePanel()

    try:
        panel.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": 1001,
                    "task_status": "RUNNING",
                    "phase": "MOVE_TO_DESTINATION",
                    "assigned_robot_id": "pinky2",
                    "latest_reason_code": None,
                },
            }
        )

        assert panel.task_id_label.text() == "1001"
        assert panel.task_status_label.text() == "RUNNING"
        assert panel.assigned_robot_id_label.text() == "pinky2"
        assert panel.robot_state_label.text() == "MOVE_TO_DESTINATION"

        panel.apply_stream_event(
            {
                "event_type": "ACTION_FEEDBACK_UPDATED",
                "payload": {
                    "task_id": 1001,
                    "feedback_summary": "MOVING / 남은 거리 1.25m",
                    "pose": {
                        "x": 1.2,
                        "y": 0.4,
                        "yaw": 0.0,
                    },
                },
            }
        )

        assert panel.robot_state_label.text() == "MOVING / 남은 거리 1.25m"
        assert panel.robot_pose_label.text() == "x=1.20, y=0.40, yaw=0.00"
    finally:
        panel.close()


def test_task_request_page_imports_side_panel_instead_of_defining_it_inline():
    source = (
        PROJECT_ROOT / "ui/utils/pages/caregiver/task_request_page.py"
    ).read_text()

    assert "class TaskRequestSidePanel" not in source
    assert "task_request_side_panel import TaskRequestSidePanel" in source
