import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_coordinate_zone_settings_page_exposes_phase1_layout_contract():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )
    from ui.utils.widgets.admin_shell import PageHeader
    from ui.utils.widgets.map_canvas import MapCanvasWidget

    page = CoordinateZoneSettingsPage()

    try:
        header = page.findChild(PageHeader, "pageHeader")
        assert header is not None
        assert header.title_label.text() == "좌표/구역 설정"
        assert "DB 기반 운영 좌표" in header.subtitle_label.text()

        refresh_button = page.findChild(QPushButton, "coordinateRefreshButton")
        save_button = page.findChild(QPushButton, "coordinateSaveButton")
        discard_button = page.findChild(QPushButton, "coordinateDiscardButton")
        assert refresh_button.text() == "새로고침"
        assert save_button.text() == "저장"
        assert discard_button.text() == "변경 취소"
        assert save_button.isEnabled() is False
        assert discard_button.isEnabled() is False

        map_canvas = page.findChild(MapCanvasWidget, "coordinateZoneMapCanvas")
        assert map_canvas is not None
        assert map_canvas.map_loaded is False
        assert map_canvas.status_text == "좌표 설정 맵 미수신"

        assert page.findChild(QTableWidget, "operationZoneTable") is not None
        assert page.findChild(QTableWidget, "goalPoseTable") is not None
        assert page.findChild(QTableWidget, "patrolAreaTable") is not None

        labels = _label_texts(page)
        assert "Active Map" in labels
        assert "operation_zone" in labels
        assert "goal_pose" in labels
        assert "patrol_area.path_json" in labels
        assert "Validation" in labels
        assert "맵이 로드되기 전에는 좌표를 저장할 수 없습니다." in labels
    finally:
        page.close()


def test_coordinate_zone_settings_page_accepts_active_map_summary():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )

    page = CoordinateZoneSettingsPage()

    try:
        page.apply_active_map(
            {
                "map_id": "map_test11_0423",
                "map_name": "map_test11_0423",
                "map_revision": 1,
                "frame_id": "map",
                "yaml_path": "maps/map_test11_0423.yaml",
                "pgm_path": "maps/map_test11_0423.pgm",
            }
        )

        assert page.active_map_labels["map_id"].text() == "map_test11_0423"
        assert page.active_map_labels["map_revision"].text() == "1"
        assert page.active_map_labels["frame_id"].text() == "map"
        assert (
            page.active_map_labels["yaml_path"].text()
            == "maps/map_test11_0423.yaml"
        )
    finally:
        page.close()
