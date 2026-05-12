import os
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame


_APP = None
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _display_texts(widget) -> list[str]:
    label_texts = [label.text() for label in widget.findChildren(QLabel)]
    button_texts = [button.text() for button in widget.findChildren(QPushButton)]
    return label_texts + button_texts


def test_admin_demo_fixture_uses_ropi_product_labels_and_korean_values():
    from ui.presentation_demo.admin_demo_data import (
        build_admin_demo_snapshot,
        forbidden_internal_tokens,
        forbidden_raw_enum_tokens,
        visible_snapshot_texts,
    )

    snapshot = build_admin_demo_snapshot()

    assert [robot.display_id for robot in snapshot.robots] == [
        "ROPI 1",
        "ROPI 2",
        "ROPI 3",
    ]
    assert [marker.display_id for marker in snapshot.map_markers] == [
        "ROPI 1",
        "ROPI 2",
        "ROPI 3",
    ]
    assert len(snapshot.map_markers) == 3
    marker_by_id = {marker.display_id: marker for marker in snapshot.map_markers}
    assert (marker_by_id["ROPI 2"].x, marker_by_id["ROPI 2"].y) == (0.40, -0.36)
    assert (marker_by_id["ROPI 1"].x, marker_by_id["ROPI 1"].y) == (0.78, 0.04)
    assert (marker_by_id["ROPI 3"].x, marker_by_id["ROPI 3"].y) == (1.36, -0.46)

    visible_text = " ".join(visible_snapshot_texts(snapshot))
    lowered = visible_text.lower()
    assert all(token not in lowered for token in forbidden_internal_tokens())
    assert all(token not in visible_text for token in forbidden_raw_enum_tokens())
    assert {"안내", "운반", "순찰", "진행 중", "주의"}.issubset(
        set(visible_snapshot_texts(snapshot))
    )


def test_admin_demo_window_has_only_presentation_pages_without_control_service():
    _app()

    from ui.presentation_demo.admin_demo_app import create_demo_window

    window = create_demo_window()

    try:
        texts = _display_texts(window)
        text_blob = " ".join(texts)
        lowered = text_blob.lower()

        assert window.NAV_ITEMS == [
            ("home", "홈"),
            ("task_request", "작업 요청"),
            ("task_monitor", "작업 모니터"),
            ("alerts", "알림/로그"),
        ]
        assert window.admin_shell.has_page("home")
        assert window.admin_shell.has_page("task_request")
        assert window.admin_shell.has_page("task_monitor")
        assert window.admin_shell.has_page("alerts")
        assert "좌표/구역 설정" not in texts
        assert "로봇 상태" not in texts
        assert "재고 관리" not in texts
        assert "어르신 정보" not in texts
        assert "ROPI 1" in texts
        assert "ROPI 2" in texts
        assert "ROPI 3" in texts
        assert "지원 기능" not in texts
        assert "현재 ROPI 위치와 진행 중인 업무를 맵 위에 표시합니다." not in texts
        assert "B동 복도" not in texts
        assert "303호 앞" not in texts
        assert {"복도1", "303호", "복도3"}.issubset(set(texts))
        assert any(
            frame.property("presentation_home_map") is True
            for frame in window.findChildren(QFrame)
        )
        assert any(
            frame.property("presentation_compact_flow") is True
            for frame in window.findChildren(QFrame)
        )
        assert window.home_page.flow_scroll.parentWidget().isHidden()
        assert window.map_widget.marker_count == 3
        assert window.map_widget.route_hint_enabled is False
        assert window.map_widget.maximumWidth() <= 560
        assert window.map_widget.maximumHeight() <= 320
        assert window.map_widget.map_loaded is True
        assert window.map_widget.map_image_size is not None
        assert all(
            token not in lowered
            for token in ("pinky", "jetcobot", "arm1", "arm2")
        )
        assert all(
            token not in text_blob
            for token in ("DELIVERY", "PATROL", "GUIDE", "RUNNING", "WARNING")
        )
    finally:
        window.close()


def test_admin_demo_task_request_updates_home_monitor_and_alerts():
    _app()

    from ui.presentation_demo.admin_demo_app import create_demo_window

    window = create_demo_window()

    try:
        initial_count = len(window.store.snapshot.tasks)
        task = window.request_page.submit_demo_request("DELIVERY")

        texts = _display_texts(window)
        text_blob = " ".join(texts)

        assert len(window.store.snapshot.tasks) == initial_count + 1
        assert task.task_id in texts
        assert "작업 생성" in texts
        assert "요청 결과" in texts
        assert "담당 ROPI" in texts
        assert "ROPI 2" in texts
        assert "운반" in texts
        assert "작업 모니터" in texts
        assert "알림/로그" in texts
        assert "진행 중" in texts
        assert "DELIVERY" not in text_blob
        assert "RUNNING" not in text_blob
        assert "pinky2" not in text_blob.lower()

        window.monitor_page.select_task("#1031")
        assert window.monitor_page.selected_task_id == "#1031"
        window.alerts_page.select_event("EV-1032")
        assert window.alerts_page.selected_event_id == "EV-1032"
    finally:
        window.close()


def test_admin_demo_smoke_mode_returns_without_event_loop():
    _app()

    from ui.presentation_demo import admin_demo_app

    admin_demo_app.main(["--smoke"])


def test_admin_demo_window_opens_maximized():
    _app()

    from ui.presentation_demo.admin_demo_app import (
        create_demo_window,
        show_demo_window,
    )

    window = create_demo_window()

    try:
        show_demo_window(window)

        assert window.windowState() & Qt.WindowState.WindowMaximized
        assert window.maximumWidth() > 2000
        assert window.maximumHeight() > 1200
    finally:
        window.close()


def test_admin_demo_has_page_neutral_uv_script_and_tracked_source():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    scripts = pyproject["project"]["scripts"]

    assert scripts["ropi-admin-demo"] == "ui.presentation_demo.admin_demo_app:main"
    assert "ropi-admin-home-demo" not in scripts

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ui/presentation_demo/exports/" in gitignore
    assert "ui/presentation_demo/\n" not in gitignore
    assert "test/unit/ui/test_presentation_admin_demo.py" not in gitignore
