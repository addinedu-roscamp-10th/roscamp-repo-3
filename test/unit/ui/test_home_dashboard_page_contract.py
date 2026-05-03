import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame, QScrollArea


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
HOME_DASHBOARD_PAGE = (
    REPO_ROOT / "ui" / "utils" / "pages" / "caregiver" / "home_dashboard_page.py"
)
ADMIN_MAIN_WINDOW = REPO_ROOT / "ui" / "admin_ui" / "main_window.py"


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_home_dashboard_page_matches_phase1_layout_contract():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        labels = _label_texts(page)
        refresh_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("dashboard_action") == "refresh"
        ]

        assert page.findChild(QFrame, "systemStatusStrip") is not None
        assert "운영 대시보드" in labels
        assert "새로고침" in [button.text() for button in refresh_buttons]
        assert "사용가능 로봇" in labels
        assert "대기 작업" in labels
        assert "진행 중 작업" in labels
        assert "경고/오류" in labels

        flow_scroll = page.findChild(QScrollArea, "flowBoardScroll")
        assert flow_scroll is not None
        assert flow_scroll.widgetResizable() is True
        assert flow_scroll.maximumHeight() <= 460
    finally:
        page.close()


def test_home_dashboard_updates_system_status_strip_from_load_result():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page._handle_dashboard_loaded(
            True,
            {},
            [],
            {},
            [],
            {
                "관제 서버": "online",
                "데이터베이스": "online",
                "ROS2": "offline",
                "AI 서버": "disabled",
            },
        )

        labels = _label_texts(page)
        assert "관제 서버 정상" in labels
        assert "데이터베이스 정상" in labels
        assert "ROS2 오류" in labels
        assert "AI 서버 미연동" in labels
        assert not any("확인 중" in text for text in labels)
    finally:
        page.close()


def test_home_dashboard_applies_summary_with_total_and_warning_count():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_summary_data(
            {
                "available_robot_count": 2,
                "total_robot_count": 5,
                "waiting_job_count": 3,
                "running_job_count": 1,
                "warning_error_count": 4,
            }
        )

        labels = _label_texts(page)
        assert "2/5대" in labels
        assert "3건" in labels
        assert "1건" in labels
        assert "4건" in labels
    finally:
        page.close()


def test_home_dashboard_robot_board_formats_location_and_last_seen_for_operators():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_robot_board_data(
            [
                {
                    "robot_id": "pinky2",
                    "robot_role": "Pinky Pro",
                    "connection_status": "OFFLINE",
                    "current_location": "좌표 x=1.2, y=0.8",
                    "battery_percent": 87.5,
                    "last_seen_at": "2026-05-03T12:00:00",
                    "chip_type": "red",
                }
            ]
        )

        labels = _label_texts(page)
        assert "현재 위치: 좌표 x=1.2, y=0.8" in labels
        assert "마지막 수신: 2026-05-03 12:00:00" in labels
        assert not any("현재 구역:" in text for text in labels)
        assert not any("T12:00:00" in text for text in labels)
        assert not any("192.168." in text for text in labels)
    finally:
        page.close()


def test_home_dashboard_normalizes_task_flow_into_spec_columns():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import (
        CaregiverHomePage,
        FlowColumn,
    )

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_flow_board_data(
            {
                "READY": [
                    {
                        "task_id": 101,
                        "task_type": "DELIVERY",
                        "task_status": "WAITING_DISPATCH",
                        "robot_id": "pinky2",
                        "description": "delivery accepted",
                        "cancellable": True,
                    }
                ],
                "ASSIGNED": [
                    {
                        "task_id": 102,
                        "task_type": "PATROL",
                        "task_status": "ASSIGNED",
                        "robot_id": "pinky3",
                        "description": "patrol assigned",
                    }
                ],
                "RUNNING": [
                    {
                        "task_id": 103,
                        "task_type": "DELIVERY",
                        "task_status": "RUNNING",
                        "robot_id": "pinky2",
                        "description": "moving",
                    },
                    {
                        "task_id": 104,
                        "task_type": "PATROL",
                        "task_status": "CANCEL_REQUESTED",
                        "robot_id": "pinky3",
                        "description": "cancel requested",
                    },
                ],
                "DONE": [
                    {
                        "task_id": 105,
                        "task_type": "DELIVERY",
                        "task_status": "FAILED",
                        "robot_id": "pinky2",
                        "description": "failed",
                    }
                ],
            }
        )

        columns = {column.column_key: column for column in page.findChildren(FlowColumn)}
        assert list(columns) == [
            "WAITING",
            "ASSIGNED",
            "IN_PROGRESS",
            "CANCELING",
            "DONE",
        ]
        assert columns["WAITING"].task_count_label.text() == "1건"
        assert columns["ASSIGNED"].task_count_label.text() == "1건"
        assert columns["IN_PROGRESS"].task_count_label.text() == "1건"
        assert columns["CANCELING"].task_count_label.text() == "1건"
        assert columns["DONE"].task_count_label.text() == "1건"
    finally:
        page.close()


def test_home_dashboard_task_cards_expose_home_cancel_action():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_flow_board_data(
            {
                "RUNNING": [
                    {
                        "task_id": 201,
                        "task_type": "DELIVERY",
                        "task_status": "RUNNING",
                        "robot_id": "pinky2",
                        "description": "moving",
                        "cancellable": True,
                    }
                ]
            }
        )

        cancel_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("dashboard_cancel_task_id") == 201
        ]
        assert len(cancel_buttons) == 1
        assert cancel_buttons[0].text() == "작업 취소"
        assert cancel_buttons[0].isEnabled() is True
    finally:
        page.close()


def test_home_dashboard_cancel_worker_uses_common_task_cancel_rpc(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.home_dashboard_page as home_dashboard_page
    from ui.utils.pages.caregiver.home_dashboard_page import DashboardTaskCancelWorker

    calls = []

    class FakeTaskMonitorRemoteService:
        def cancel_task(self, **payload):
            calls.append(payload)
            return {
                "result_code": "CANCEL_REQUESTED",
                "result_message": "cancel accepted",
                "task_id": payload["task_id"],
                "cancel_requested": True,
            }

    monkeypatch.setattr(
        home_dashboard_page,
        "TaskMonitorRemoteService",
        FakeTaskMonitorRemoteService,
    )

    worker = DashboardTaskCancelWorker(
        {
            "task_id": 201,
            "caregiver_id": 1,
            "reason": "operator_cancel",
        }
    )
    emitted = []
    worker.finished.connect(lambda success, response: emitted.append((success, response)))

    worker.run()

    assert calls == [
        {
            "task_id": 201,
            "caregiver_id": 1,
            "reason": "operator_cancel",
        }
    ]
    assert emitted[0][0] is True
    assert emitted[0][1]["result_code"] == "CANCEL_REQUESTED"


def test_home_dashboard_uses_shared_worker_thread_helper():
    dashboard_source = HOME_DASHBOARD_PAGE.read_text(encoding="utf-8")
    main_window_source = ADMIN_MAIN_WINDOW.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in dashboard_source
    assert "start_worker_thread(" in dashboard_source
    assert "stop_worker_thread(" in dashboard_source
    assert "QThread(" not in dashboard_source
    assert "class CaregiverHomePage" not in main_window_source
    assert "QThread" not in main_window_source
