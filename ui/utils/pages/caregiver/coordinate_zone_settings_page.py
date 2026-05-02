import base64
import binascii

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.network.service_clients import CoordinateConfigRemoteService
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.map_overlay import PatrolMapOverlay


ACTIVE_MAP_FIELDS = [
    ("map_id", "map_id"),
    ("map_name", "map_name"),
    ("map_revision", "map_revision"),
    ("frame_id", "frame_id"),
    ("yaml_path", "yaml_path"),
    ("pgm_path", "pgm_path"),
]
GOAL_POSE_PURPOSES = ["PICKUP", "DESTINATION", "DOCK"]
OPERATION_ZONE_TYPES = [
    "ROOM",
    "ENTRANCE",
    "CORRIDOR",
    "NURSE_STATION",
    "STAFF_STATION",
    "CAREGIVER_ROOM",
    "SUPPLY_STATION",
    "DOCK",
    "RESTRICTED",
    "OTHER",
]


class CoordinateConfigLoadWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.service_factory = service_factory

    def run(self):
        try:
            service = self.service_factory()
            bundle = service.get_active_map_bundle(
                include_disabled=True,
                include_zone_boundaries=True,
                include_patrol_paths=True,
            )
            if not _is_ok_response(bundle):
                self.finished.emit(False, _format_result_error(bundle))
                return

            map_profile = bundle.get("map_profile") or {}
            map_id = map_profile.get("map_id")
            yaml_asset = service.get_map_asset(
                asset_type="YAML",
                map_id=map_id,
                encoding="TEXT",
            )
            if not _is_ok_response(yaml_asset):
                self.finished.emit(False, _format_result_error(yaml_asset))
                return

            pgm_asset = service.get_map_asset(
                asset_type="PGM",
                map_id=map_id,
                encoding="BASE64",
            )
            if not _is_ok_response(pgm_asset):
                self.finished.emit(False, _format_result_error(pgm_asset))
                return

            yaml_text = str(yaml_asset.get("content_text") or "")
            pgm_bytes = _decode_base64_asset(pgm_asset.get("content_base64"))
            if not yaml_text or not pgm_bytes:
                self.finished.emit(False, "맵 asset 응답이 비어 있습니다.")
                return

            self.finished.emit(
                True,
                {
                    "bundle": bundle,
                    "yaml_text": yaml_text,
                    "pgm_bytes": pgm_bytes,
                    "yaml_sha256": yaml_asset.get("sha256"),
                    "pgm_sha256": pgm_asset.get("sha256"),
                },
            )
        except Exception as exc:
            self.finished.emit(False, str(exc))


class GoalPoseSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            response = self.service_factory().update_goal_pose(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class OperationZoneSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, mode, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.mode = str(mode or "").strip()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            service = self.service_factory()
            if self.mode == "create":
                response = service.create_operation_zone(**self.payload)
                success_code = "CREATED"
            else:
                response = service.update_operation_zone(**self.payload)
                success_code = "UPDATED"

            if (
                isinstance(response, dict)
                and response.get("result_code") == success_code
            ):
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class OperationZoneBoundarySaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            service = self.service_factory()
            response = service.update_operation_zone_boundary(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class PatrolAreaPathSaveWorker(QObject):
    finished = pyqtSignal(object, object)

    def __init__(self, *, payload, service_factory=CoordinateConfigRemoteService):
        super().__init__()
        self.payload = dict(payload or {})
        self.service_factory = service_factory

    def run(self):
        try:
            response = self.service_factory().update_patrol_area_path(**self.payload)
            if isinstance(response, dict) and response.get("result_code") == "UPDATED":
                self.finished.emit(True, response)
                return
            self.finished.emit(False, _format_result_error(response))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class CoordinateZoneSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_map_labels = {}
        self.tables = {}
        self.load_thread = None
        self.load_worker = None
        self.goal_pose_save_thread = None
        self.goal_pose_save_worker = None
        self.operation_zone_save_thread = None
        self.operation_zone_save_worker = None
        self.patrol_area_save_thread = None
        self.patrol_area_save_worker = None
        self._worker_stop_wait_ms = 1500
        self.current_bundle = {}
        self.operation_zone_rows = []
        self.goal_pose_rows = []
        self.patrol_area_rows = []
        self.patrol_waypoint_rows = []
        self.selected_edit_type = None
        self.operation_zone_mode = None
        self.selected_operation_zone = None
        self.selected_operation_zone_index = None
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = False
        self.operation_zone_boundary_vertices = []
        self.selected_operation_zone_boundary_vertex_index = None
        self._syncing_operation_zone_form = False
        self._syncing_operation_zone_boundary_form = False
        self.selected_goal_pose = None
        self.selected_goal_pose_index = None
        self.goal_pose_dirty = False
        self._syncing_goal_pose_form = False
        self.selected_patrol_area = None
        self.selected_patrol_area_index = None
        self.selected_patrol_waypoint_index = None
        self.patrol_area_dirty = False
        self._syncing_patrol_waypoint_form = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            PageHeader(
                "좌표/구역 설정",
                "DB 기반 운영 좌표, 구역, 순찰 경로 설정을 관리합니다.",
            ),
            1,
        )
        header_row.addLayout(self._build_action_buttons())

        root.addLayout(header_row)
        root.addWidget(self._build_active_map_bar())
        root.addLayout(self._build_content_row(), 1)

    def _build_action_buttons(self):
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setObjectName("coordinateRefreshButton")
        self.save_button = QPushButton("저장")
        self.save_button.setObjectName("coordinateSaveButton")
        self.save_button.setEnabled(False)
        self.discard_button = QPushButton("변경 취소")
        self.discard_button.setObjectName("coordinateDiscardButton")
        self.discard_button.setEnabled(False)

        self.refresh_button.clicked.connect(self.load_coordinate_bundle)
        self.save_button.clicked.connect(self.save_current_edit)
        self.discard_button.clicked.connect(self.discard_current_edit)
        action_row.addWidget(self.refresh_button)
        action_row.addWidget(self.discard_button)
        action_row.addWidget(self.save_button)
        return action_row

    def _build_active_map_bar(self):
        panel = QFrame()
        panel.setObjectName("coordinateActiveMapBar")
        layout = QGridLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(8)

        title = QLabel("Active Map")
        title.setObjectName("sectionTitle")
        layout.addWidget(title, 0, 0, 1, 2)

        for index, (key, label_text) in enumerate(ACTIVE_MAP_FIELDS):
            label = QLabel(label_text)
            label.setObjectName("mutedText")
            value = QLabel("-")
            value.setObjectName("sideMetricValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.active_map_labels[key] = value

            row = 1 + (index // 3)
            column = (index % 3) * 2
            layout.addWidget(label, row, column)
            layout.addWidget(value, row, column + 1)

        return panel

    def _build_content_row(self):
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addLayout(self._build_left_column(), 2)
        row.addLayout(self._build_right_column(), 1)
        return row

    def _build_left_column(self):
        column = QVBoxLayout()
        column.setSpacing(14)

        map_card = QFrame()
        map_card.setObjectName("card")
        map_layout = QVBoxLayout(map_card)
        map_layout.setContentsMargins(18, 18, 18, 18)
        map_layout.setSpacing(10)

        map_title = QLabel("Map Canvas")
        map_title.setObjectName("sectionTitle")
        self.map_canvas = PatrolMapOverlay()
        self.map_canvas.setObjectName("coordinateZoneMapCanvas")
        self.map_canvas.clear_map("좌표 설정 맵 미수신")
        self.map_canvas.setMinimumHeight(280)
        self.map_canvas.map_clicked.connect(self.handle_map_click)
        self.map_canvas.map_dragged.connect(self.handle_map_drag)

        map_layout.addWidget(map_title)
        map_layout.addWidget(self.map_canvas)

        table_row = QHBoxLayout()
        table_row.setSpacing(12)
        table_row.addWidget(
            self._build_table_card(
                "operation_zone",
                "operationZoneTable",
                ["zone_id", "zone_name", "zone_type", "enabled"],
            )
        )
        table_row.addWidget(
            self._build_table_card(
                "goal_pose",
                "goalPoseTable",
                ["goal_pose_id", "purpose", "zone", "x/y/yaw"],
            )
        )
        table_row.addWidget(
            self._build_table_card(
                "patrol_area.path_json",
                "patrolAreaTable",
                ["patrol_area_id", "revision", "waypoints", "enabled"],
            )
        )

        column.addWidget(map_card)
        column.addLayout(table_row)
        return column

    def _build_table_card(self, title_text, object_name, headers):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        table = QTableWidget(0, len(headers))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        self.tables[object_name] = table
        if object_name == "goalPoseTable":
            table.cellClicked.connect(lambda row, _column: self.select_goal_pose(row))
        if object_name == "operationZoneTable":
            table.cellClicked.connect(
                lambda row, _column: self.select_operation_zone(row)
            )
        if object_name == "patrolAreaTable":
            table.cellClicked.connect(lambda row, _column: self.select_patrol_area(row))

        layout.addWidget(title)
        layout.addWidget(table)
        return card

    def _build_right_column(self):
        column = QVBoxLayout()
        column.setSpacing(14)
        column.addWidget(self._build_edit_panel(), 2)
        column.addWidget(self._build_validation_panel())
        return column

    def _build_edit_panel(self):
        panel = QFrame()
        panel.setObjectName("coordinateEditPanel")
        self.edit_panel_layout = QVBoxLayout(panel)
        self.edit_panel_layout.setContentsMargins(18, 18, 18, 18)
        self.edit_panel_layout.setSpacing(10)

        title = QLabel("Edit Panel")
        title.setObjectName("sectionTitle")
        self.edit_mode_label = QLabel("선택 모드")
        self.edit_mode_label.setObjectName("coordinateEditModeLabel")
        self.edit_placeholder_label = QLabel(
            "목록 또는 맵 marker를 선택하면 구역, 목표 좌표, 순찰 waypoint "
            "편집 폼이 여기에 표시됩니다."
        )
        self.edit_placeholder_label.setObjectName("mutedText")
        self.edit_placeholder_label.setWordWrap(True)
        self.operation_zone_new_button = QPushButton("새 구역")
        self.operation_zone_new_button.setObjectName("operationZoneNewButton")
        self.operation_zone_new_button.clicked.connect(self.start_operation_zone_create)
        self.operation_zone_form = self._build_operation_zone_form()
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form = self._build_goal_pose_form()
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form = self._build_patrol_area_form()
        self.patrol_area_form.setHidden(True)

        self.edit_panel_layout.addWidget(title)
        self.edit_panel_layout.addWidget(self.edit_mode_label)
        self.edit_panel_layout.addWidget(self.operation_zone_new_button)
        self.edit_panel_layout.addWidget(self.edit_placeholder_label)
        self.edit_panel_layout.addWidget(self.operation_zone_form)
        self.edit_panel_layout.addWidget(self.goal_pose_form)
        self.edit_panel_layout.addWidget(self.patrol_area_form)
        self.edit_panel_layout.addStretch(1)
        return panel

    def _build_operation_zone_form(self):
        form = QFrame()
        form.setObjectName("operationZoneEditForm")
        layout = QGridLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        self.operation_zone_id_input = QLineEdit()
        self.operation_zone_id_input.setObjectName("operationZoneIdInput")
        self.operation_zone_name_input = QLineEdit()
        self.operation_zone_name_input.setObjectName("operationZoneNameInput")
        self.operation_zone_type_combo = QComboBox()
        self.operation_zone_type_combo.setObjectName("operationZoneTypeCombo")
        self.operation_zone_type_combo.addItems(OPERATION_ZONE_TYPES)
        self.operation_zone_enabled_check = QCheckBox("활성")
        self.operation_zone_enabled_check.setObjectName("operationZoneEnabledCheck")

        rows = [
            ("구역 ID", self.operation_zone_id_input),
            ("구역명", self.operation_zone_name_input),
            ("구역 유형", self.operation_zone_type_combo),
            ("사용 여부", self.operation_zone_enabled_check),
        ]
        for row_index, (label_text, widget) in enumerate(rows):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            layout.addWidget(label, row_index, 0)
            layout.addWidget(widget, row_index, 1)

        for widget in [
            self.operation_zone_id_input,
            self.operation_zone_name_input,
            self.operation_zone_type_combo,
            self.operation_zone_enabled_check,
        ]:
            self._connect_operation_zone_dirty_signal(widget)

        boundary_title = QLabel("boundary vertices")
        boundary_title.setObjectName("fieldLabel")
        self.operation_zone_boundary_table = QTableWidget(0, 3)
        self.operation_zone_boundary_table.setObjectName("operationZoneBoundaryTable")
        self.operation_zone_boundary_table.setHorizontalHeaderLabels(["#", "x", "y"])
        self.operation_zone_boundary_table.horizontalHeader().setStretchLastSection(True)
        self.operation_zone_boundary_table.cellClicked.connect(
            lambda row, _column: self.select_operation_zone_boundary_vertex(row)
        )
        layout.addWidget(boundary_title, len(rows), 0)
        layout.addWidget(self.operation_zone_boundary_table, len(rows), 1)

        self.operation_zone_boundary_x_spin = self._coordinate_spin(
            "operationZoneBoundaryXSpin"
        )
        self.operation_zone_boundary_y_spin = self._coordinate_spin(
            "operationZoneBoundaryYSpin"
        )
        layout.addWidget(QLabel("vertex x"), len(rows) + 1, 0)
        layout.addWidget(self.operation_zone_boundary_x_spin, len(rows) + 1, 1)
        layout.addWidget(QLabel("vertex y"), len(rows) + 2, 0)
        layout.addWidget(self.operation_zone_boundary_y_spin, len(rows) + 2, 1)

        boundary_button_row = QHBoxLayout()
        boundary_button_row.setSpacing(8)
        self.operation_zone_boundary_delete_button = QPushButton("꼭짓점 삭제")
        self.operation_zone_boundary_delete_button.setObjectName(
            "operationZoneBoundaryDeleteButton"
        )
        self.operation_zone_boundary_clear_button = QPushButton("boundary 초기화")
        self.operation_zone_boundary_clear_button.setObjectName(
            "operationZoneBoundaryClearButton"
        )
        self.operation_zone_boundary_delete_button.clicked.connect(
            self.delete_selected_operation_zone_boundary_vertex
        )
        self.operation_zone_boundary_clear_button.clicked.connect(
            self.clear_operation_zone_boundary
        )
        boundary_button_row.addWidget(self.operation_zone_boundary_delete_button)
        boundary_button_row.addWidget(self.operation_zone_boundary_clear_button)
        layout.addLayout(boundary_button_row, len(rows) + 3, 1)

        for widget in [
            self.operation_zone_boundary_x_spin,
            self.operation_zone_boundary_y_spin,
        ]:
            widget.valueChanged.connect(
                lambda _value: (
                    self._update_selected_operation_zone_boundary_vertex_from_form()
                )
            )

        return form

    def _build_goal_pose_form(self):
        form = QFrame()
        form.setObjectName("goalPoseEditForm")
        layout = QGridLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        self.goal_pose_id_label = self._readonly_value_label("goalPoseIdLabel")
        self.goal_pose_zone_combo = QComboBox()
        self.goal_pose_zone_combo.setObjectName("goalPoseZoneCombo")
        self.goal_pose_purpose_combo = QComboBox()
        self.goal_pose_purpose_combo.setObjectName("goalPosePurposeCombo")
        self.goal_pose_purpose_combo.addItems(GOAL_POSE_PURPOSES)
        self.goal_pose_x_spin = self._coordinate_spin("goalPoseXSpin")
        self.goal_pose_y_spin = self._coordinate_spin("goalPoseYSpin")
        self.goal_pose_yaw_spin = self._coordinate_spin("goalPoseYawSpin")
        self.goal_pose_frame_id_label = self._readonly_value_label(
            "goalPoseFrameIdLabel"
        )
        self.goal_pose_enabled_check = QCheckBox("활성")
        self.goal_pose_enabled_check.setObjectName("goalPoseEnabledCheck")

        rows = [
            ("좌표 ID", self.goal_pose_id_label),
            ("연결 구역", self.goal_pose_zone_combo),
            ("목적", self.goal_pose_purpose_combo),
            ("x", self.goal_pose_x_spin),
            ("y", self.goal_pose_y_spin),
            ("yaw(rad)", self.goal_pose_yaw_spin),
            ("frame_id", self.goal_pose_frame_id_label),
            ("사용 여부", self.goal_pose_enabled_check),
        ]
        for row_index, (label_text, widget) in enumerate(rows):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            layout.addWidget(label, row_index, 0)
            layout.addWidget(widget, row_index, 1)

        for widget in [
            self.goal_pose_zone_combo,
            self.goal_pose_purpose_combo,
            self.goal_pose_x_spin,
            self.goal_pose_y_spin,
            self.goal_pose_yaw_spin,
            self.goal_pose_enabled_check,
        ]:
            self._connect_goal_pose_dirty_signal(widget)

        return form

    def _build_patrol_area_form(self):
        form = QFrame()
        form.setObjectName("patrolAreaEditForm")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        summary_layout = QGridLayout()
        summary_layout.setHorizontalSpacing(10)
        summary_layout.setVerticalSpacing(8)
        self.patrol_area_id_label = self._readonly_value_label("patrolAreaIdLabel")
        self.patrol_area_name_label = self._readonly_value_label("patrolAreaNameLabel")
        self.patrol_area_revision_label = self._readonly_value_label(
            "patrolAreaRevisionLabel"
        )
        self.patrol_path_frame_label = self._readonly_value_label("patrolPathFrameLabel")

        summary_rows = [
            ("순찰 구역 ID", self.patrol_area_id_label),
            ("순찰 구역명", self.patrol_area_name_label),
            ("경로 revision", self.patrol_area_revision_label),
            ("frame_id", self.patrol_path_frame_label),
        ]
        for row_index, (label_text, widget) in enumerate(summary_rows):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            summary_layout.addWidget(label, row_index, 0)
            summary_layout.addWidget(widget, row_index, 1)
        layout.addLayout(summary_layout)

        self.patrol_waypoint_table = QTableWidget(0, 4)
        self.patrol_waypoint_table.setObjectName("patrolWaypointTable")
        self.patrol_waypoint_table.setHorizontalHeaderLabels(["#", "x", "y", "yaw"])
        self.patrol_waypoint_table.horizontalHeader().setStretchLastSection(True)
        self.patrol_waypoint_table.cellClicked.connect(
            lambda row, _column: self.select_patrol_waypoint(row)
        )
        layout.addWidget(self.patrol_waypoint_table)

        waypoint_form = QGridLayout()
        waypoint_form.setHorizontalSpacing(10)
        waypoint_form.setVerticalSpacing(8)
        self.patrol_waypoint_x_spin = self._coordinate_spin("patrolWaypointXSpin")
        self.patrol_waypoint_y_spin = self._coordinate_spin("patrolWaypointYSpin")
        self.patrol_waypoint_yaw_spin = self._coordinate_spin("patrolWaypointYawSpin")
        for row_index, (label_text, widget) in enumerate(
            [
                ("waypoint x", self.patrol_waypoint_x_spin),
                ("waypoint y", self.patrol_waypoint_y_spin),
                ("waypoint yaw(rad)", self.patrol_waypoint_yaw_spin),
            ]
        ):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            waypoint_form.addWidget(label, row_index, 0)
            waypoint_form.addWidget(widget, row_index, 1)
        layout.addLayout(waypoint_form)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.patrol_waypoint_up_button = QPushButton("위로")
        self.patrol_waypoint_up_button.setObjectName("patrolWaypointUpButton")
        self.patrol_waypoint_down_button = QPushButton("아래로")
        self.patrol_waypoint_down_button.setObjectName("patrolWaypointDownButton")
        self.patrol_waypoint_delete_button = QPushButton("waypoint 삭제")
        self.patrol_waypoint_delete_button.setObjectName("patrolWaypointDeleteButton")
        self.patrol_waypoint_up_button.clicked.connect(
            lambda: self.move_selected_patrol_waypoint(-1)
        )
        self.patrol_waypoint_down_button.clicked.connect(
            lambda: self.move_selected_patrol_waypoint(1)
        )
        self.patrol_waypoint_delete_button.clicked.connect(
            self.delete_selected_patrol_waypoint
        )
        button_row.addWidget(self.patrol_waypoint_up_button)
        button_row.addWidget(self.patrol_waypoint_down_button)
        button_row.addWidget(self.patrol_waypoint_delete_button)
        layout.addLayout(button_row)

        for widget in [
            self.patrol_waypoint_x_spin,
            self.patrol_waypoint_y_spin,
            self.patrol_waypoint_yaw_spin,
        ]:
            widget.valueChanged.connect(
                lambda _value: self._update_selected_patrol_waypoint_from_form()
            )

        return form

    @staticmethod
    def _readonly_value_label(object_name):
        label = QLabel("-")
        label.setObjectName(object_name)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _coordinate_spin(object_name):
        spin = QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(-10000.0, 10000.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.01)
        return spin

    def _connect_goal_pose_dirty_signal(self, widget):
        if isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(lambda _value: self._mark_goal_pose_dirty())
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda _index: self._mark_goal_pose_dirty()
            )
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _checked: self._mark_goal_pose_dirty())

    def _connect_operation_zone_dirty_signal(self, widget):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _text: self._mark_operation_zone_dirty())
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda _index: self._mark_operation_zone_dirty()
            )
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(
                lambda _checked: self._mark_operation_zone_dirty()
            )

    def _build_validation_panel(self):
        panel = QFrame()
        panel.setObjectName("coordinateValidationPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title = QLabel("Validation")
        title.setObjectName("sectionTitle")
        self.validation_message_label = QLabel(
            "맵이 로드되기 전에는 좌표를 저장할 수 없습니다."
        )
        self.validation_message_label.setObjectName("mutedText")
        self.validation_message_label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.validation_message_label)
        return panel

    def apply_active_map(self, map_profile):
        map_profile = map_profile if isinstance(map_profile, dict) else {}
        for key, label in self.active_map_labels.items():
            value = map_profile.get(key)
            label.setText("-" if value in (None, "") else str(value))

    def load_coordinate_bundle(self):
        if self.load_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("좌표 설정을 불러오는 중입니다.")

        self.load_thread, self.load_worker = start_worker_thread(
            self,
            worker=CoordinateConfigLoadWorker(),
            finished_handler=self._handle_load_finished,
            clear_handler=self._clear_load_thread,
        )

    def apply_loaded_coordinate_config(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        bundle = (
            payload.get("bundle")
            if isinstance(payload.get("bundle"), dict)
            else {}
        )
        self.apply_bundle(bundle)

        map_profile = bundle.get("map_profile") or {}
        cache_key = (
            map_profile.get("map_id"),
            payload.get("yaml_sha256"),
            payload.get("pgm_sha256"),
        )
        self.map_canvas.load_map_from_assets(
            yaml_text=payload.get("yaml_text"),
            pgm_bytes=payload.get("pgm_bytes"),
            cache_key=cache_key,
        )
        if not self.map_canvas.map_loaded:
            self.apply_load_error(self.map_canvas.status_text or "맵 로드 실패")
            return

        self.validation_message_label.setText("맵과 좌표 설정을 불러왔습니다.")
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)

    def apply_bundle(self, bundle):
        bundle = bundle if isinstance(bundle, dict) else {}
        self.current_bundle = bundle
        self.operation_zone_rows = [
            row for row in bundle.get("operation_zones") or [] if isinstance(row, dict)
        ]
        self.goal_pose_rows = [
            row for row in bundle.get("goal_poses") or [] if isinstance(row, dict)
        ]
        self.patrol_area_rows = [
            row for row in bundle.get("patrol_areas") or [] if isinstance(row, dict)
        ]
        self.apply_active_map(bundle.get("map_profile") or {})
        self._populate_goal_pose_form_options()
        self._set_table_rows(
            self.tables["operationZoneTable"],
            self.operation_zone_rows,
            [
                "zone_id",
                "zone_name",
                "zone_type",
                ("is_enabled", _enabled_text),
            ],
        )
        self._set_table_rows(
            self.tables["goalPoseTable"],
            self.goal_pose_rows,
            [
                "goal_pose_id",
                "purpose",
                ("zone_name", _zone_label),
                ("pose", _goal_pose_text),
            ],
        )
        self._set_table_rows(
            self.tables["patrolAreaTable"],
            self.patrol_area_rows,
            [
                "patrol_area_id",
                "revision",
                ("waypoint_count", _waypoint_count_text),
                ("is_enabled", _enabled_text),
            ],
        )

    def apply_load_error(self, message):
        self.map_canvas.clear_map("좌표 설정 맵 로드 실패")
        self.validation_message_label.setText(str(message or "좌표 설정 로드 실패"))
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)

    def select_operation_zone(self, row_index):
        try:
            row_index = int(row_index)
            operation_zone = self.operation_zone_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "operation_zone"
        self.operation_zone_mode = "edit"
        self.selected_operation_zone_index = row_index
        self.selected_operation_zone = dict(operation_zone)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(False)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.edit_mode_label.setText("구역 boundary 편집 모드")
        self._clear_patrol_overlay()
        self._set_operation_zone_form(operation_zone, mode="edit")
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = False
        self._sync_operation_zone_save_state()

    def start_operation_zone_create(self):
        self.selected_edit_type = "operation_zone"
        self.operation_zone_mode = "create"
        self.selected_operation_zone = None
        self.selected_operation_zone_index = None
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(False)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.edit_mode_label.setText("구역 생성 모드")
        self._clear_patrol_overlay()
        self._set_operation_zone_form(
            {
                "zone_id": "",
                "zone_name": "",
                "zone_type": "ROOM",
                "is_enabled": True,
            },
            mode="create",
        )
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = False
        self.validation_message_label.setText("새 운영 구역을 입력하세요.")
        self._sync_operation_zone_save_state()

    def select_goal_pose(self, row_index):
        try:
            row_index = int(row_index)
            goal_pose = self.goal_pose_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "goal_pose"
        self.selected_goal_pose_index = row_index
        self.selected_goal_pose = dict(goal_pose)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(False)
        self.patrol_area_form.setHidden(True)
        self.edit_mode_label.setText("목표 좌표 편집 모드")
        self._clear_patrol_overlay()
        self._set_goal_pose_form(goal_pose)
        self.goal_pose_dirty = False
        self._sync_goal_pose_save_state()

    def select_patrol_area(self, row_index):
        try:
            row_index = int(row_index)
            patrol_area = self.patrol_area_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "patrol_area"
        self.selected_patrol_area_index = row_index
        self.selected_patrol_area = dict(patrol_area)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(False)
        self.edit_mode_label.setText("순찰 경로 편집 모드")
        self._set_patrol_area_form(patrol_area)
        self.patrol_area_dirty = False
        self._sync_patrol_area_save_state()

    def handle_map_click(self, world_pose):
        if self.selected_edit_type == "operation_zone":
            self.handle_map_click_for_operation_zone(world_pose)
        elif self.selected_edit_type == "goal_pose":
            self.handle_map_click_for_goal_pose(world_pose)
        elif self.selected_edit_type == "patrol_area":
            self.handle_map_click_for_patrol_area(world_pose)

    def handle_map_drag(self, world_pose):
        if self.selected_edit_type == "operation_zone":
            self.move_selected_operation_zone_boundary_vertex(world_pose)
        elif self.selected_edit_type == "goal_pose":
            self.handle_map_click_for_goal_pose(world_pose)
        elif self.selected_edit_type == "patrol_area":
            self.move_selected_patrol_waypoint_to_world(world_pose)

    def handle_map_click_for_operation_zone(self, world_pose):
        if self.selected_edit_type != "operation_zone" or not isinstance(world_pose, dict):
            return
        if self.operation_zone_mode == "create":
            self.validation_message_label.setText(
                "새 구역은 먼저 저장한 뒤 boundary를 편집할 수 있습니다."
            )
            return
        try:
            vertex = {
                "x": float(world_pose.get("x")),
                "y": float(world_pose.get("y")),
            }
        except (TypeError, ValueError):
            return
        if not self.map_canvas.contains_world_pose(vertex):
            self.validation_message_label.setText(
                "구역 boundary 꼭짓점이 맵 범위를 벗어나 추가할 수 없습니다."
            )
            return

        selected = self._nearest_pose_index(
            self.operation_zone_boundary_vertices,
            vertex,
        )
        if selected is not None:
            self.select_operation_zone_boundary_vertex(selected)
            return

        self.operation_zone_boundary_vertices.append(vertex)
        self.selected_operation_zone_boundary_vertex_index = (
            len(self.operation_zone_boundary_vertices) - 1
        )
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def handle_map_click_for_goal_pose(self, world_pose):
        if self.selected_edit_type != "goal_pose" or not isinstance(world_pose, dict):
            return
        try:
            x = float(world_pose.get("x"))
            y = float(world_pose.get("y"))
        except (TypeError, ValueError):
            return
        self.goal_pose_x_spin.setValue(x)
        self.goal_pose_y_spin.setValue(y)
        self._mark_goal_pose_dirty()

    def handle_map_click_for_patrol_area(self, world_pose):
        if self.selected_edit_type != "patrol_area" or not isinstance(world_pose, dict):
            return
        try:
            pose = {
                "x": float(world_pose.get("x")),
                "y": float(world_pose.get("y")),
                "yaw": 0.0,
            }
        except (TypeError, ValueError):
            return
        if not self.map_canvas.contains_world_pose(pose):
            self.validation_message_label.setText(
                "순찰 waypoint가 맵 범위를 벗어나 추가할 수 없습니다."
            )
            return

        selected = self._nearest_pose_index(self.patrol_waypoint_rows, pose)
        if selected is not None:
            self.select_patrol_waypoint(selected)
            return

        self.patrol_waypoint_rows.append(pose)
        self.selected_patrol_waypoint_index = len(self.patrol_waypoint_rows) - 1
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def save_current_edit(self):
        if self.selected_edit_type == "operation_zone":
            self.save_selected_operation_zone()
        elif self.selected_edit_type == "goal_pose":
            self.save_selected_goal_pose()
        elif self.selected_edit_type == "patrol_area":
            self.save_selected_patrol_area_path()

    def discard_current_edit(self):
        if self.selected_edit_type == "operation_zone":
            if self.operation_zone_mode == "create":
                self._set_operation_zone_form(
                    {
                        "zone_id": "",
                        "zone_name": "",
                        "zone_type": "ROOM",
                        "is_enabled": True,
                    },
                    mode="create",
                )
                self.validation_message_label.setText(
                    "새 운영 구역 입력을 취소했습니다."
                )
            elif self.selected_operation_zone:
                self._set_operation_zone_form(
                    self.selected_operation_zone,
                    mode="edit",
                )
                self.validation_message_label.setText(
                    "운영 구역 변경을 취소했습니다."
                )
            self.operation_zone_dirty = False
            self.operation_zone_boundary_dirty = False
            self._sync_operation_zone_save_state()
        elif self.selected_edit_type == "goal_pose" and self.selected_goal_pose:
            self._set_goal_pose_form(self.selected_goal_pose)
            self.goal_pose_dirty = False
            self.validation_message_label.setText("목표 좌표 변경을 취소했습니다.")
            self._sync_goal_pose_save_state()
        elif self.selected_edit_type == "patrol_area" and self.selected_patrol_area:
            self._set_patrol_area_form(self.selected_patrol_area)
            self.patrol_area_dirty = False
            self.validation_message_label.setText("순찰 경로 변경을 취소했습니다.")
            self._sync_patrol_area_save_state()

    def save_selected_operation_zone(self):
        if self.operation_zone_save_thread is not None:
            return
        if self.operation_zone_boundary_dirty and not self.operation_zone_dirty:
            self.save_selected_operation_zone_boundary()
            return
        if not self.operation_zone_dirty:
            return

        payload = self._build_operation_zone_save_payload()
        if not payload["zone_id"] or not payload["zone_name"]:
            self.validation_message_label.setText("구역 ID와 구역명을 입력하세요.")
            return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("운영 구역을 저장하는 중입니다.")
        self.operation_zone_save_thread, self.operation_zone_save_worker = (
            start_worker_thread(
                self,
                worker=OperationZoneSaveWorker(
                    mode=self.operation_zone_mode,
                    payload=payload,
                ),
                finished_handler=self._handle_operation_zone_save_finished,
                clear_handler=self._clear_operation_zone_save_thread,
            )
        )

    def _set_operation_zone_form(self, operation_zone, *, mode):
        operation_zone = operation_zone if isinstance(operation_zone, dict) else {}
        self._syncing_operation_zone_form = True
        try:
            self.operation_zone_id_input.setReadOnly(mode != "create")
            self.operation_zone_id_input.setText(
                _display_empty(operation_zone.get("zone_id"))
            )
            self.operation_zone_name_input.setText(
                _display_empty(operation_zone.get("zone_name"))
            )
            self._set_combo_text(
                self.operation_zone_type_combo,
                _display_empty(operation_zone.get("zone_type")) or "ROOM",
            )
            self.operation_zone_enabled_check.setChecked(
                bool(operation_zone.get("is_enabled", True))
            )
        finally:
            self._syncing_operation_zone_form = False
        self._set_operation_zone_boundary_form(operation_zone)

    def _mark_operation_zone_dirty(self):
        if (
            self._syncing_operation_zone_form
            or self.selected_edit_type != "operation_zone"
        ):
            return
        self.operation_zone_dirty = True
        self.validation_message_label.setText("운영 구역 변경 사항이 저장 전입니다.")
        self._sync_operation_zone_save_state()

    def _set_operation_zone_boundary_form(self, operation_zone):
        boundary = (
            operation_zone.get("boundary_json")
            if isinstance(operation_zone, dict)
            else None
        )
        boundary = boundary if isinstance(boundary, dict) else {}
        raw_vertices = boundary.get("vertices")
        if not isinstance(raw_vertices, list):
            raw_vertices = []

        self.operation_zone_boundary_vertices = [
            {"x": _float_or_default(vertex.get("x")), "y": _float_or_default(vertex.get("y"))}
            for vertex in raw_vertices
            if isinstance(vertex, dict)
        ]
        self.selected_operation_zone_boundary_vertex_index = (
            0 if self.operation_zone_boundary_vertices else None
        )
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._sync_operation_zone_overlay()

    def _populate_operation_zone_boundary_table(self):
        self.operation_zone_boundary_table.setRowCount(
            len(self.operation_zone_boundary_vertices)
        )
        for row_index, vertex in enumerate(self.operation_zone_boundary_vertices):
            row_values = [
                str(row_index + 1),
                _waypoint_number_text(vertex.get("x")),
                _waypoint_number_text(vertex.get("y")),
            ]
            for column_index, value in enumerate(row_values):
                self.operation_zone_boundary_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

    def select_operation_zone_boundary_vertex(self, row_index):
        try:
            row_index = int(row_index)
        except (TypeError, ValueError):
            return
        if not 0 <= row_index < len(self.operation_zone_boundary_vertices):
            return
        self.selected_operation_zone_boundary_vertex_index = row_index
        self._set_operation_zone_boundary_vertex_form(row_index)
        self._sync_operation_zone_overlay()

    def _set_operation_zone_boundary_vertex_form(self, row_index):
        enabled = row_index is not None and 0 <= row_index < len(
            self.operation_zone_boundary_vertices
        )
        self._syncing_operation_zone_boundary_form = True
        try:
            self.operation_zone_boundary_x_spin.setEnabled(enabled)
            self.operation_zone_boundary_y_spin.setEnabled(enabled)
            self.operation_zone_boundary_delete_button.setEnabled(enabled)
            self.operation_zone_boundary_clear_button.setEnabled(
                bool(self.operation_zone_boundary_vertices)
            )
            if enabled:
                vertex = self.operation_zone_boundary_vertices[row_index]
                self.operation_zone_boundary_x_spin.setValue(
                    _float_or_default(vertex.get("x"))
                )
                self.operation_zone_boundary_y_spin.setValue(
                    _float_or_default(vertex.get("y"))
                )
            else:
                self.operation_zone_boundary_x_spin.setValue(0.0)
                self.operation_zone_boundary_y_spin.setValue(0.0)
        finally:
            self._syncing_operation_zone_boundary_form = False

    def _update_selected_operation_zone_boundary_vertex_from_form(self):
        if (
            self._syncing_operation_zone_boundary_form
            or self.selected_edit_type != "operation_zone"
        ):
            return
        index = self.selected_operation_zone_boundary_vertex_index
        if index is None or not 0 <= index < len(self.operation_zone_boundary_vertices):
            return
        self.operation_zone_boundary_vertices[index] = {
            "x": self.operation_zone_boundary_x_spin.value(),
            "y": self.operation_zone_boundary_y_spin.value(),
        }
        self._populate_operation_zone_boundary_table()
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def delete_selected_operation_zone_boundary_vertex(self):
        index = self.selected_operation_zone_boundary_vertex_index
        if index is None or not 0 <= index < len(self.operation_zone_boundary_vertices):
            return
        del self.operation_zone_boundary_vertices[index]
        if self.operation_zone_boundary_vertices:
            self.selected_operation_zone_boundary_vertex_index = min(
                index,
                len(self.operation_zone_boundary_vertices) - 1,
            )
        else:
            self.selected_operation_zone_boundary_vertex_index = None
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def clear_operation_zone_boundary(self):
        if not self.operation_zone_boundary_vertices:
            return
        self.operation_zone_boundary_vertices = []
        self.selected_operation_zone_boundary_vertex_index = None
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(None)
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def move_selected_operation_zone_boundary_vertex(self, world_pose):
        if self.selected_edit_type != "operation_zone" or not isinstance(world_pose, dict):
            return
        index = self.selected_operation_zone_boundary_vertex_index
        if index is None or not 0 <= index < len(self.operation_zone_boundary_vertices):
            return
        try:
            vertex = {
                "x": float(world_pose.get("x")),
                "y": float(world_pose.get("y")),
            }
        except (TypeError, ValueError):
            return
        if not self.map_canvas.contains_world_pose(vertex):
            return
        self.operation_zone_boundary_vertices[index] = vertex
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(index)
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def _mark_operation_zone_boundary_dirty(self):
        if self.selected_edit_type != "operation_zone":
            return
        self.operation_zone_boundary_dirty = True
        self.validation_message_label.setText(
            "운영 구역 boundary 변경 사항이 저장 전입니다."
        )
        self._sync_operation_zone_save_state()

    def _sync_operation_zone_save_state(self):
        can_save = (
            self.selected_edit_type == "operation_zone"
            and (self.operation_zone_dirty or self.operation_zone_boundary_dirty)
            and self.map_canvas.map_loaded
            and self.operation_zone_save_thread is None
        )
        self.save_button.setEnabled(can_save)
        self.discard_button.setEnabled(
            self.selected_edit_type == "operation_zone"
            and (self.operation_zone_dirty or self.operation_zone_boundary_dirty)
        )

    def _build_operation_zone_save_payload(self):
        zone_id = self.operation_zone_id_input.text().strip()
        zone_name = self.operation_zone_name_input.text().strip()
        zone_type = self.operation_zone_type_combo.currentText().strip()
        is_enabled = self.operation_zone_enabled_check.isChecked()

        if self.operation_zone_mode == "create":
            map_profile = self.current_bundle.get("map_profile") or {}
            return {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "zone_type": zone_type,
                "map_id": map_profile.get("map_id"),
                "is_enabled": is_enabled,
            }

        return {
            "zone_id": zone_id,
            "expected_revision": int(
                self.selected_operation_zone.get("revision", 0)
            ),
            "zone_name": zone_name,
            "zone_type": zone_type,
            "is_enabled": is_enabled,
        }

    def save_selected_operation_zone_boundary(self):
        if self.operation_zone_save_thread is not None:
            return
        if (
            not self.operation_zone_boundary_dirty
            or not self.selected_operation_zone
            or self.operation_zone_mode == "create"
        ):
            return

        if 0 < len(self.operation_zone_boundary_vertices) < 3:
            self.validation_message_label.setText(
                "구역 boundary는 최소 3개 꼭짓점이 필요합니다."
            )
            return

        for vertex in self.operation_zone_boundary_vertices:
            if not self.map_canvas.contains_world_pose(vertex):
                self.validation_message_label.setText(
                    "구역 boundary 꼭짓점이 맵 범위를 벗어나 저장할 수 없습니다."
                )
                return

        payload = self._build_operation_zone_boundary_save_payload()
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("운영 구역 boundary를 저장하는 중입니다.")
        self.operation_zone_save_thread, self.operation_zone_save_worker = (
            start_worker_thread(
                self,
                worker=OperationZoneBoundarySaveWorker(payload=payload),
                finished_handler=self._handle_operation_zone_boundary_save_finished,
                clear_handler=self._clear_operation_zone_save_thread,
            )
        )

    def _build_operation_zone_boundary_save_payload(self):
        return {
            "zone_id": self.selected_operation_zone.get("zone_id"),
            "expected_revision": int(self.selected_operation_zone.get("revision") or 0),
            "boundary_json": self._current_operation_zone_boundary_json(),
        }

    def _current_operation_zone_boundary_json(self):
        if not self.operation_zone_boundary_vertices:
            return None
        return {
            "type": "POLYGON",
            "header": {"frame_id": self._active_map_frame_id()},
            "vertices": [
                {
                    "x": _float_or_default(vertex.get("x")),
                    "y": _float_or_default(vertex.get("y")),
                }
                for vertex in self.operation_zone_boundary_vertices
            ],
        }

    def _handle_operation_zone_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.operation_zone_dirty = True
            self._sync_operation_zone_save_state()
            return

        response = response if isinstance(response, dict) else {}
        operation_zone = response.get("operation_zone")
        if not isinstance(operation_zone, dict):
            self.validation_message_label.setText("운영 구역 저장 결과가 비어 있습니다.")
            self.operation_zone_dirty = True
            self._sync_operation_zone_save_state()
            return

        boundary_dirty = self.operation_zone_boundary_dirty
        if boundary_dirty:
            operation_zone = {
                **operation_zone,
                "boundary_json": self._current_operation_zone_boundary_json(),
            }
        self._replace_operation_zone_row(operation_zone)
        self.selected_operation_zone = dict(operation_zone)
        self.operation_zone_mode = "edit"
        self._set_operation_zone_form(operation_zone, mode="edit")
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = boundary_dirty
        self.validation_message_label.setText("운영 구역을 저장했습니다.")
        self._populate_goal_pose_form_options()
        self._sync_operation_zone_save_state()

    def _handle_operation_zone_boundary_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.operation_zone_boundary_dirty = True
            self._sync_operation_zone_save_state()
            return

        response = response if isinstance(response, dict) else {}
        operation_zone = response.get("operation_zone")
        if not isinstance(operation_zone, dict):
            self.validation_message_label.setText(
                "운영 구역 boundary 저장 결과가 비어 있습니다."
            )
            self.operation_zone_boundary_dirty = True
            self._sync_operation_zone_save_state()
            return

        self._replace_operation_zone_row(operation_zone)
        self.selected_operation_zone = dict(operation_zone)
        self._set_operation_zone_form(operation_zone, mode="edit")
        self.operation_zone_boundary_dirty = False
        self.validation_message_label.setText("운영 구역 boundary를 저장했습니다.")
        self._sync_operation_zone_save_state()

    def _replace_operation_zone_row(self, operation_zone):
        zone_id = operation_zone.get("zone_id")
        for index, row in enumerate(self.operation_zone_rows):
            if row.get("zone_id") == zone_id:
                self.operation_zone_rows[index] = dict(operation_zone)
                self.selected_operation_zone_index = index
                break
        else:
            self.operation_zone_rows.append(dict(operation_zone))
            self.selected_operation_zone_index = len(self.operation_zone_rows) - 1

        self.current_bundle["operation_zones"] = self.operation_zone_rows
        self._set_table_rows(
            self.tables["operationZoneTable"],
            self.operation_zone_rows,
            [
                "zone_id",
                "zone_name",
                "zone_type",
                ("is_enabled", _enabled_text),
            ],
        )

    def save_selected_patrol_area_path(self):
        if self.patrol_area_save_thread is not None:
            return
        if not self.patrol_area_dirty or not self.selected_patrol_area:
            return

        payload = self._build_patrol_area_path_save_payload()
        poses = payload["path_json"]["poses"]
        if len(poses) < 2:
            self.validation_message_label.setText(
                "순찰 경로는 최소 2개 waypoint가 필요합니다."
            )
            return

        for pose in poses:
            if not self.map_canvas.contains_world_pose(pose):
                self.validation_message_label.setText(
                    "순찰 waypoint가 맵 범위를 벗어나 저장할 수 없습니다."
                )
                return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("순찰 경로를 저장하는 중입니다.")
        self.patrol_area_save_thread, self.patrol_area_save_worker = (
            start_worker_thread(
                self,
                worker=PatrolAreaPathSaveWorker(payload=payload),
                finished_handler=self._handle_patrol_area_path_save_finished,
                clear_handler=self._clear_patrol_area_save_thread,
            )
        )

    def _set_patrol_area_form(self, patrol_area):
        patrol_area = patrol_area if isinstance(patrol_area, dict) else {}
        self.patrol_area_id_label.setText(_display(patrol_area.get("patrol_area_id")))
        self.patrol_area_name_label.setText(
            _display(patrol_area.get("patrol_area_name"))
        )
        self.patrol_area_revision_label.setText(_display(patrol_area.get("revision")))
        frame_id = _patrol_path_frame_id(patrol_area) or self._active_map_frame_id()
        self.patrol_path_frame_label.setText(_display(frame_id))
        self.patrol_waypoint_rows = _patrol_path_poses(patrol_area.get("path_json"))
        self.selected_patrol_waypoint_index = 0 if self.patrol_waypoint_rows else None
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._sync_patrol_overlay()

    def _populate_patrol_waypoint_table(self):
        self.patrol_waypoint_table.setRowCount(len(self.patrol_waypoint_rows))
        for row_index, pose in enumerate(self.patrol_waypoint_rows):
            row_values = [
                str(row_index + 1),
                _waypoint_number_text(pose.get("x")),
                _waypoint_number_text(pose.get("y")),
                _waypoint_number_text(pose.get("yaw")),
            ]
            for column_index, value in enumerate(row_values):
                self.patrol_waypoint_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

    def select_patrol_waypoint(self, row_index):
        try:
            row_index = int(row_index)
        except (TypeError, ValueError):
            return
        if not 0 <= row_index < len(self.patrol_waypoint_rows):
            return

        self.selected_patrol_waypoint_index = row_index
        self._set_patrol_waypoint_form(row_index)
        self._sync_patrol_overlay()

    def _set_patrol_waypoint_form(self, row_index):
        enabled = row_index is not None and 0 <= row_index < len(
            self.patrol_waypoint_rows
        )
        self._syncing_patrol_waypoint_form = True
        try:
            for widget in [
                self.patrol_waypoint_x_spin,
                self.patrol_waypoint_y_spin,
                self.patrol_waypoint_yaw_spin,
            ]:
                widget.setEnabled(enabled)
            if enabled:
                pose = self.patrol_waypoint_rows[row_index]
                self.patrol_waypoint_x_spin.setValue(_float_or_default(pose.get("x")))
                self.patrol_waypoint_y_spin.setValue(_float_or_default(pose.get("y")))
                self.patrol_waypoint_yaw_spin.setValue(
                    _float_or_default(pose.get("yaw"))
                )
            else:
                self.patrol_waypoint_x_spin.setValue(0.0)
                self.patrol_waypoint_y_spin.setValue(0.0)
                self.patrol_waypoint_yaw_spin.setValue(0.0)
        finally:
            self._syncing_patrol_waypoint_form = False
        self._sync_patrol_waypoint_buttons()

    def _update_selected_patrol_waypoint_from_form(self):
        if (
            self._syncing_patrol_waypoint_form
            or self.selected_edit_type != "patrol_area"
        ):
            return
        index = self.selected_patrol_waypoint_index
        if index is None or not 0 <= index < len(self.patrol_waypoint_rows):
            return

        self.patrol_waypoint_rows[index] = {
            "x": self.patrol_waypoint_x_spin.value(),
            "y": self.patrol_waypoint_y_spin.value(),
            "yaw": self.patrol_waypoint_yaw_spin.value(),
        }
        self._populate_patrol_waypoint_table()
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def delete_selected_patrol_waypoint(self):
        index = self.selected_patrol_waypoint_index
        if index is None or not 0 <= index < len(self.patrol_waypoint_rows):
            return

        del self.patrol_waypoint_rows[index]
        if self.patrol_waypoint_rows:
            self.selected_patrol_waypoint_index = min(
                index,
                len(self.patrol_waypoint_rows) - 1,
            )
        else:
            self.selected_patrol_waypoint_index = None
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def move_selected_patrol_waypoint(self, offset):
        index = self.selected_patrol_waypoint_index
        if index is None or not 0 <= index < len(self.patrol_waypoint_rows):
            return
        next_index = index + int(offset)
        if not 0 <= next_index < len(self.patrol_waypoint_rows):
            return

        self.patrol_waypoint_rows[index], self.patrol_waypoint_rows[next_index] = (
            self.patrol_waypoint_rows[next_index],
            self.patrol_waypoint_rows[index],
        )
        self.selected_patrol_waypoint_index = next_index
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(next_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def move_selected_patrol_waypoint_to_world(self, world_pose):
        if self.selected_edit_type != "patrol_area" or not isinstance(world_pose, dict):
            return
        index = self.selected_patrol_waypoint_index
        if index is None or not 0 <= index < len(self.patrol_waypoint_rows):
            return
        try:
            pose = {
                "x": float(world_pose.get("x")),
                "y": float(world_pose.get("y")),
                "yaw": _float_or_default(self.patrol_waypoint_rows[index].get("yaw")),
            }
        except (TypeError, ValueError):
            return
        if not self.map_canvas.contains_world_pose(pose):
            return
        self.patrol_waypoint_rows[index] = pose
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def _sync_patrol_waypoint_buttons(self):
        index = self.selected_patrol_waypoint_index
        has_selection = index is not None and 0 <= index < len(self.patrol_waypoint_rows)
        self.patrol_waypoint_delete_button.setEnabled(has_selection)
        self.patrol_waypoint_up_button.setEnabled(has_selection and index > 0)
        self.patrol_waypoint_down_button.setEnabled(
            has_selection and index < len(self.patrol_waypoint_rows) - 1
        )

    def _mark_patrol_area_dirty(self):
        if self.selected_edit_type != "patrol_area":
            return
        self.patrol_area_dirty = True
        self.validation_message_label.setText("순찰 경로 변경 사항이 저장 전입니다.")
        self._sync_patrol_area_save_state()

    def _sync_patrol_area_save_state(self):
        can_save = (
            self.selected_edit_type == "patrol_area"
            and self.patrol_area_dirty
            and self.map_canvas.map_loaded
            and self.patrol_area_save_thread is None
        )
        self.save_button.setEnabled(can_save)
        self.discard_button.setEnabled(
            self.selected_edit_type == "patrol_area" and self.patrol_area_dirty
        )

    def _build_patrol_area_path_save_payload(self):
        return {
            "patrol_area_id": self.patrol_area_id_label.text().strip(),
            "expected_revision": int(
                self.selected_patrol_area.get("revision") or 0
            ),
            "path_json": {
                "header": {"frame_id": self._active_map_frame_id()},
                "poses": [
                    {
                        "x": _float_or_default(pose.get("x")),
                        "y": _float_or_default(pose.get("y")),
                        "yaw": _float_or_default(pose.get("yaw")),
                    }
                    for pose in self.patrol_waypoint_rows
                ],
            },
        }

    def _handle_patrol_area_path_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.patrol_area_dirty = True
            self._sync_patrol_area_save_state()
            return

        response = response if isinstance(response, dict) else {}
        patrol_area = response.get("patrol_area")
        if not isinstance(patrol_area, dict):
            self.validation_message_label.setText("순찰 경로 저장 결과가 비어 있습니다.")
            self.patrol_area_dirty = True
            self._sync_patrol_area_save_state()
            return

        self._replace_patrol_area_row(patrol_area)
        self.selected_patrol_area = dict(patrol_area)
        self._set_patrol_area_form(patrol_area)
        self.patrol_area_dirty = False
        self.validation_message_label.setText("순찰 경로를 저장했습니다.")
        self._sync_patrol_area_save_state()

    def _replace_patrol_area_row(self, updated_patrol_area):
        patrol_area_id = updated_patrol_area.get("patrol_area_id")
        for index, row in enumerate(self.patrol_area_rows):
            if row.get("patrol_area_id") == patrol_area_id:
                self.patrol_area_rows[index] = dict(updated_patrol_area)
                self.selected_patrol_area_index = index
                break
        else:
            self.patrol_area_rows.append(dict(updated_patrol_area))
            self.selected_patrol_area_index = len(self.patrol_area_rows) - 1

        self.current_bundle["patrol_areas"] = self.patrol_area_rows
        self._set_table_rows(
            self.tables["patrolAreaTable"],
            self.patrol_area_rows,
            [
                "patrol_area_id",
                "revision",
                ("waypoint_count", _waypoint_count_text),
                ("is_enabled", _enabled_text),
            ],
        )

    def _active_map_frame_id(self):
        map_profile = self.current_bundle.get("map_profile") or {}
        return str(map_profile.get("frame_id") or "map").strip()

    def _sync_operation_zone_overlay(self):
        self.map_canvas.zone_boundary_pixel_points = [
            pixel
            for pixel in (
                self.map_canvas.world_to_pixel(vertex)
                for vertex in self.operation_zone_boundary_vertices
            )
            if pixel is not None
        ]
        self.map_canvas.selected_zone_boundary_vertex_index = (
            self.selected_operation_zone_boundary_vertex_index
        )
        self.map_canvas.route_pixel_points = []
        self.map_canvas.current_waypoint_index = None
        self.map_canvas.goal_pose_pixel_points = []
        self.map_canvas.selected_goal_pose_pixel_point = None
        self.map_canvas.robot_pixel_point = None
        self.map_canvas.fall_alert_pixel_point = None
        self.map_canvas.update()

    def _sync_goal_pose_overlay(self):
        self.map_canvas.goal_pose_pixel_points = [
            pixel
            for pixel in (
                self.map_canvas.world_to_pixel(
                    {"x": row.get("pose_x"), "y": row.get("pose_y")}
                )
                for row in self.goal_pose_rows
            )
            if pixel is not None
        ]
        self.map_canvas.selected_goal_pose_pixel_point = self.map_canvas.world_to_pixel(
            {
                "x": self.goal_pose_x_spin.value(),
                "y": self.goal_pose_y_spin.value(),
            }
        )
        self.map_canvas.zone_boundary_pixel_points = []
        self.map_canvas.selected_zone_boundary_vertex_index = None
        self.map_canvas.route_pixel_points = []
        self.map_canvas.current_waypoint_index = None
        self.map_canvas.robot_pixel_point = None
        self.map_canvas.fall_alert_pixel_point = None
        self.map_canvas.update()

    def _sync_patrol_overlay(self):
        self.map_canvas.zone_boundary_pixel_points = []
        self.map_canvas.selected_zone_boundary_vertex_index = None
        self.map_canvas.goal_pose_pixel_points = []
        self.map_canvas.selected_goal_pose_pixel_point = None
        self.map_canvas.route_pixel_points = [
            pixel
            for pixel in (
                self.map_canvas.world_to_pixel(pose)
                for pose in self.patrol_waypoint_rows
            )
            if pixel is not None
        ]
        self.map_canvas.current_waypoint_index = self.selected_patrol_waypoint_index
        self.map_canvas.robot_pixel_point = None
        self.map_canvas.fall_alert_pixel_point = None
        self.map_canvas.update()

    def _clear_patrol_overlay(self):
        self.map_canvas.route_pixel_points = []
        self.map_canvas.current_waypoint_index = None
        self.map_canvas.robot_pixel_point = None
        self.map_canvas.fall_alert_pixel_point = None
        self.map_canvas.zone_boundary_pixel_points = []
        self.map_canvas.selected_zone_boundary_vertex_index = None
        self.map_canvas.goal_pose_pixel_points = []
        self.map_canvas.selected_goal_pose_pixel_point = None
        self.map_canvas.update()

    def _nearest_pose_index(self, poses, world_pose, *, threshold_world=0.08):
        if not isinstance(world_pose, dict):
            return None
        try:
            target_x = float(world_pose.get("x"))
            target_y = float(world_pose.get("y"))
        except (TypeError, ValueError):
            return None
        best_index = None
        best_distance = float(threshold_world)
        for index, pose in enumerate(poses or []):
            try:
                pose_x = float(pose.get("x"))
                pose_y = float(pose.get("y"))
            except (AttributeError, TypeError, ValueError):
                continue
            distance = ((pose_x - target_x) ** 2 + (pose_y - target_y) ** 2) ** 0.5
            if distance <= best_distance:
                best_index = index
                best_distance = distance
        return best_index

    def save_selected_goal_pose(self):
        if self.goal_pose_save_thread is not None:
            return
        if not self.goal_pose_dirty or not self.selected_goal_pose:
            return

        payload = self._build_goal_pose_update_payload()
        if not self.map_canvas.contains_world_pose(
            {"x": payload["pose_x"], "y": payload["pose_y"]}
        ):
            self.validation_message_label.setText(
                "좌표가 맵 범위를 벗어나 저장할 수 없습니다."
            )
            return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("목표 좌표를 저장하는 중입니다.")
        self.goal_pose_save_thread, self.goal_pose_save_worker = start_worker_thread(
            self,
            worker=GoalPoseSaveWorker(payload=payload),
            finished_handler=self._handle_goal_pose_save_finished,
            clear_handler=self._clear_goal_pose_save_thread,
        )

    def _set_goal_pose_form(self, goal_pose):
        goal_pose = goal_pose if isinstance(goal_pose, dict) else {}
        self._syncing_goal_pose_form = True
        try:
            self.goal_pose_id_label.setText(_display(goal_pose.get("goal_pose_id")))
            self._set_combo_data(
                self.goal_pose_zone_combo,
                goal_pose.get("zone_id"),
            )
            self._set_combo_text(
                self.goal_pose_purpose_combo,
                _display(goal_pose.get("purpose")),
            )
            self.goal_pose_x_spin.setValue(_float_or_default(goal_pose.get("pose_x")))
            self.goal_pose_y_spin.setValue(_float_or_default(goal_pose.get("pose_y")))
            self.goal_pose_yaw_spin.setValue(
                _float_or_default(goal_pose.get("pose_yaw"))
            )
            self.goal_pose_frame_id_label.setText(_display(goal_pose.get("frame_id")))
            self.goal_pose_enabled_check.setChecked(bool(goal_pose.get("is_enabled")))
        finally:
            self._syncing_goal_pose_form = False
        self._sync_goal_pose_overlay()

    def _populate_goal_pose_form_options(self):
        current_zone_id = self.goal_pose_zone_combo.currentData()
        self.goal_pose_zone_combo.blockSignals(True)
        try:
            self.goal_pose_zone_combo.clear()
            self.goal_pose_zone_combo.addItem("(연결 없음)", None)
            for zone in self.operation_zone_rows:
                zone_id = zone.get("zone_id")
                zone_name = zone.get("zone_name") or zone_id
                self.goal_pose_zone_combo.addItem(f"{zone_name} ({zone_id})", zone_id)
            self._set_combo_data(self.goal_pose_zone_combo, current_zone_id)
        finally:
            self.goal_pose_zone_combo.blockSignals(False)

    def _mark_goal_pose_dirty(self):
        if self._syncing_goal_pose_form or self.selected_edit_type != "goal_pose":
            return
        self.goal_pose_dirty = True
        self.validation_message_label.setText("목표 좌표 변경 사항이 저장 전입니다.")
        self._sync_goal_pose_overlay()
        self._sync_goal_pose_save_state()

    def _sync_goal_pose_save_state(self):
        can_save = (
            self.selected_edit_type == "goal_pose"
            and self.goal_pose_dirty
            and self.map_canvas.map_loaded
            and self.goal_pose_save_thread is None
        )
        self.save_button.setEnabled(can_save)
        self.discard_button.setEnabled(
            self.selected_edit_type == "goal_pose" and self.goal_pose_dirty
        )

    def _build_goal_pose_update_payload(self):
        return {
            "goal_pose_id": self.goal_pose_id_label.text().strip(),
            "expected_updated_at": self.selected_goal_pose.get("updated_at"),
            "zone_id": self.goal_pose_zone_combo.currentData(),
            "purpose": self.goal_pose_purpose_combo.currentText().strip(),
            "pose_x": self.goal_pose_x_spin.value(),
            "pose_y": self.goal_pose_y_spin.value(),
            "pose_yaw": self.goal_pose_yaw_spin.value(),
            "frame_id": self.goal_pose_frame_id_label.text().strip(),
            "is_enabled": self.goal_pose_enabled_check.isChecked(),
        }

    def _handle_goal_pose_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.goal_pose_dirty = True
            self._sync_goal_pose_save_state()
            return

        response = response if isinstance(response, dict) else {}
        updated_goal_pose = response.get("goal_pose")
        if not isinstance(updated_goal_pose, dict):
            self.validation_message_label.setText("목표 좌표 저장 결과가 비어 있습니다.")
            self.goal_pose_dirty = True
            self._sync_goal_pose_save_state()
            return

        self._replace_goal_pose_row(updated_goal_pose)
        self.selected_goal_pose = dict(updated_goal_pose)
        self._set_goal_pose_form(updated_goal_pose)
        self.goal_pose_dirty = False
        self.validation_message_label.setText("목표 좌표를 저장했습니다.")
        self._sync_goal_pose_save_state()

    def _replace_goal_pose_row(self, updated_goal_pose):
        goal_pose_id = updated_goal_pose.get("goal_pose_id")
        for index, row in enumerate(self.goal_pose_rows):
            if row.get("goal_pose_id") == goal_pose_id:
                self.goal_pose_rows[index] = dict(updated_goal_pose)
                self.selected_goal_pose_index = index
                break
        else:
            self.goal_pose_rows.append(dict(updated_goal_pose))
            self.selected_goal_pose_index = len(self.goal_pose_rows) - 1

        self.current_bundle["goal_poses"] = self.goal_pose_rows
        self._set_table_rows(
            self.tables["goalPoseTable"],
            self.goal_pose_rows,
            [
                "goal_pose_id",
                "purpose",
                ("zone_name", _zone_label),
                ("pose", _goal_pose_text),
            ],
        )

    @staticmethod
    def _set_combo_data(combo, value):
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0 if combo.count() else -1)

    @staticmethod
    def _set_combo_text(combo, text):
        if combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)

    def _handle_load_finished(self, ok, payload):
        if ok:
            self.apply_loaded_coordinate_config(payload)
        else:
            self.apply_load_error(payload)
        self.refresh_button.setEnabled(True)

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None

    def _clear_goal_pose_save_thread(self):
        self.goal_pose_save_thread = None
        self.goal_pose_save_worker = None
        self._sync_goal_pose_save_state()

    def _clear_operation_zone_save_thread(self):
        self.operation_zone_save_thread = None
        self.operation_zone_save_worker = None
        self._sync_operation_zone_save_state()

    def _clear_patrol_area_save_thread(self):
        self.patrol_area_save_thread = None
        self.patrol_area_save_worker = None
        self._sync_patrol_area_save_state()

    def _stop_load_thread(self):
        if self.load_thread is None:
            return True
        if self.load_thread.isRunning():
            self.load_thread.quit()
            stopped = bool(self.load_thread.wait(self._worker_stop_wait_ms))
        else:
            stopped = True
        if stopped:
            self._clear_load_thread()
        return stopped

    def shutdown(self):
        self._stop_load_thread()
        self._stop_operation_zone_save_thread()
        self._stop_goal_pose_save_thread()
        self._stop_patrol_area_save_thread()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    @staticmethod
    def _set_table_rows(table, rows, columns):
        rows = rows if isinstance(rows, list) else []
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row = row if isinstance(row, dict) else {}
            for column_index, column in enumerate(columns):
                value = _column_value(row, column)
                table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _stop_goal_pose_save_thread(self):
        if self.goal_pose_save_thread is None:
            return True
        if self.goal_pose_save_thread.isRunning():
            self.goal_pose_save_thread.quit()
            stopped = bool(
                self.goal_pose_save_thread.wait(self._worker_stop_wait_ms)
            )
        else:
            stopped = True
        if stopped:
            self._clear_goal_pose_save_thread()
        return stopped

    def _stop_operation_zone_save_thread(self):
        if self.operation_zone_save_thread is None:
            return True
        if self.operation_zone_save_thread.isRunning():
            self.operation_zone_save_thread.quit()
            stopped = bool(
                self.operation_zone_save_thread.wait(self._worker_stop_wait_ms)
            )
        else:
            stopped = True
        if stopped:
            self._clear_operation_zone_save_thread()
        return stopped

    def _stop_patrol_area_save_thread(self):
        if self.patrol_area_save_thread is None:
            return True
        if self.patrol_area_save_thread.isRunning():
            self.patrol_area_save_thread.quit()
            stopped = bool(
                self.patrol_area_save_thread.wait(self._worker_stop_wait_ms)
            )
        else:
            stopped = True
        if stopped:
            self._clear_patrol_area_save_thread()
        return stopped


def _is_ok_response(response):
    return isinstance(response, dict) and response.get("result_code") == "OK"


def _format_result_error(response):
    if not isinstance(response, dict):
        return "좌표 설정 요청에 실패했습니다."
    reason_code = response.get("reason_code")
    message = response.get("result_message")
    result_code = response.get("result_code")
    if reason_code and message:
        return f"{reason_code}: {message}"
    if message:
        return str(message)
    if reason_code:
        return str(reason_code)
    return str(result_code or "좌표 설정 요청에 실패했습니다.")


def _decode_base64_asset(value):
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except (binascii.Error, ValueError):
        return b""


def _column_value(row, column):
    if isinstance(column, tuple):
        key, formatter = column
        return formatter(row, row.get(key))
    return _display(row.get(column))


def _display(value):
    if value is None or value == "":
        return "-"
    return str(value)


def _display_empty(value):
    if value is None:
        return ""
    return str(value)


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _patrol_path_poses(path_json):
    path_json = path_json if isinstance(path_json, dict) else {}
    poses = path_json.get("poses")
    if not isinstance(poses, list):
        return []
    return [
        pose
        for pose in (_normalize_patrol_pose(pose) for pose in poses)
        if pose is not None
    ]


def _normalize_patrol_pose(pose):
    if not isinstance(pose, dict):
        return None
    try:
        return {
            "x": float(pose.get("x")),
            "y": float(pose.get("y")),
            "yaw": float(pose.get("yaw", 0.0)),
        }
    except (TypeError, ValueError):
        return None


def _patrol_path_frame_id(patrol_area):
    path_json = patrol_area.get("path_json") if isinstance(patrol_area, dict) else {}
    header = path_json.get("header") if isinstance(path_json, dict) else {}
    if isinstance(header, dict) and header.get("frame_id"):
        return str(header.get("frame_id")).strip()
    if isinstance(patrol_area, dict) and patrol_area.get("path_frame_id"):
        return str(patrol_area.get("path_frame_id")).strip()
    return ""


def _waypoint_number_text(value):
    return f"{_float_or_default(value):.4f}"


def _enabled_text(_row, value):
    return "활성" if bool(value) else "비활성"


def _zone_label(row, value):
    return _display(value or row.get("zone_id"))


def _goal_pose_text(row, _value):
    try:
        x = float(row.get("pose_x"))
        y = float(row.get("pose_y"))
        yaw = float(row.get("pose_yaw"))
    except (TypeError, ValueError):
        return "-"
    return f"x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"


def _waypoint_count_text(row, value):
    if value not in (None, ""):
        return str(value)
    path_json = row.get("path_json")
    poses = path_json.get("poses") if isinstance(path_json, dict) else []
    return str(len(poses)) if isinstance(poses, list) else "0"


__all__ = [
    "CoordinateConfigLoadWorker",
    "CoordinateZoneSettingsPage",
    "GoalPoseSaveWorker",
    "OperationZoneBoundarySaveWorker",
    "OperationZoneSaveWorker",
    "PatrolAreaPathSaveWorker",
]
