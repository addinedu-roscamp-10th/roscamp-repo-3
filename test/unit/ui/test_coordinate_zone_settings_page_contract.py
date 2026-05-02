import base64
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


def _sample_bundle():
    return {
        "result_code": "OK",
        "generated_at": "2026-05-02T03:10:00Z",
        "map_profile": {
            "map_id": "map_test",
            "map_name": "테스트 맵",
            "map_revision": 3,
            "frame_id": "map",
            "yaml_path": "maps/map_test.yaml",
            "pgm_path": "maps/map_test.pgm",
            "is_active": True,
        },
        "operation_zones": [
            {
                "zone_id": "room_301",
                "zone_name": "301호",
                "zone_type": "ROOM",
                "revision": 1,
                "is_enabled": True,
            }
        ],
        "goal_poses": [
            {
                "goal_pose_id": "delivery_room_301",
                "zone_id": "room_301",
                "zone_name": "301호",
                "purpose": "DESTINATION",
                "pose_x": 1.7,
                "pose_y": 0.02,
                "pose_yaw": 0.0,
                "frame_id": "map",
                "is_enabled": True,
            }
        ],
        "patrol_areas": [
            {
                "patrol_area_id": "patrol_ward_night_01",
                "patrol_area_name": "야간 병동 순찰",
                "revision": 7,
                "waypoint_count": 2,
                "path_frame_id": "map",
                "is_enabled": False,
            }
        ],
    }


def _sample_map_assets():
    pgm_bytes = b"P5\n2 2\n255\n\x00\x80\xc0\xff"
    return {
        "yaml_text": "image: map.pgm\nresolution: 0.02\norigin: [0.0, 0.0, 0.0]\n",
        "pgm_bytes": pgm_bytes,
        "yaml_sha256": "yaml-sha",
        "pgm_sha256": "pgm-sha",
    }


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


def test_coordinate_config_load_worker_fetches_bundle_and_assets():
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateConfigLoadWorker,
    )

    calls = []
    pgm_bytes = b"P5\n2 1\n255\n\x00\xff"

    class FakeCoordinateService:
        def get_active_map_bundle(self, *, include_disabled, include_patrol_paths):
            calls.append(
                (
                    "get_active_map_bundle",
                    include_disabled,
                    include_patrol_paths,
                )
            )
            return _sample_bundle()

        def get_map_asset(self, *, asset_type, map_id=None, encoding=None):
            calls.append(("get_map_asset", asset_type, map_id, encoding))
            if asset_type == "YAML":
                return {
                    "result_code": "OK",
                    "content_text": (
                        "image: map.pgm\nresolution: 0.02\norigin: [0, 0, 0]\n"
                    ),
                    "sha256": "yaml-sha",
                }
            return {
                "result_code": "OK",
                "content_base64": base64.b64encode(pgm_bytes).decode("ascii"),
                "sha256": "pgm-sha",
            }

    emitted = []
    worker = CoordinateConfigLoadWorker(service_factory=FakeCoordinateService)
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))

    worker.run()

    assert calls == [
        ("get_active_map_bundle", True, True),
        ("get_map_asset", "YAML", "map_test", "TEXT"),
        ("get_map_asset", "PGM", "map_test", "BASE64"),
    ]
    assert emitted[0][0] is True
    assert emitted[0][1]["bundle"]["map_profile"]["map_id"] == "map_test"
    assert emitted[0][1]["pgm_bytes"] == pgm_bytes
    assert emitted[0][1]["yaml_sha256"] == "yaml-sha"


def test_coordinate_zone_settings_page_applies_loaded_bundle_and_map_assets():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )

    page = CoordinateZoneSettingsPage()

    try:
        page.apply_loaded_coordinate_config(
            {
                "bundle": _sample_bundle(),
                **_sample_map_assets(),
            }
        )

        assert page.active_map_labels["map_id"].text() == "map_test"
        assert page.map_canvas.map_loaded is True
        assert page.map_canvas.map_image_size == (2, 2)

        zone_table = page.findChild(QTableWidget, "operationZoneTable")
        goal_table = page.findChild(QTableWidget, "goalPoseTable")
        patrol_table = page.findChild(QTableWidget, "patrolAreaTable")

        assert zone_table.rowCount() == 1
        assert zone_table.item(0, 0).text() == "room_301"
        assert zone_table.item(0, 3).text() == "활성"
        assert goal_table.item(0, 0).text() == "delivery_room_301"
        assert goal_table.item(0, 3).text() == "x=1.70, y=0.02, yaw=0.00"
        assert patrol_table.item(0, 0).text() == "patrol_ward_night_01"
        assert patrol_table.item(0, 3).text() == "비활성"
        assert page.validation_message_label.text() == "맵과 좌표 설정을 불러왔습니다."
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_shows_map_asset_error_without_save():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )

    page = CoordinateZoneSettingsPage()

    try:
        page.apply_load_error("MAP_ASSET_UNAVAILABLE: 맵 asset 파일을 읽을 수 없습니다.")

        assert page.map_canvas.map_loaded is False
        assert page.save_button.isEnabled() is False
        assert "MAP_ASSET_UNAVAILABLE" in page.validation_message_label.text()
    finally:
        page.close()


def test_coordinate_zone_settings_page_shutdown_stops_running_load_thread():
    _app()

    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )

    class FakeThread:
        def __init__(self):
            self.quit_called = False
            self.wait_timeout = None

        def isRunning(self):
            return True

        def quit(self):
            self.quit_called = True

        def wait(self, timeout):
            self.wait_timeout = timeout
            return True

    page = CoordinateZoneSettingsPage()
    fake_thread = FakeThread()
    page.load_thread = fake_thread
    page.load_worker = object()

    try:
        page.shutdown()

        assert fake_thread.quit_called is True
        assert fake_thread.wait_timeout == page._worker_stop_wait_ms
        assert page.load_thread is None
        assert page.load_worker is None
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
