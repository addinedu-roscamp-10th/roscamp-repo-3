import base64
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
)


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
                "boundary_json": {
                    "type": "POLYGON",
                    "header": {"frame_id": "map"},
                    "vertices": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 1.0, "y": 0.0},
                        {"x": 1.0, "y": 1.0},
                    ],
                },
                "boundary_vertex_count": 3,
                "boundary_frame_id": "map",
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
                "updated_at": "2026-05-02T03:00:00Z",
            }
        ],
        "patrol_areas": [
            {
                "patrol_area_id": "patrol_ward_night_01",
                "patrol_area_name": "야간 병동 순찰",
                "revision": 7,
                "waypoint_count": 2,
                "path_frame_id": "map",
                "path_json": {
                    "header": {"frame_id": "map"},
                    "poses": [
                        {"x": 0.0, "y": 0.2, "yaw": 0.0},
                        {"x": 1.0, "y": 1.0, "yaw": 1.57},
                    ],
                },
                "is_enabled": False,
            }
        ],
    }


def _sample_map_assets():
    pgm_bytes = b"P5\n2 2\n255\n\x00\x80\xc0\xff"
    return {
        "yaml_text": "image: map.pgm\nresolution: 1.0\norigin: [0.0, 0.0, 0.0]\n",
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
        new_zone_button = page.findChild(QPushButton, "operationZoneNewButton")
        assert new_zone_button.text() == "새 구역"
        assert new_zone_button.parent() is not page.operation_zone_form
        assert page.findChild(QLabel, "coordinateEditModeLabel") is not None

        map_canvas = page.findChild(MapCanvasWidget, "coordinateZoneMapCanvas")
        assert map_canvas is not None
        assert map_canvas.map_loaded is False
        assert map_canvas.status_text == "좌표 설정 맵 미수신"

        assert page.findChild(QTableWidget, "operationZoneTable") is not None
        assert page.findChild(QTableWidget, "goalPoseTable") is not None
        assert page.findChild(QTableWidget, "patrolAreaTable") is not None
        assert page.findChild(QTableWidget, "operationZoneBoundaryTable") is not None

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
        def get_active_map_bundle(
            self,
            *,
            include_disabled,
            include_zone_boundaries,
            include_patrol_paths,
        ):
            calls.append(
                (
                    "get_active_map_bundle",
                    include_disabled,
                    include_zone_boundaries,
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
        ("get_active_map_bundle", True, True, True),
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


def test_coordinate_zone_settings_page_selects_operation_zone_into_edit_form():
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
        page.select_operation_zone(0)

        assert page.selected_edit_type == "operation_zone"
        assert page.operation_zone_mode == "edit"
        assert page.selected_operation_zone["zone_id"] == "room_301"
        assert page.findChild(QLineEdit, "operationZoneIdInput").text() == "room_301"
        assert page.findChild(QLineEdit, "operationZoneIdInput").isReadOnly() is True
        assert page.findChild(QLineEdit, "operationZoneNameInput").text() == "301호"
        assert (
            page.findChild(QComboBox, "operationZoneTypeCombo").currentText()
            == "ROOM"
        )
        assert page.findChild(QCheckBox, "operationZoneEnabledCheck").isChecked() is True
        boundary_table = page.findChild(QTableWidget, "operationZoneBoundaryTable")
        assert boundary_table.rowCount() == 3
        assert boundary_table.item(2, 2).text() == "1.0000"
        assert len(page.map_canvas.zone_boundary_pixel_points) == 3
        assert page.findChild(QLabel, "coordinateEditModeLabel").text() == (
            "구역 boundary 편집 모드"
        )
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_operation_zone_dirty_create_and_discard():
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
        page.start_operation_zone_create()

        zone_id_input = page.findChild(QLineEdit, "operationZoneIdInput")
        zone_name_input = page.findChild(QLineEdit, "operationZoneNameInput")
        zone_type_combo = page.findChild(QComboBox, "operationZoneTypeCombo")
        enabled_check = page.findChild(QCheckBox, "operationZoneEnabledCheck")

        assert page.operation_zone_mode == "create"
        assert zone_id_input.isReadOnly() is False

        zone_id_input.setText("caregiver_room")
        zone_name_input.setText("보호사실")
        zone_type_combo.setCurrentText("STAFF_STATION")
        enabled_check.setChecked(True)

        assert page.operation_zone_dirty is True
        assert page.save_button.isEnabled() is True
        assert page.discard_button.isEnabled() is True

        page.discard_current_edit()

        assert zone_id_input.text() == ""
        assert zone_name_input.text() == ""
        assert page.operation_zone_dirty is False
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_operation_zone_boundary_click_drag_and_discard():
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
        page.select_operation_zone(0)

        page.handle_map_click_for_operation_zone({"x": 0.5, "y": 1.5})

        boundary_table = page.findChild(QTableWidget, "operationZoneBoundaryTable")
        assert boundary_table.rowCount() == 4
        assert boundary_table.item(3, 1).text() == "0.5000"
        assert page.selected_operation_zone_boundary_vertex_index == 3
        assert page.operation_zone_boundary_dirty is True
        assert page.save_button.isEnabled() is True

        page.move_selected_operation_zone_boundary_vertex({"x": 0.25, "y": 1.25})

        assert boundary_table.item(3, 1).text() == "0.2500"
        assert boundary_table.item(3, 2).text() == "1.2500"
        assert page.operation_zone_boundary_vertices[3] == {"x": 0.25, "y": 1.25}

        page.discard_current_edit()

        assert boundary_table.rowCount() == 3
        assert page.operation_zone_boundary_dirty is False
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_operation_zone_save_worker_sends_if_loc_002_and_003_payloads():
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        OperationZoneSaveWorker,
    )

    calls = []

    class FakeCoordinateService:
        def create_operation_zone(self, **payload):
            calls.append(("create", payload))
            return {
                "result_code": "CREATED",
                "operation_zone": {**payload, "revision": 1},
            }

        def update_operation_zone(self, **payload):
            calls.append(("update", payload))
            return {
                "result_code": "UPDATED",
                "operation_zone": {
                    "zone_id": payload["zone_id"],
                    "zone_name": payload["zone_name"],
                    "zone_type": payload["zone_type"],
                    "revision": payload["expected_revision"] + 1,
                    "is_enabled": payload["is_enabled"],
                },
            }

    emitted = []
    create_payload = {
        "zone_id": "caregiver_room",
        "zone_name": "보호사실",
        "zone_type": "STAFF_STATION",
        "map_id": "map_test",
        "is_enabled": True,
    }
    update_payload = {
        "zone_id": "room_301",
        "expected_revision": 1,
        "zone_name": "301호",
        "zone_type": "ROOM",
        "is_enabled": False,
    }

    create_worker = OperationZoneSaveWorker(
        mode="create",
        payload=create_payload,
        service_factory=FakeCoordinateService,
    )
    update_worker = OperationZoneSaveWorker(
        mode="edit",
        payload=update_payload,
        service_factory=FakeCoordinateService,
    )
    create_worker.finished.connect(lambda ok, response: emitted.append((ok, response)))
    update_worker.finished.connect(lambda ok, response: emitted.append((ok, response)))

    create_worker.run()
    update_worker.run()

    assert calls == [
        ("create", create_payload),
        ("update", update_payload),
    ]
    assert emitted[0][0] is True
    assert emitted[0][1]["operation_zone"]["zone_id"] == "caregiver_room"
    assert emitted[1][0] is True
    assert emitted[1][1]["operation_zone"]["revision"] == 2


def test_operation_zone_boundary_save_worker_sends_if_loc_007_payload():
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        OperationZoneBoundarySaveWorker,
    )

    calls = []

    class FakeCoordinateService:
        def update_operation_zone_boundary(self, **payload):
            calls.append(payload)
            return {
                "result_code": "UPDATED",
                "operation_zone": {
                    "zone_id": payload["zone_id"],
                    "revision": payload["expected_revision"] + 1,
                    "boundary_json": payload["boundary_json"],
                },
            }

    payload = {
        "zone_id": "room_301",
        "expected_revision": 1,
        "boundary_json": {
            "type": "POLYGON",
            "header": {"frame_id": "map"},
            "vertices": [
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
            ],
        },
    }
    emitted = []
    worker = OperationZoneBoundarySaveWorker(
        payload=payload,
        service_factory=FakeCoordinateService,
    )
    worker.finished.connect(lambda ok, response: emitted.append((ok, response)))

    worker.run()

    assert calls == [payload]
    assert emitted[0][0] is True
    assert emitted[0][1]["operation_zone"]["revision"] == 2


def test_coordinate_zone_settings_page_applies_operation_zone_save_success():
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
        page.select_operation_zone(0)
        page._handle_operation_zone_save_finished(
            True,
            {
                "result_code": "UPDATED",
                "operation_zone": {
                    "zone_id": "room_301",
                    "zone_name": "301호",
                    "zone_type": "ROOM",
                    "revision": 2,
                    "is_enabled": False,
                },
            },
        )

        zone_table = page.findChild(QTableWidget, "operationZoneTable")
        assert zone_table.item(0, 0).text() == "room_301"
        assert zone_table.item(0, 3).text() == "비활성"
        assert page.selected_operation_zone["revision"] == 2
        assert page.operation_zone_dirty is False
        assert page.validation_message_label.text() == "운영 구역을 저장했습니다."

        page.start_operation_zone_create()
        page._handle_operation_zone_save_finished(
            True,
            {
                "result_code": "CREATED",
                "operation_zone": {
                    "zone_id": "caregiver_room",
                    "zone_name": "보호사실",
                    "zone_type": "STAFF_STATION",
                    "revision": 1,
                    "is_enabled": True,
                },
            },
        )

        assert zone_table.rowCount() == 2
        assert zone_table.item(1, 0).text() == "caregiver_room"
        assert page.findChild(QComboBox, "goalPoseZoneCombo").findData(
            "caregiver_room"
        ) >= 0
    finally:
        page.close()


def test_coordinate_zone_settings_page_applies_operation_zone_boundary_save_success():
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
        page.select_operation_zone(0)
        page.handle_map_click_for_operation_zone({"x": 0.5, "y": 1.5})

        page._handle_operation_zone_boundary_save_finished(
            True,
            {
                "result_code": "UPDATED",
                "operation_zone": {
                    "zone_id": "room_301",
                    "zone_name": "301호",
                    "zone_type": "ROOM",
                    "revision": 2,
                    "boundary_json": {
                        "type": "POLYGON",
                        "header": {"frame_id": "map"},
                        "vertices": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 1.0, "y": 0.0},
                            {"x": 1.0, "y": 1.0},
                            {"x": 0.5, "y": 1.5},
                        ],
                    },
                    "boundary_vertex_count": 4,
                    "boundary_frame_id": "map",
                    "is_enabled": True,
                },
            },
        )

        assert page.selected_operation_zone["revision"] == 2
        assert page.operation_zone_boundary_dirty is False
        assert page.findChild(QTableWidget, "operationZoneBoundaryTable").rowCount() == 4
        assert page.validation_message_label.text() == "운영 구역 boundary를 저장했습니다."
    finally:
        page.close()


def test_coordinate_zone_settings_page_keeps_operation_zone_dirty_on_failure():
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
        page.select_operation_zone(0)
        page.findChild(QLineEdit, "operationZoneNameInput").setText("301호-수정")

        page._handle_operation_zone_save_finished(
            False,
            "ZONE_REVISION_CONFLICT: 다른 사용자가 먼저 구역을 수정했습니다.",
        )

        assert page.findChild(QLineEdit, "operationZoneNameInput").text() == "301호-수정"
        assert page.operation_zone_dirty is True
        assert page.save_button.isEnabled() is True
        assert "ZONE_REVISION_CONFLICT" in page.validation_message_label.text()
    finally:
        page.close()


def test_coordinate_zone_settings_page_selects_goal_pose_into_edit_form():
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
        page.select_goal_pose(0)

        assert page.selected_edit_type == "goal_pose"
        assert page.selected_goal_pose["goal_pose_id"] == "delivery_room_301"
        assert page.findChild(QLabel, "goalPoseIdLabel").text() == "delivery_room_301"
        assert (
            page.findChild(QComboBox, "goalPoseZoneCombo").currentData()
            == "room_301"
        )
        assert (
            page.findChild(QComboBox, "goalPosePurposeCombo").currentText()
            == "DESTINATION"
        )
        assert page.findChild(QDoubleSpinBox, "goalPoseXSpin").value() == 1.7
        assert page.findChild(QDoubleSpinBox, "goalPoseYSpin").value() == 0.02
        assert page.findChild(QDoubleSpinBox, "goalPoseYawSpin").value() == 0.0
        assert page.findChild(QLabel, "goalPoseFrameIdLabel").text() == "map"
        assert page.findChild(QCheckBox, "goalPoseEnabledCheck").isChecked() is True
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_goal_pose_dirty_and_map_click_preview():
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
        page.select_goal_pose(0)

        page.findChild(QDoubleSpinBox, "goalPoseYawSpin").setValue(1.57)

        assert page.goal_pose_dirty is True
        assert page.save_button.isEnabled() is True
        assert page.discard_button.isEnabled() is True
        assert "저장 전" in page.validation_message_label.text()

        page.handle_map_click_for_goal_pose({"x": 0.02, "y": 0.04})

        assert page.findChild(QDoubleSpinBox, "goalPoseXSpin").value() == 0.02
        assert page.findChild(QDoubleSpinBox, "goalPoseYSpin").value() == 0.04
        assert page.goal_pose_dirty is True
    finally:
        page.close()


def test_goal_pose_save_worker_sends_if_loc_004_payload():
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        GoalPoseSaveWorker,
    )

    calls = []

    class FakeCoordinateService:
        def update_goal_pose(self, **payload):
            calls.append(payload)
            return {
                "result_code": "UPDATED",
                "goal_pose": {
                    **payload,
                    "updated_at": "2026-05-02T03:30:00Z",
                },
            }

    payload = {
        "goal_pose_id": "delivery_room_301",
        "expected_updated_at": "2026-05-02T03:00:00Z",
        "zone_id": "room_301",
        "purpose": "DESTINATION",
        "pose_x": 1.72,
        "pose_y": 0.03,
        "pose_yaw": 1.57,
        "frame_id": "map",
        "is_enabled": True,
    }
    emitted = []
    worker = GoalPoseSaveWorker(
        payload=payload,
        service_factory=FakeCoordinateService,
    )
    worker.finished.connect(lambda ok, response: emitted.append((ok, response)))

    worker.run()

    assert calls == [payload]
    assert emitted[0][0] is True
    assert emitted[0][1]["goal_pose"]["updated_at"] == "2026-05-02T03:30:00Z"


def test_coordinate_zone_settings_page_applies_goal_pose_save_success():
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
        page.select_goal_pose(0)
        page._handle_goal_pose_save_finished(
            True,
            {
                "result_code": "UPDATED",
                "goal_pose": {
                    "goal_pose_id": "delivery_room_301",
                    "zone_id": "room_301",
                    "zone_name": "301호",
                    "purpose": "DESTINATION",
                    "pose_x": 1.72,
                    "pose_y": 0.03,
                    "pose_yaw": 1.57,
                    "frame_id": "map",
                    "is_enabled": True,
                    "updated_at": "2026-05-02T03:30:00Z",
                },
            },
        )

        goal_table = page.findChild(QTableWidget, "goalPoseTable")
        assert goal_table.item(0, 3).text() == "x=1.72, y=0.03, yaw=1.57"
        assert page.selected_goal_pose["updated_at"] == "2026-05-02T03:30:00Z"
        assert page.goal_pose_dirty is False
        assert page.save_button.isEnabled() is False
        assert page.validation_message_label.text() == "목표 좌표를 저장했습니다."
    finally:
        page.close()


def test_coordinate_zone_settings_page_keeps_dirty_values_on_goal_pose_save_failure():
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
        page.select_goal_pose(0)
        page.findChild(QDoubleSpinBox, "goalPoseXSpin").setValue(0.01)

        page._handle_goal_pose_save_finished(
            False,
            "GOAL_POSE_STALE: 다른 사용자가 먼저 좌표를 수정했습니다.",
        )

        assert page.findChild(QDoubleSpinBox, "goalPoseXSpin").value() == 0.01
        assert page.goal_pose_dirty is True
        assert page.save_button.isEnabled() is True
        assert "GOAL_POSE_STALE" in page.validation_message_label.text()
    finally:
        page.close()


def test_coordinate_zone_settings_page_selects_patrol_area_into_waypoint_form():
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
        page.select_patrol_area(0)

        assert page.selected_edit_type == "patrol_area"
        assert page.selected_patrol_area["patrol_area_id"] == "patrol_ward_night_01"
        assert (
            page.findChild(QLabel, "patrolAreaIdLabel").text()
            == "patrol_ward_night_01"
        )
        assert page.findChild(QLabel, "patrolAreaRevisionLabel").text() == "7"

        waypoint_table = page.findChild(QTableWidget, "patrolWaypointTable")
        assert waypoint_table.rowCount() == 2
        assert waypoint_table.item(0, 1).text() == "0.0000"
        assert waypoint_table.item(1, 3).text() == "1.5700"
        assert len(page.map_canvas.route_pixel_points) == 2
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_patrol_path_map_click_edit_and_discard():
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
        page.select_patrol_area(0)

        page.handle_map_click_for_patrol_area({"x": 0.5, "y": 0.5})

        waypoint_table = page.findChild(QTableWidget, "patrolWaypointTable")
        assert waypoint_table.rowCount() == 3
        assert waypoint_table.item(2, 1).text() == "0.5000"
        assert page.patrol_area_dirty is True
        assert page.save_button.isEnabled() is True
        assert page.discard_button.isEnabled() is True

        page.select_patrol_waypoint(2)
        page.findChild(QDoubleSpinBox, "patrolWaypointYawSpin").setValue(3.14)

        assert waypoint_table.item(2, 3).text() == "3.1400"

        page.discard_current_edit()

        assert waypoint_table.rowCount() == 2
        assert page.patrol_area_dirty is False
        assert page.save_button.isEnabled() is False
    finally:
        page.close()


def test_coordinate_zone_settings_page_patrol_waypoint_click_selects_and_drag_moves():
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
        page.select_patrol_area(0)

        page.handle_map_click_for_patrol_area({"x": 0.0, "y": 0.2})

        waypoint_table = page.findChild(QTableWidget, "patrolWaypointTable")
        assert waypoint_table.rowCount() == 2
        assert page.selected_patrol_waypoint_index == 0

        page.move_selected_patrol_waypoint_to_world({"x": 0.4, "y": 0.6})

        assert waypoint_table.item(0, 1).text() == "0.4000"
        assert waypoint_table.item(0, 2).text() == "0.6000"
        assert page.patrol_waypoint_rows[0]["yaw"] == 0.0
        assert page.patrol_area_dirty is True
    finally:
        page.close()


def test_patrol_area_path_save_worker_sends_if_loc_005_payload():
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        PatrolAreaPathSaveWorker,
    )

    calls = []

    class FakeCoordinateService:
        def update_patrol_area_path(self, **payload):
            calls.append(payload)
            return {
                "result_code": "UPDATED",
                "patrol_area": {
                    "patrol_area_id": payload["patrol_area_id"],
                    "revision": payload["expected_revision"] + 1,
                    "path_json": payload["path_json"],
                    "waypoint_count": len(payload["path_json"]["poses"]),
                    "path_frame_id": payload["path_json"]["header"]["frame_id"],
                    "is_enabled": True,
                },
            }

    payload = {
        "patrol_area_id": "patrol_ward_night_01",
        "expected_revision": 7,
        "path_json": {
            "header": {"frame_id": "map"},
            "poses": [
                {"x": 0.0, "y": 0.2, "yaw": 0.0},
                {"x": 1.0, "y": 1.0, "yaw": 1.57},
            ],
        },
    }
    emitted = []
    worker = PatrolAreaPathSaveWorker(
        payload=payload,
        service_factory=FakeCoordinateService,
    )
    worker.finished.connect(lambda ok, response: emitted.append((ok, response)))

    worker.run()

    assert calls == [payload]
    assert emitted[0][0] is True
    assert emitted[0][1]["patrol_area"]["revision"] == 8


def test_coordinate_zone_settings_page_applies_patrol_area_path_save_success():
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
        page.select_patrol_area(0)
        page._handle_patrol_area_path_save_finished(
            True,
            {
                "result_code": "UPDATED",
                "patrol_area": {
                    "patrol_area_id": "patrol_ward_night_01",
                    "patrol_area_name": "야간 병동 순찰",
                    "revision": 8,
                    "waypoint_count": 3,
                    "path_frame_id": "map",
                    "path_json": {
                        "header": {"frame_id": "map"},
                        "poses": [
                            {"x": 0.0, "y": 0.2, "yaw": 0.0},
                            {"x": 1.0, "y": 1.0, "yaw": 1.57},
                            {"x": 0.5, "y": 0.5, "yaw": 0.0},
                        ],
                    },
                    "is_enabled": True,
                },
            },
        )

        patrol_table = page.findChild(QTableWidget, "patrolAreaTable")
        waypoint_table = page.findChild(QTableWidget, "patrolWaypointTable")
        assert patrol_table.item(0, 1).text() == "8"
        assert patrol_table.item(0, 2).text() == "3"
        assert waypoint_table.rowCount() == 3
        assert page.selected_patrol_area["revision"] == 8
        assert page.patrol_area_dirty is False
        assert page.validation_message_label.text() == "순찰 경로를 저장했습니다."
    finally:
        page.close()


def test_coordinate_zone_settings_page_keeps_patrol_area_dirty_on_failure():
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
        page.select_patrol_area(0)
        page.handle_map_click_for_patrol_area({"x": 0.5, "y": 0.5})

        page._handle_patrol_area_path_save_finished(
            False,
            "PATROL_AREA_REVISION_CONFLICT: 다른 사용자가 먼저 경로를 수정했습니다.",
        )

        assert page.findChild(QTableWidget, "patrolWaypointTable").rowCount() == 3
        assert page.patrol_area_dirty is True
        assert page.save_button.isEnabled() is True
        assert "PATROL_AREA_REVISION_CONFLICT" in page.validation_message_label.text()
    finally:
        page.close()


def test_coordinate_zone_settings_page_blocks_patrol_path_with_less_than_two_waypoints():
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
        page.select_patrol_area(0)
        page.select_patrol_waypoint(1)
        page.delete_selected_patrol_waypoint()

        page.save_current_edit()

        assert page.patrol_area_dirty is True
        assert page.patrol_area_save_thread is None
        assert "최소 2개" in page.validation_message_label.text()
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
