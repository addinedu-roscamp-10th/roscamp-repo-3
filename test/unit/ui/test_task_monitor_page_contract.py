import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame

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
