import base64
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QVBoxLayout,
)


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


def _map_assets(map_id="map_0504", *, width=4, height=4):
    return {
        "map_id": map_id,
        "yaml_text": "image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
        "pgm_bytes": f"P5\n{width} {height}\n255\n".encode("ascii")
        + (b"\x00" * (width * height)),
        "yaml_sha256": f"{map_id}-yaml",
        "pgm_sha256": f"{map_id}-pgm",
    }


def test_home_dashboard_page_matches_phase1_layout_contract():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    page.resize(1280, 900)
    page.show()
    app.processEvents()

    try:
        labels = _label_texts(page)
        refresh_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("dashboard_action") == "refresh"
        ]

        assert page.findChild(QFrame, "systemStatusStrip") is not None
        header = page.findChild(QFrame, "pageHeader")
        time_card = page.findChild(QFrame, "homeTimeCard")
        assert header is not None
        assert time_card is not None
        assert page.time_card is time_card
        assert page.clock_label.objectName() == "timeCardClock"
        assert page.date_label.objectName() == "timeCardDate"
        assert "실시간 운영 요약" not in labels
        assert page.status_banner.parentWidget() is page
        assert page.status_banner.maximumHeight() <= 128
        assert "운영 대시보드" in labels
        assert "새로고침" in [button.text() for button in refresh_buttons]
        assert "사용가능 로봇" in labels
        assert "대기 작업" in labels
        assert "진행 중 작업" in labels
        assert "경고/오류" in labels
        assert "현재 요청된 작업을 상태별로 분류해 보여줍니다." not in labels

        map_flow_row = page.findChild(QFrame, "homeMapFlowRow")
        map_panel = page.findChild(QFrame, "homeOperationMapPanel")
        flow_panel = page.findChild(QFrame, "homeTaskFlowPanel")
        map_canvas = page.findChild(QFrame, "homeOperationMapCanvas")
        assert map_flow_row is not None
        assert map_panel is not None
        assert flow_panel is not None
        assert map_canvas is not None
        assert map_panel.parentWidget() is map_flow_row
        assert flow_panel.parentWidget() is map_flow_row
        map_flow_layout = map_flow_row.layout()
        assert map_flow_layout.stretch(0) == map_flow_layout.stretch(1) == 1
        assert map_panel.minimumWidth() == flow_panel.minimumWidth()
        assert map_panel.maximumWidth() == flow_panel.maximumWidth()
        assert 400 <= map_panel.minimumWidth() <= 440
        assert map_panel.maximumWidth() > 10_000
        row_content_width = map_flow_row.contentsRect().width()
        combined_panel_width = (
            map_panel.width() + flow_panel.width() + map_flow_layout.spacing()
        )
        assert abs(combined_panel_width - row_content_width) <= 2
        assert abs(map_panel.width() - flow_panel.width()) <= 1
        assert map_panel.minimumHeight() == map_panel.maximumHeight()
        assert flow_panel.minimumHeight() == flow_panel.maximumHeight()
        assert map_panel.minimumHeight() == flow_panel.minimumHeight()
        assert "운영 맵" in labels

        flow_scroll = page.findChild(QScrollArea, "flowBoardScroll")
        assert flow_scroll is not None
        assert flow_scroll.parentWidget() is flow_panel
        assert flow_scroll.widgetResizable() is True
        assert flow_scroll.maximumHeight() < flow_panel.maximumHeight()
        assert isinstance(flow_scroll.widget().layout(), QVBoxLayout)
    finally:
        page.close()


def test_home_dashboard_map_canvas_uses_loaded_map_ratio_without_dark_letterbox():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.home_map_canvas.resize(528, 280)
        page.apply_home_map_data(
            {
                "selected_map_id": "map_test12_0506",
                "map_assets": _map_assets(
                    "map_test12_0506",
                    width=105,
                    height=59,
                ),
            },
            robots=[],
        )

        expected_height = round(528 * 59 / 105)
        assert page.home_map_canvas.background_color.name().upper() == "#FFFFFF"
        assert abs(page.home_map_canvas.height() - expected_height) <= 1
    finally:
        page.close()


def test_home_dashboard_map_canvas_scales_down_inside_equal_height_panel():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    page.resize(1600, 1000)
    page.show()
    app.processEvents()

    try:
        page.apply_home_map_data(
            {
                "selected_map_id": "map_test12_0506",
                "map_assets": _map_assets(
                    "map_test12_0506",
                    width=105,
                    height=59,
                ),
            },
            robots=[],
        )
        app.processEvents()

        map_panel = page.findChild(QFrame, "homeOperationMapPanel")
        flow_panel = page.findChild(QFrame, "homeTaskFlowPanel")
        map_canvas = page.findChild(QFrame, "homeOperationMapCanvas")
        assert map_panel.width() == flow_panel.width()
        assert map_panel.height() == flow_panel.height()
        assert map_canvas.y() + map_canvas.height() <= map_panel.height()
        assert map_canvas.width() > map_canvas.height()
    finally:
        page.close()


def test_home_dashboard_map_uses_dashboard_robot_pose_and_db_assets():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        robots = [
            {
                "robot_id": "pinky2",
                "connection_status": "ONLINE",
                "current_pose": {
                    "map_id": "map_0504",
                    "x": 1.0,
                    "y": 1.0,
                    "yaw": 0.5,
                },
            },
            {
                "robot_id": "pinky3",
                "connection_status": "ONLINE",
                "current_pose": {
                    "map_id": "map_other",
                    "x": 2.0,
                    "y": 2.0,
                    "yaw": 0.0,
                },
            },
        ]

        page.apply_home_map_data(
            {
                "selected_map_id": "map_0504",
                "map_assets": _map_assets("map_0504"),
            },
            robots=robots,
        )

        assert page.home_map_canvas.map_loaded is True
        assert page.home_map_canvas.visible_robot_ids == ["pinky2"]
        assert "map_0504" in page.home_map_status_label.text()
        assert "표시 1대 / 전체 2대" in page.home_map_status_label.text()
    finally:
        page.close()


def test_home_dashboard_load_worker_attaches_db_backed_map_assets(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.home_dashboard_page as home_dashboard_page
    from ui.utils.pages.caregiver.home_dashboard_page import DashboardLoadWorker

    calls = []
    pgm_bytes = _map_assets("map_0504")["pgm_bytes"]

    class FakeCaregiverRemoteService:
        def get_dashboard_bundle(self):
            calls.append("get_dashboard_bundle")
            return {
                "summary": {},
                "robots": [
                    {
                        "robot_id": "pinky2",
                        "connection_status": "ONLINE",
                        "current_pose": {
                            "map_id": "map_0504",
                            "x": 1.0,
                            "y": 1.0,
                        },
                    }
                ],
                "flow_data": {
                    "IN_PROGRESS": [
                        {
                            "task_id": 100,
                            "task_type": "DELIVERY",
                            "task_status": "RUNNING",
                        }
                    ]
                },
                "timeline_rows": [],
            }

    class FakeCoordinateConfigRemoteService:
        def list_map_profiles(self):
            calls.append("list_map_profiles")
            return {
                "result_code": "OK",
                "map_profiles": [
                    {
                        "map_id": "map_0504",
                        "map_name": "patrol map",
                        "is_active": True,
                    }
                ],
            }

        def get_map_asset(self, *, asset_type, map_id=None, encoding=None):
            calls.append(f"get_map_asset:{asset_type}:{map_id}:{encoding}")
            if asset_type == "YAML":
                return {
                    "result_code": "OK",
                    "content_text": _map_assets("map_0504")["yaml_text"],
                    "sha256": "map_0504-yaml",
                }
            return {
                "result_code": "OK",
                "content_base64": base64.b64encode(pgm_bytes).decode("ascii"),
                "sha256": "map_0504-pgm",
            }

    monkeypatch.setattr(
        home_dashboard_page,
        "CaregiverRemoteService",
        FakeCaregiverRemoteService,
    )
    monkeypatch.setattr(
        home_dashboard_page,
        "CoordinateConfigRemoteService",
        FakeCoordinateConfigRemoteService,
    )
    monkeypatch.setattr(
        home_dashboard_page,
        "send_request",
        lambda _code, _payload: {"ok": True, "payload": {}},
    )

    worker = DashboardLoadWorker()
    emitted = []
    worker.finished.connect(lambda *args: emitted.append(args))

    worker.run()

    assert emitted[0][0] is True
    assert emitted[0][2][0]["robot_id"] == "pinky2"
    assert emitted[0][3]["IN_PROGRESS"][0]["task_id"] == 100
    map_data = emitted[0][6]
    assert map_data["selected_map_id"] == "map_0504"
    assert map_data["map_assets"]["pgm_bytes"] == pgm_bytes
    assert calls == [
        "get_dashboard_bundle",
        "list_map_profiles",
        "get_map_asset:YAML:map_0504:TEXT",
        "get_map_asset:PGM:map_0504:BASE64",
    ]


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


def test_home_dashboard_starts_lightweight_system_status_poll_timer():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(
        autoload=False,
        auto_system_status_poll=True,
        system_status_poll_interval_ms=1234,
    )

    try:
        assert page.system_status_timer.interval() == 1234
        assert page.system_status_timer.isActive() is True
    finally:
        page.close()


def test_home_dashboard_refreshes_header_status_without_dashboard_reload(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.home_dashboard_page as home_dashboard_page
    from ui.utils.pages.caregiver.home_dashboard_page import (
        CaregiverHomePage,
        HomeSystemStatusWorker,
    )

    page = CaregiverHomePage(autoload=False, auto_system_status_poll=False)
    workers = []

    try:
        def fake_start_worker_thread(
            parent,
            *,
            worker,
            finished_handler=None,
            clear_handler=None,
            worker_signal_connections=None,
        ):
            assert parent is page
            assert isinstance(worker, HomeSystemStatusWorker)
            assert worker_signal_connections is None
            workers.append(worker)
            finished_handler(
                {
                    "관제 서버": "online",
                    "데이터베이스": "online",
                    "ROS2": "online",
                    "AI 서버": "disabled",
                }
            )
            return object(), worker

        monkeypatch.setattr(
            home_dashboard_page,
            "start_worker_thread",
            fake_start_worker_thread,
        )
        page.load_dashboard_data = lambda: (_ for _ in ()).throw(
            AssertionError("system status refresh must not reload dashboard data")
        )

        page._refresh_system_statuses()

        labels = _label_texts(page)
        assert len(workers) == 1
        assert "ROS2 정상" in labels
        assert "AI 서버 미연동" in labels
    finally:
        page.system_status_thread = None
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
        assert page.kpi_cards["available_robots"].objectName() == "homeKpiCard"
        assert page.kpi_cards["available_robots"].property("tone") == "teal"
        assert page.kpi_cards["waiting_tasks"].property("tone") == "amber"
        assert page.kpi_cards["running_tasks"].property("tone") == "green"
        assert page.kpi_cards["warning_errors"].property("tone") == "red"
        assert "배차 대기 필요" in labels
        assert "로봇 수행 중" in labels
        assert "운영 확인 필요" in labels
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
                    "display_name": "Pinky Pro",
                    "robot_type": "MOBILE",
                    "capabilities": ["GUIDE", "DELIVERY", "PATROL"],
                    "connection_status": "OFFLINE",
                    "current_location": "좌표 x=1.2, y=0.8",
                    "battery_percent": 87.5,
                    "last_seen_at": "2026-05-03T12:00:00",
                    "chip_type": "red",
                },
                {
                    "robot_id": "jetcobot1",
                    "display_name": "JetCobot",
                    "robot_type": "ARM",
                    "capabilities": ["MANIPULATION"],
                    "connection_status": "ONLINE",
                    "current_location": "-",
                    "battery_percent": None,
                    "last_seen_at": "2026-05-03T12:01:00",
                    "chip_type": "green",
                },
            ]
        )

        labels = _label_texts(page)
        cards = [
            frame
            for frame in page.findChildren(QFrame)
            if frame.objectName() == "homeRobotCard"
        ]
        assert len(cards) == 2
        assert cards[0].property("connection_status") == "offline"
        assert "pinky2" in labels
        assert "jetcobot1" in labels
        assert "Pinky Pro · pinky2" not in labels
        assert "JetCobot · jetcobot1" not in labels
        assert "구분" in labels
        assert "MOBILE" in labels
        assert "지원 기능" in labels
        assert "GUIDE, DELIVERY, PATROL" in labels
        assert "현재 작업" in labels
        assert "위치" in labels
        assert "좌표 x=1.2, y=0.8" in labels
        assert "88%" in labels
        assert "-" in labels
        assert "마지막 수신" in labels
        assert "2026.05.03 12:00" in labels
        assert any(
            label.objectName() == "homeRobotFieldKey" and label.text() == "위치"
            for label in page.findChildren(QLabel)
        )
        assert any(
            label.objectName() == "homeRobotFieldValue"
            and label.text() == "좌표 x=1.2, y=0.8"
            for label in page.findChildren(QLabel)
        )
        assert not any("현재 구역:" in text for text in labels)
        assert not any("T12:00:00" in text for text in labels)
        assert not any("192.168." in text for text in labels)
    finally:
        page.close()


def test_home_dashboard_patches_robot_board_from_robot_stream_event():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        page.apply_robot_board_data(
            [
                {
                    "robot_id": "pinky2",
                    "robot_type": "MOBILE",
                    "capabilities": ["DELIVERY"],
                    "connection_status": "OFFLINE",
                    "current_location": "위치 미수신",
                    "battery_percent": 10,
                    "current_task_id": None,
                    "last_seen_at": "2026-05-11T19:00:00",
                    "chip_type": "red",
                }
            ]
        )
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        page.apply_stream_event(
            {
                "event_type": "PINKY_UPDATED",
                "payload": {
                    "pinky_id": "pinky2",
                    "connection_status": "ONLINE",
                    "runtime_state": "RUNNING",
                    "battery_percent": 54.4,
                    "active_task_id": 301,
                    "zone_name": "303호 앞",
                    "last_seen_at": "2026-05-11T20:15:54",
                },
            }
        )

        card = page.robot_row.itemAt(0).widget()
        labels = _label_texts(card)
        assert refresh_calls == []
        assert page.robot_row.count() == 1
        assert card.property("connection_status") == "online"
        assert "ONLINE" in labels
        assert "303호 앞" in labels
        assert "54%" in labels
        assert "301" in labels
        assert "2026.05.11 20:15" in labels
        assert "OFFLINE" not in labels
        assert "위치 미수신" not in labels
    finally:
        page.close()


def test_home_dashboard_patches_map_pose_from_action_feedback_stream_event():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        robots = [
            {
                "robot_id": "pinky2",
                "robot_type": "MOBILE",
                "capabilities": ["DELIVERY"],
                "connection_status": "ONLINE",
                "runtime_state": "RUNNING",
                "current_location": "좌표 x=1.00, y=1.00",
                "current_pose": {
                    "map_id": "map_0504",
                    "frame_id": "map",
                    "x": 1.0,
                    "y": 1.0,
                    "yaw": 0.0,
                },
                "current_task_id": 300,
                "last_seen_at": "2026-05-11T20:15:00",
            }
        ]
        page.apply_robot_board_data(robots)
        page.apply_home_map_data(
            {
                "selected_map_id": "map_0504",
                "map_assets": _map_assets("map_0504"),
            },
            robots=robots,
        )
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        page.apply_stream_event(
            {
                "event_type": "ACTION_FEEDBACK_UPDATED",
                "payload": {
                    "task_id": 301,
                    "action_name": "/ropi/control/pinky2/navigate_to_goal",
                    "feedback_type": "NAVIGATION_FEEDBACK",
                    "current_pose": {
                        "map_id": "map_0504",
                        "frame_id": "map",
                        "x": 2.5,
                        "y": 1.5,
                        "yaw": 0.2,
                    },
                    "distance_remaining_m": 1.25,
                    "received_at": "2026-05-11T20:15:54+00:00",
                },
            }
        )

        card = page.robot_row.itemAt(0).widget()
        labels = _label_texts(card)
        assert refresh_calls == []
        assert page.home_map_canvas.visible_robot_ids == ["pinky2"]
        assert page._last_robots[0]["current_task_id"] == 301
        assert page._last_robots[0]["current_pose"] == {
            "map_id": "map_0504",
            "frame_id": "map",
            "x": 2.5,
            "y": 1.5,
            "yaw": 0.2,
            "updated_at": "2026-05-11T20:15:54+00:00",
        }
        assert "좌표 x=2.50, y=1.50" in labels
    finally:
        page.close()


def test_home_dashboard_schedules_refresh_from_admin_stream_events():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    calls = []

    try:
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: calls.append("refresh")

        page.apply_stream_event(
            {"event_type": "TASK_UPDATED", "payload": {"task_id": 1}}
        )
        page.apply_stream_event({"event_type": "IGNORED", "payload": {}})

        assert calls == ["refresh"]
    finally:
        page.close()


def test_home_dashboard_defers_stream_refresh_while_hidden_until_shown(monkeypatch):
    app = _app()

    import ui.utils.pages.caregiver.home_dashboard_page as home_dashboard_page
    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    scheduled_callbacks = []
    load_calls = []

    try:
        monkeypatch.setattr(
            home_dashboard_page.QTimer,
            "singleShot",
            lambda _delay, callback: scheduled_callbacks.append(callback),
        )
        page.load_dashboard_data = lambda: load_calls.append("load")

        page.apply_stream_event(
            {"event_type": "TASK_UPDATED", "payload": {"task_id": 1}}
        )

        assert scheduled_callbacks == []
        assert load_calls == []
        assert page._deferred_stream_refresh is True

        page.show()
        app.processEvents()

        assert scheduled_callbacks == [page._run_stream_refresh]
        assert page._deferred_stream_refresh is False

        scheduled_callbacks.pop()()

        assert load_calls == ["load"]
    finally:
        page.close()


def test_home_dashboard_defers_stream_refresh_while_snapshot_load_is_running(
    monkeypatch,
):
    app = _app()

    import ui.utils.pages.caregiver.home_dashboard_page as home_dashboard_page
    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    scheduled_callbacks = []
    load_calls = []

    try:
        page.show()
        app.processEvents()
        monkeypatch.setattr(
            home_dashboard_page.QTimer,
            "singleShot",
            lambda _delay, callback: scheduled_callbacks.append(callback),
        )
        page.load_dashboard_data = lambda: load_calls.append("load")
        page.dashboard_thread = object()
        page._stream_refresh_pending = True

        page._run_stream_refresh()

        assert page._stream_refresh_pending is True
        assert load_calls == []
        assert scheduled_callbacks == [page._run_stream_refresh]

        page.dashboard_thread = None
        scheduled_callbacks.pop()()

        assert page._stream_refresh_pending is False
        assert load_calls == ["load"]
    finally:
        page.close()


def test_home_dashboard_normalizes_task_flow_into_compact_one_column_list():
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

        task_titles = [
            label.text()
            for label in page.findChildren(QLabel)
            if label.objectName() == "homeTaskTitle"
        ]
        assert page.findChildren(FlowColumn) == []
        assert page.flow_count_label.text() == "5건"
        assert task_titles == [
            "작업 #104 · 순찰",
            "작업 #103 · 운반",
            "작업 #102 · 순찰",
            "작업 #101 · 운반",
            "작업 #105 · 운반",
        ]
    finally:
        page.close()


def test_home_dashboard_renders_rejected_guide_without_stale_ready_phase():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_flow_board_data(
            {
                "IN_PROGRESS": [
                    {
                        "task_id": 709,
                        "task_type": "GUIDE",
                        "task_status": "RUNNING",
                        "phase": "READY_TO_START_GUIDANCE",
                        "assigned_robot_id": "pinky1",
                        "result_code": "REJECTED",
                        "latest_reason_code": "GUIDE_STATE_MISMATCH",
                        "description": "안내 주행을 시작할 수 없는 상태입니다.",
                    }
                ]
            }
        )

        labels = _label_texts(page)
        assert "작업 #709 · 안내" in labels
        assert "실패" in labels
        assert "안내 시작 준비" not in labels
        assert "READY_TO_START_GUIDANCE" not in labels
        assert "안내 상태 불일치" in labels
    finally:
        page.close()


def test_home_dashboard_patches_existing_task_flow_from_task_stream_event():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import (
        CaregiverHomePage,
    )

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        page.apply_summary_data(
            {
                "available_robot_count": 1,
                "total_robot_count": 2,
                "waiting_job_count": 1,
                "running_job_count": 1,
                "warning_error_count": 0,
            }
        )
        page.apply_flow_board_data(
            {
                "WAITING": [
                    {
                        "task_id": 101,
                        "task_type": "DELIVERY",
                        "task_status": "WAITING_DISPATCH",
                        "phase": "WAITING_DISPATCH",
                        "robot_id": None,
                        "description": "accepted",
                    }
                ],
                "IN_PROGRESS": [
                    {
                        "task_id": 102,
                        "task_type": "PATROL",
                        "task_status": "RUNNING",
                        "phase": "RUNNING",
                        "robot_id": "pinky3",
                        "description": "patrolling",
                    }
                ],
            }
        )
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": 101,
                    "task_type": "DELIVERY",
                    "task_status": "RUNNING",
                    "phase": "MOVE_TO_DESTINATION",
                    "assigned_robot_id": "pinky2",
                    "result_message": "moving to destination",
                    "cancellable": True,
                },
            }
        )

        labels = _label_texts(page.findChild(QFrame, "homeTaskFlowPanel"))
        assert refresh_calls == []
        assert page.flow_count_label.text() == "2건"
        assert page.kpi_cards["waiting_tasks"].value_label.text() == "0건"
        assert page.kpi_cards["running_tasks"].value_label.text() == "2건"
        assert "작업 #101 · 운반" in labels
        assert "진행 중" in labels
        assert "목적지 이동" in labels
        assert "pinky2" in labels
        assert "moving to destination" in labels
    finally:
        page.close()


def test_home_dashboard_adds_new_task_from_task_stream_event():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import (
        CaregiverHomePage,
    )

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        page.apply_summary_data(
            {
                "available_robot_count": 1,
                "total_robot_count": 2,
                "waiting_job_count": 0,
                "running_job_count": 0,
                "warning_error_count": 0,
            }
        )
        page.apply_flow_board_data({})
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": 301,
                    "task_type": "DELIVERY",
                    "task_status": "WAITING_DISPATCH",
                    "phase": "WAITING_DISPATCH",
                    "assigned_robot_id": "pinky2",
                    "result_message": "운반 요청 접수",
                    "cancellable": True,
                },
            }
        )

        labels = _label_texts(page.findChild(QFrame, "homeTaskFlowPanel"))
        assert refresh_calls == []
        assert page.flow_count_label.text() == "1건"
        assert page.kpi_cards["waiting_tasks"].value_label.text() == "1건"
        assert page.kpi_cards["running_tasks"].value_label.text() == "0건"
        assert "작업 #301 · 운반" in labels
        assert "배차 대기" in labels
        assert "pinky2" in labels
        assert "운반 요청 접수" in labels
    finally:
        page.close()


def test_home_dashboard_patches_warning_kpi_and_timeline_from_alert_stream_event():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        page.apply_summary_data(
            {
                "available_robot_count": 1,
                "total_robot_count": 2,
                "waiting_job_count": 0,
                "running_job_count": 1,
                "warning_error_count": 0,
            }
        )
        page.apply_timeline_data(
            [
                {
                    "occurred_at": "2026-05-11T20:00:00",
                    "task_id": 100,
                    "event_type": "TASK_UPDATED",
                    "message": "기존 이벤트",
                }
            ]
        )
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        event = {
            "event_type": "ALERT_CREATED",
            "payload": {
                "alert_id": "fall-17",
                "task_id": 2001,
                "pinky_id": "pinky3",
                "zone_name": "3층 복도",
                "result_seq": 44,
                "occurred_at": "2026-05-11T20:15:54",
                "message": "낙상 의심 알림",
            },
        }

        page.apply_stream_event(event)
        page.apply_stream_event(event)

        assert refresh_calls == []
        assert page.kpi_cards["warning_errors"].value_label.text() == "1건"
        assert page.timeline_table.rowCount() == 2
        assert page.timeline_table.item(0, 0).text() == "2026.05.11 20:15"
        assert page.timeline_table.item(0, 1).text() == "2001"
        assert page.timeline_table.item(0, 2).text() == "ALERT_CREATED"
        assert page.timeline_table.item(0, 3).text() == "낙상 의심 알림"
        assert page.timeline_table.item(1, 3).text() == "기존 이벤트"
    finally:
        page.close()


def test_home_dashboard_patches_alert_carried_by_task_updated_without_reload():
    app = _app()

    from ui.utils.pages.caregiver.home_dashboard_page import (
        CaregiverHomePage,
    )

    page = CaregiverHomePage(autoload=False)
    refresh_calls = []

    try:
        page.apply_summary_data(
            {
                "available_robot_count": 1,
                "total_robot_count": 2,
                "waiting_job_count": 0,
                "running_job_count": 1,
                "warning_error_count": 0,
            }
        )
        page.apply_flow_board_data(
            {
                "IN_PROGRESS": [
                    {
                        "task_id": 2001,
                        "task_type": "PATROL",
                        "task_status": "RUNNING",
                        "phase": "RUNNING",
                        "robot_id": "pinky3",
                        "description": "patrolling",
                    }
                ]
            }
        )
        page.apply_timeline_data([])
        page.show()
        app.processEvents()
        page._schedule_stream_refresh = lambda: refresh_calls.append("refresh")

        page.apply_stream_event(
            {
                "event_type": "TASK_UPDATED",
                "payload": {
                    "task_id": 2001,
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "phase": "WAIT_FALL_RESPONSE",
                    "assigned_robot_id": "pinky3",
                    "result_message": "낙상 대응 시작",
                    "fall_alert": {
                        "alert_id": "fall-18",
                        "zone_name": "3층 복도",
                        "result_seq": 45,
                    },
                },
            }
        )

        flow_labels = _label_texts(page.findChild(QFrame, "homeTaskFlowPanel"))
        assert refresh_calls == []
        assert page.kpi_cards["warning_errors"].value_label.text() == "1건"
        assert page.timeline_table.rowCount() == 1
        assert page.timeline_table.item(0, 1).text() == "2001"
        assert page.timeline_table.item(0, 2).text() == "FALL_ALERT_CREATED"
        assert page.timeline_table.item(0, 3).text() == "낙상 대응 시작"
        assert "낙상 대응 대기" in flow_labels
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


def test_home_dashboard_task_cards_use_operator_labels_instead_of_raw_codes():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page.apply_flow_board_data(
            {
                "WAITING": [
                    {
                        "task_id": 6,
                        "task_type": "DELIVERY",
                        "task_status": "WAITING_DISPATCH",
                        "robot_id": None,
                        "phase": "MOVE_TO_PICKUP",
                        "destination_label": "301호",
                        "description": (
                            "ROS service command failed: execute_patrol_path: "
                            "[Errno 2] No such file or directory"
                        ),
                    }
                ]
            }
        )

        labels = _label_texts(page)
        assert "작업 #6 · 운반" in labels
        assert "배차 대기" in labels
        assert "로봇" in labels
        assert "미배정" in labels
        assert "단계" in labels
        assert "픽업 지점 이동" in labels
        assert "목적지" in labels
        assert "301호" in labels
        assert "최근" in labels
        assert "ROS 브릿지에 연결할 수 없습니다." in labels
        assert any(text.startswith("ROS service command failed") for text in labels)
        key_labels = [
            label
            for label in page.findChildren(QLabel)
            if label.objectName() == "homeTaskFieldKey"
        ]
        value_labels = [
            label
            for label in page.findChildren(QLabel)
            if label.objectName() == "homeTaskFieldValue"
        ]
        detail_labels = [
            label
            for label in page.findChildren(QLabel)
            if label.objectName() == "homeTaskFieldDetail"
        ]
        assert [label.text() for label in key_labels] == [
            "로봇",
            "단계",
            "목적지",
            "최근",
            "상세",
        ]
        assert any(label.text() == "미배정" for label in value_labels)
        assert any(
            label.text().startswith("ROS service command failed")
            for label in detail_labels
        )
        assert not any("로봇: 미배정" in text for text in labels)
        assert not any("#6 DELIVERY / WAITING_DISPATCH" in text for text in labels)
    finally:
        page.close()


def test_home_dashboard_cancel_failure_uses_structured_operator_banner():
    _app()

    from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage

    page = CaregiverHomePage(autoload=False)

    try:
        page._handle_task_cancel_finished(
            False,
            {
                "result_code": "CLIENT_ERROR",
                "reason_code": "ROS_SERVICE_UNAVAILABLE",
                "result_message": (
                    "ROS service command failed: cancel_action: "
                    "[Errno 2] No such file or directory"
                ),
                "cancel_requested": False,
            },
        )

        labels = _label_texts(page)
        assert "작업 취소 실패" in labels
        assert "ROS 브릿지에 연결할 수 없습니다." in labels
        assert page.status_banner.parentWidget() is page
        assert page.status_banner.parentWidget().objectName() != "homeTimeCard"
        assert any(
            text.startswith("상세: ROS service command failed") for text in labels
        )
        assert not any(
            "CLIENT_ERROR / ROS_SERVICE_UNAVAILABLE" in text for text in labels
        )
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
    worker.finished.connect(
        lambda success, response: emitted.append((success, response))
    )

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
