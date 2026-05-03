import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
ROBOT_STATUS_PAGE = (
    REPO_ROOT / "ui" / "utils" / "pages" / "caregiver" / "robot_status_page.py"
)


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _bundle():
    return {
        "summary": {
            "total_robot_count": 5,
            "online_robot_count": 2,
            "offline_robot_count": 1,
            "caution_robot_count": 2,
        },
        "robots": [
            {
                "robot_id": "pinky2",
                "display_name": "Pinky Pro",
                "robot_type": "MOBILE",
                "manager_group": "모바일팀",
                "capabilities": ["DELIVERY", "PATROL"],
                "station_roles": [],
                "connection_status": "ONLINE",
                "runtime_state": "RUNNING",
                "battery_percent": 87.5,
                "current_location": "x=1.2, y=0.8",
                "current_task_id": 1001,
                "current_phase": "DELIVERY_DESTINATION",
                "last_seen_at": "2026-05-03T12:00:00",
            },
            {
                "robot_id": "jetcobot1",
                "display_name": "JetCobot",
                "robot_type": "ARM",
                "manager_group": "운반팀",
                "capabilities": ["MANIPULATION"],
                "station_roles": [{"task_type": "DELIVERY", "station_role": "PICKUP"}],
                "connection_status": "DEGRADED",
                "runtime_state": "ERROR",
                "battery_percent": None,
                "current_location": "-",
                "current_task_id": None,
                "current_phase": None,
                "last_seen_at": "2026-05-03T11:58:00",
            },
        ],
        "delivery_composition": [
            {"label": "픽업 로봇팔", "value": "jetcobot1"},
            {"label": "목적지 로봇팔", "value": "jetcobot2"},
            {"label": "ROS adapter arm_id", "value": "arm1 / arm2"},
        ],
    }


def test_robot_status_page_matches_phase1_layout_contract():
    _app()

    from ui.utils.pages.caregiver.robot_status_page import RobotStatusPage

    page = RobotStatusPage(autoload=False)

    try:
        labels = _label_texts(page)
        refresh_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("robot_status_action") == "refresh"
        ]

        assert "로봇 상태" in labels
        assert "전체 로봇" in labels
        assert "온라인" in labels
        assert "오프라인" in labels
        assert "주의" in labels
        assert "로봇 상세" in labels
        assert "맵/위치 시각화" in labels
        assert page.findChild(QFrame, "pageTimeCard") is not None
        assert "새로고침" in [button.text() for button in refresh_buttons]
    finally:
        page.close()


def test_robot_status_page_applies_server_bundle_to_cards_table_and_detail():
    _app()

    from ui.utils.pages.caregiver.robot_status_page import RobotStatusPage

    page = RobotStatusPage(autoload=False)

    try:
        page.apply_robot_status_bundle(_bundle())

        labels = _label_texts(page)
        assert "5대" in labels
        assert "2대" in labels
        assert "1대" in labels
        assert "pinky2" in labels
        assert "Pinky Pro" in labels
        assert "모바일팀" in labels
        assert "DELIVERY, PATROL" in labels
        assert "픽업 로봇팔" in labels
        assert "pinky2" in labels
        assert "ROS adapter arm_id" in labels
        assert "arm1 / arm2" in labels
        assert not any("Delivery Mobile Robot: pinky2" in text for text in labels)
        assert not any("유형/역할" in text for text in labels)
        assert not any("PICKUP_ARM" in text for text in labels)
        assert page.findChildren(QFrame, "keyValueRow")
        assert page.table.rowCount() == 2
        assert page.table.item(0, 0).text() == "pinky2"
        assert page.table.item(0, 2).text() == "MOBILE"
        assert page.table.item(0, 4).text() == "DELIVERY, PATROL"
        assert page.table.item(0, 5).text() == "ONLINE"

        page.table.selectRow(1)
        page._handle_table_selection()

        labels = _label_texts(page)
        assert "선택 로봇" in labels
        assert "jetcobot1" in labels
        assert "상태" in labels
        assert "DEGRADED / ERROR" in labels
        assert not any("선택 로봇: jetcobot1" in text for text in labels)
    finally:
        page.close()


def test_robot_status_load_worker_uses_caregiver_robot_status_rpc(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.robot_status_page as robot_status_page
    from ui.utils.pages.caregiver.robot_status_page import RobotStatusLoadWorker

    calls = []

    class FakeCaregiverRemoteService:
        def get_robot_status_bundle(self):
            calls.append("get_robot_status_bundle")
            return _bundle()

    monkeypatch.setattr(
        robot_status_page,
        "CaregiverRemoteService",
        FakeCaregiverRemoteService,
    )

    worker = RobotStatusLoadWorker()
    emitted = []
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))

    worker.run()

    assert calls == ["get_robot_status_bundle"]
    assert emitted[0][0] is True
    assert emitted[0][1]["summary"]["total_robot_count"] == 5


def test_robot_status_page_uses_shared_worker_thread_helper():
    source = ROBOT_STATUS_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in source
    assert "start_worker_thread(" in source
    assert "stop_worker_thread(" in source
    assert "QThread(" not in source
    assert "ui.utils.mock_data" not in source
