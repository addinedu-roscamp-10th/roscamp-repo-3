import os
import base64
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame, QComboBox, QWidget


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
                "capabilities": ["GUIDE", "DELIVERY", "PATROL"],
                "station_roles": [],
                "connection_status": "ONLINE",
                "runtime_state": "RUNNING",
                "battery_percent": 87.5,
                "current_location": "x=1.2, y=0.8",
                "current_pose": {
                    "map_id": "map_0504",
                    "frame_id": "map",
                    "x": 1.2,
                    "y": 0.8,
                    "yaw": 0.0,
                    "updated_at": "2026-05-03T12:00:00",
                },
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
                "current_pose": None,
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
        "map_profiles": [
            {"map_id": "map_0504", "map_name": "순찰/안내 맵", "frame_id": "map"},
            {
                "map_id": "map_test12_0506",
                "map_name": "운반 맵",
                "frame_id": "map",
            },
        ],
        "selected_map_id": "map_0504",
        "map_assets": _map_assets("map_0504"),
    }


def _map_assets(map_id):
    return {
        "map_id": map_id,
        "yaml_text": "image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
        "pgm_bytes": b"P5\n4 4\n255\n" + (b"\x00" * 16),
        "yaml_sha256": f"{map_id}-yaml",
        "pgm_sha256": f"{map_id}-pgm",
    }


def _multi_map_bundle():
    bundle = _bundle()
    bundle["robots"] = [
        {
            **bundle["robots"][0],
            "robot_id": "pinky2",
            "current_location": "x=1.2, y=0.8",
            "current_pose": {
                "map_id": "map_test12_0506",
                "frame_id": "map",
                "x": 1.2,
                "y": 0.8,
                "yaw": 0.0,
                "updated_at": "2026-05-03T12:00:00",
            },
        },
        {
            **bundle["robots"][0],
            "robot_id": "pinky3",
            "current_location": "x=2.0, y=1.0",
            "current_pose": {
                "map_id": "map_0504",
                "frame_id": "map",
                "x": 2.0,
                "y": 1.0,
                "yaw": 1.57,
                "updated_at": "2026-05-03T12:00:01",
            },
        },
        bundle["robots"][1],
    ]
    bundle["selected_map_id"] = "map_0504"
    bundle["map_assets"] = _map_assets("map_0504")
    return bundle


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
        robot_cards_panel = page.findChild(QFrame, "robotCardsPanel")
        location_panel = page.findChild(QFrame, "robotLocationMapPanel")
        assert robot_cards_panel is not None
        assert location_panel is not None
        assert location_panel.parentWidget() is robot_cards_panel
        assert location_panel.minimumHeight() >= 320
        assert page.findChild(QComboBox, "robotMapSelector") is not None
        assert page.findChild(QWidget, "robotLocationMapCanvas") is not None
        assert "로봇 위치 맵" in labels
        assert "로봇 위치 요약" not in labels
        assert "맵/위치 시각화" not in labels
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
        assert "GUIDE, DELIVERY, PATROL" in labels
        assert "픽업 로봇팔" in labels
        assert "pinky2" in labels
        assert "ROS adapter arm_id" in labels
        assert "arm1 / arm2" in labels
        assert "로봇 위치 맵" in labels
        assert page.map_selector.count() == 2
        assert page.selected_map_id == "map_0504"
        assert page.robot_map_canvas.map_loaded is True
        assert page.robot_map_canvas.visible_robot_ids == ["pinky2"]
        assert "x=1.2, y=0.8" in labels
        assert not any("Delivery Mobile Robot: pinky2" in text for text in labels)
        assert not any("유형/역할" in text for text in labels)
        assert not any("PICKUP_ARM" in text for text in labels)
        assert not any("관리 그룹" in text for text in labels)
        assert not any("모바일팀" in text for text in labels)
        assert not any("운반팀" in text for text in labels)
        assert page.findChildren(QFrame, "keyValueRow")
        assert page.table.rowCount() == 2
        assert page.table.item(0, 0).text() == "pinky2"
        assert page.table.item(0, 2).text() == "MOBILE"
        assert page.table.item(0, 3).text() == "GUIDE, DELIVERY, PATROL"
        assert page.table.item(0, 4).text() == "ONLINE"
        assert page.table.item(0, 8).text() == "2026.05.03 12:00"
        assert "T12:00:00" not in page.table.item(0, 8).text()

        robot_cards = [
            frame
            for frame in page.findChildren(QFrame)
            if frame.objectName() == "robotStatusCard"
        ]
        assert len(robot_cards) == 2
        first_card_labels = _label_texts(robot_cards[0])
        second_card_labels = _label_texts(robot_cards[1])
        assert "pinky2" in first_card_labels
        assert "Pinky Pro" not in first_card_labels
        assert "jetcobot1" in second_card_labels
        assert "JetCobot" not in second_card_labels
        assert not any("Pinky Pro · pinky2" in text for text in labels)
        assert not any("JetCobot · jetcobot1" in text for text in labels)

        page.table.selectRow(1)
        page._handle_table_selection()

        labels = _label_texts(page)
        assert "선택 로봇" in labels
        assert "jetcobot1" in labels
        assert "상태" in labels
        assert "DEGRADED / ERROR" in labels
        assert "2026.05.03 11:58" in labels
        assert "2026-05-03T11:58:00" not in labels
        assert not any("선택 로봇: jetcobot1" in text for text in labels)
    finally:
        page.close()


def test_robot_status_page_orders_pinky_cards_above_jetcobot_cards():
    _app()

    from ui.utils.pages.caregiver.robot_status_page import RobotStatusPage

    page = RobotStatusPage(autoload=False)
    bundle = _bundle()
    bundle["robots"] = [
        {"robot_id": "jetcobot2", "robot_type": "ARM"},
        {"robot_id": "pinky3", "robot_type": "MOBILE"},
        {"robot_id": "jetcobot1", "robot_type": "ARM"},
        {"robot_id": "pinky1", "robot_type": "MOBILE"},
        {"robot_id": "pinky2", "robot_type": "MOBILE"},
    ]

    try:
        page.apply_robot_status_bundle(bundle)

        assert page.card_grid.itemAtPosition(0, 0).widget().robot_id == "pinky1"
        assert page.card_grid.itemAtPosition(0, 1).widget().robot_id == "pinky2"
        assert page.card_grid.itemAtPosition(0, 2).widget().robot_id == "pinky3"
        assert page.card_grid.itemAtPosition(1, 0).widget().robot_id == "jetcobot1"
        assert page.card_grid.itemAtPosition(1, 1).widget().robot_id == "jetcobot2"
        assert [page.table.item(row, 0).text() for row in range(5)] == [
            "pinky1",
            "pinky2",
            "pinky3",
            "jetcobot1",
            "jetcobot2",
        ]
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

    class FakeCoordinateConfigRemoteService:
        def list_map_profiles(self):
            calls.append("list_map_profiles")
            return {
                "result_code": "OK",
                "map_profiles": _bundle()["map_profiles"],
            }

        def get_map_asset(self, *, asset_type, map_id=None, encoding=None):
            calls.append(f"get_map_asset:{asset_type}:{map_id}:{encoding}")
            if asset_type == "YAML":
                return {
                    "result_code": "OK",
                    "content_text": _map_assets(map_id)["yaml_text"],
                    "sha256": "yaml-sha",
                }
            return {
                "result_code": "OK",
                "content_base64": base64.b64encode(
                    _map_assets(map_id)["pgm_bytes"]
                ).decode("ascii"),
                "sha256": "pgm-sha",
            }

    monkeypatch.setattr(
        robot_status_page,
        "CaregiverRemoteService",
        FakeCaregiverRemoteService,
    )
    monkeypatch.setattr(
        robot_status_page,
        "CoordinateConfigRemoteService",
        FakeCoordinateConfigRemoteService,
    )

    worker = RobotStatusLoadWorker(selected_map_id="map_0504")
    emitted = []
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))

    worker.run()

    assert calls == [
        "get_robot_status_bundle",
        "list_map_profiles",
        "get_map_asset:YAML:map_0504:TEXT",
        "get_map_asset:PGM:map_0504:BASE64",
    ]
    assert emitted[0][0] is True
    assert emitted[0][1]["summary"]["total_robot_count"] == 5
    assert emitted[0][1]["selected_map_id"] == "map_0504"
    assert emitted[0][1]["map_assets"]["pgm_bytes"] == _map_assets("map_0504")[
        "pgm_bytes"
    ]


def test_robot_status_page_uses_shared_worker_thread_helper():
    source = ROBOT_STATUS_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in source
    assert "start_worker_thread(" in source
    assert "stop_worker_thread(" in source
    assert "QThread(" not in source
    assert "ui.utils.mock_data" not in source
