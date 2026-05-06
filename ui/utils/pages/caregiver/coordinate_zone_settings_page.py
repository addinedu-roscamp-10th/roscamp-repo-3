import copy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.pages.caregiver.coordinate_boundary_editing import (
    append_boundary_vertex,
    boundary_table_rows,
    boundary_vertex_buttons_state,
    boundary_vertices_from_json,
    clear_boundary_vertices as clear_boundary_vertex_list,
    delete_selected_boundary_vertex as delete_boundary_vertex,
    move_selected_boundary_vertex_to_world as move_boundary_vertex_to_world,
    replace_selected_boundary_vertex,
    selected_boundary_vertex,
)
from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
    build_goal_pose_update_payload,
    goal_pose_from_save_response,
    goal_pose_world_point_from_payload,
)
from ui.utils.pages.caregiver.coordinate_fms_waypoint_editing import (
    build_fms_waypoint_payload,
    fms_waypoint_from_save_response,
    fms_waypoint_row_from_form,
    fms_waypoint_world_point_from_payload,
)
from ui.utils.pages.caregiver.coordinate_fms_edge_editing import (
    build_fms_edge_payload,
    fms_edge_from_save_response,
    fms_edge_row_from_form,
)
from ui.utils.pages.caregiver.coordinate_fms_route_editing import (
    build_fms_route_payload,
    fms_route_from_save_response,
    fms_route_row_from_form,
    fms_route_waypoint_table_rows,
)
from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
    build_operation_zone_boundary_save_payload,
    build_operation_zone_save_payload,
    operation_zone_from_save_response,
)
from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
    build_patrol_area_path_save_payload,
    patrol_area_from_path_save_response,
    patrol_path_poses_from_save_payload,
)
from ui.utils.pages.caregiver.coordinate_pose_editing import (
    coerce_point2d,
    coerce_pose2d,
    nearest_pose_index,
)
from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
    append_patrol_waypoint,
    delete_selected_patrol_waypoint as delete_patrol_waypoint,
    move_selected_patrol_waypoint as move_patrol_waypoint,
    move_selected_patrol_waypoint_to_world as move_patrol_waypoint_to_world,
    patrol_waypoint_buttons_state,
    patrol_waypoint_table_rows,
    replace_selected_patrol_waypoint,
    selected_patrol_waypoint,
)
from ui.utils.pages.caregiver.coordinate_zone_settings_forms import (
    build_fms_edge_form,
    build_fms_route_form,
    build_fms_waypoint_form,
    build_goal_pose_form,
    build_operation_zone_form,
    build_patrol_area_form,
)
from ui.utils.pages.caregiver.coordinate_zone_settings_bundle import (
    FMS_EDGE_TABLE_COLUMNS,
    FMS_ROUTE_TABLE_COLUMNS,
    FMS_WAYPOINT_TABLE_COLUMNS,
    GOAL_POSE_TABLE_COLUMNS,
    OPERATION_ZONE_TABLE_COLUMNS,
    PATROL_AREA_TABLE_COLUMNS,
    find_row_index_by_value,
    normalize_coordinate_config_bundle,
    set_table_rows,
)
from ui.utils.pages.caregiver.coordinate_zone_settings_edit_state import (
    replace_row_by_key,
)
from ui.utils.pages.caregiver.coordinate_zone_settings_workers import (
    CoordinateConfigBatchSaveWorker,
    CoordinateConfigLoadWorker,
    FmsEdgeSaveWorker,
    FmsRouteSaveWorker,
    FmsWaypointSaveWorker,
    GoalPoseSaveWorker,
    OperationZoneBoundarySaveWorker,
    OperationZoneSaveWorker,
    PatrolAreaPathSaveWorker,
)
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard
from ui.utils.widgets.map_overlay import OperationalMapOverlay


ACTIVE_MAP_FIELDS = [
    ("map_id", "map_id"),
    ("map_name", "map_name"),
    ("map_revision", "map_revision"),
    ("frame_id", "frame_id"),
    ("yaml_path", "yaml_path"),
    ("pgm_path", "pgm_path"),
]

DRAFT_STATUS_TABLES = {
    "operation_zone": {
        "object_name": "operationZoneTable",
        "rows_attr": "operation_zone_rows",
        "dirty_attr": "operation_zone_dirty_row_ids",
        "snapshot_key": "operation_zones",
        "row_key": "zone_id",
        "label": "operation_zone",
    },
    "goal_pose": {
        "object_name": "goalPoseTable",
        "rows_attr": "goal_pose_rows",
        "dirty_attr": "goal_pose_dirty_row_ids",
        "snapshot_key": "goal_poses",
        "row_key": "goal_pose_id",
        "label": "goal_pose",
    },
    "fms_waypoint": {
        "object_name": "fmsWaypointTable",
        "rows_attr": "fms_waypoint_rows",
        "dirty_attr": "fms_waypoint_dirty_row_ids",
        "snapshot_key": "fms_waypoints",
        "row_key": "waypoint_id",
        "label": "FMS waypoint",
    },
    "fms_edge": {
        "object_name": "fmsEdgeTable",
        "rows_attr": "fms_edge_rows",
        "dirty_attr": "fms_edge_dirty_row_ids",
        "snapshot_key": "fms_edges",
        "row_key": "edge_id",
        "label": "FMS edge",
    },
    "fms_route": {
        "object_name": "fmsRouteTable",
        "rows_attr": "fms_route_rows",
        "dirty_attr": "fms_route_dirty_row_ids",
        "snapshot_key": "fms_routes",
        "row_key": "route_id",
        "label": "FMS route",
    },
}
DRAFT_STATUS_TABLE_OBJECT_NAMES = {
    config["object_name"] for config in DRAFT_STATUS_TABLES.values()
}

TABLE_CARD_ACTIONS = {
    "operationZoneTable": {
        "table_name": "operation_zone",
        "create_object_name": "operationZoneNewRowButton",
        "create_handler": "start_operation_zone_create",
        "deactivate_object_name": "operationZoneDeactivateRowButton",
        "revert_object_name": "operationZoneRevertRowButton",
    },
    "goalPoseTable": {
        "table_name": "goal_pose",
        "deactivate_object_name": "goalPoseDeactivateRowButton",
        "revert_object_name": "goalPoseRevertRowButton",
    },
    "fmsWaypointTable": {
        "table_name": "fms_waypoint",
        "create_object_name": "fmsWaypointNewRowButton",
        "create_handler": "start_fms_waypoint_create",
        "deactivate_object_name": "fmsWaypointDeactivateRowButton",
        "revert_object_name": "fmsWaypointRevertRowButton",
    },
    "fmsEdgeTable": {
        "table_name": "fms_edge",
        "create_object_name": "fmsEdgeNewRowButton",
        "create_handler": "start_fms_edge_create",
        "deactivate_object_name": "fmsEdgeDeactivateRowButton",
        "revert_object_name": "fmsEdgeRevertRowButton",
    },
    "fmsRouteTable": {
        "table_name": "fms_route",
        "create_object_name": "fmsRouteNewRowButton",
        "create_handler": "start_fms_route_create",
        "deactivate_object_name": "fmsRouteDeactivateRowButton",
        "revert_object_name": "fmsRouteRevertRowButton",
    },
}

DEACTIVATABLE_TABLES = {
    "operation_zone",
    "goal_pose",
    "fms_waypoint",
    "fms_edge",
    "fms_route",
}


class CoordinateZoneSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_map_labels = {}
        self.tables = {}
        self.table_action_buttons = {}
        self.load_thread = None
        self.load_worker = None
        self.coordinate_batch_save_thread = None
        self.coordinate_batch_save_worker = None
        self.goal_pose_save_thread = None
        self.goal_pose_save_worker = None
        self.operation_zone_save_thread = None
        self.operation_zone_save_worker = None
        self.patrol_area_save_thread = None
        self.patrol_area_save_worker = None
        self.fms_waypoint_save_thread = None
        self.fms_waypoint_save_worker = None
        self.fms_edge_save_thread = None
        self.fms_edge_save_worker = None
        self.fms_route_save_thread = None
        self.fms_route_save_worker = None
        self.operation_zone_dirty_row_ids = set()
        self.goal_pose_dirty_row_ids = set()
        self.fms_waypoint_dirty_row_ids = set()
        self.fms_edge_dirty_row_ids = set()
        self.fms_route_dirty_row_ids = set()
        self.failed_coordinate_row_errors = {}
        self._worker_stop_wait_ms = 1500
        self.current_bundle = {}
        self.server_bundle_snapshot = {}
        self.operation_zone_rows = []
        self.goal_pose_rows = []
        self.patrol_area_rows = []
        self.fms_waypoint_rows = []
        self.fms_edge_rows = []
        self.fms_route_rows = []
        self.patrol_waypoint_rows = []
        self.fms_route_waypoint_rows = []
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
        self.selected_fms_waypoint = None
        self.selected_fms_waypoint_index = None
        self.fms_waypoint_mode = None
        self.fms_waypoint_dirty = False
        self._syncing_fms_waypoint_form = False
        self.selected_fms_edge = None
        self.selected_fms_edge_index = None
        self.fms_edge_mode = None
        self.fms_edge_dirty = False
        self._syncing_fms_edge_form = False
        self.selected_fms_route = None
        self.selected_fms_route_index = None
        self.selected_fms_route_waypoint_index = None
        self.fms_route_mode = None
        self.fms_route_dirty = False
        self._syncing_fms_route_form = False
        self._syncing_fms_route_waypoint_form = False
        self._suppress_draft_capture = False
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
        self.time_card = PageTimeCard(show_last_update=False)
        for button in self._build_action_buttons():
            self.time_card.add_action(button)
        header_row.addWidget(self.time_card)

        root.addLayout(header_row)
        root.addWidget(self._build_active_map_bar())
        root.addLayout(self._build_content_row(), 1)

    def _build_action_buttons(self):
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
        return [self.refresh_button, self.discard_button, self.save_button]

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
            label.setObjectName("keyValueKey")
            value = QLabel("-")
            value.setObjectName("keyValueValue")
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
        self.map_canvas = OperationalMapOverlay()
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
        table_row.addWidget(
            self._build_table_card(
                "FMS waypoint",
                "fmsWaypointTable",
                ["waypoint_id", "display_name", "type", "x/y/yaw", "enabled"],
            )
        )
        table_row.addWidget(
            self._build_table_card(
                "FMS edge",
                "fmsEdgeTable",
                ["edge_id", "from", "to", "direction", "enabled"],
            )
        )
        table_row.addWidget(
            self._build_table_card(
                "FMS route",
                "fmsRouteTable",
                ["route_id", "name", "scope", "waypoints", "enabled"],
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

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)
        self._add_table_card_action_buttons(header_row, object_name)
        table_headers = list(headers)
        if object_name in DRAFT_STATUS_TABLE_OBJECT_NAMES:
            table_headers.append("상태")
        table = QTableWidget(0, len(table_headers))
        table.setObjectName(object_name)
        table.setHorizontalHeaderLabels(table_headers)
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
        if object_name == "fmsWaypointTable":
            table.cellClicked.connect(
                lambda row, _column: self.select_fms_waypoint(row)
            )
        if object_name == "fmsEdgeTable":
            table.cellClicked.connect(lambda row, _column: self.select_fms_edge(row))
        if object_name == "fmsRouteTable":
            table.cellClicked.connect(lambda row, _column: self.select_fms_route(row))

        layout.addLayout(header_row)
        layout.addWidget(table)
        return card

    def _add_table_card_action_buttons(self, header_row, object_name):
        config = TABLE_CARD_ACTIONS.get(object_name)
        if not config:
            return
        table_name = config["table_name"]
        buttons = {}
        create_object_name = config.get("create_object_name")
        if create_object_name:
            create_button = QPushButton("+ 새 row")
            create_button.setObjectName(create_object_name)
            create_button.clicked.connect(getattr(self, config["create_handler"]))
            buttons["create"] = create_button
            header_row.addWidget(create_button)

        deactivate_button = QPushButton("비활성화")
        deactivate_button.setObjectName(config["deactivate_object_name"])
        deactivate_button.setEnabled(False)
        deactivate_button.clicked.connect(self.deactivate_selected_row)
        buttons["deactivate"] = deactivate_button
        header_row.addWidget(deactivate_button)

        revert_button = QPushButton("되돌리기")
        revert_button.setObjectName(config["revert_object_name"])
        revert_button.setEnabled(False)
        revert_button.clicked.connect(self.revert_selected_row)
        buttons["revert"] = revert_button
        header_row.addWidget(revert_button)
        self.table_action_buttons[table_name] = buttons

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
        self.change_summary_label = QLabel("미저장 변경 없음")
        self.change_summary_label.setObjectName("coordinateChangeSummaryLabel")
        self.change_summary_label.setWordWrap(True)
        self.edit_placeholder_label = QLabel(
            "목록 또는 맵 marker를 선택하면 구역, 목표 좌표, 순찰 waypoint "
            "편집 폼이 여기에 표시됩니다."
        )
        self.edit_placeholder_label.setObjectName("mutedText")
        self.edit_placeholder_label.setWordWrap(True)
        self.operation_zone_form = build_operation_zone_form(self)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form = build_goal_pose_form(self)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form = build_patrol_area_form(self)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form = build_fms_waypoint_form(self)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form = build_fms_edge_form(self)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form = build_fms_route_form(self)
        self.fms_route_form.setHidden(True)

        self.edit_panel_layout.addWidget(title)
        self.edit_panel_layout.addWidget(self.edit_mode_label)
        self.edit_panel_layout.addWidget(self.change_summary_label)
        self.edit_panel_layout.addWidget(self.edit_placeholder_label)
        self.edit_panel_layout.addWidget(self.operation_zone_form)
        self.edit_panel_layout.addWidget(self.goal_pose_form)
        self.edit_panel_layout.addWidget(self.patrol_area_form)
        self.edit_panel_layout.addWidget(self.fms_waypoint_form)
        self.edit_panel_layout.addWidget(self.fms_edge_form)
        self.edit_panel_layout.addWidget(self.fms_route_form)
        self.edit_panel_layout.addStretch(1)
        return panel

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

    def reset_page(self):
        if self.load_thread is not None:
            return
        if self.map_canvas.map_loaded:
            return
        if self._has_pending_draft_changes() or self._has_local_form_dirty_state():
            return
        if self.operation_zone_boundary_dirty or self.patrol_area_dirty:
            return
        self.load_coordinate_bundle()

    def apply_loaded_coordinate_config(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        bundle = (
            payload.get("bundle") if isinstance(payload.get("bundle"), dict) else {}
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
        selected = self._capture_selected_bundle_selection()
        normalized = normalize_coordinate_config_bundle(bundle)
        self.current_bundle = normalized.source
        self.server_bundle_snapshot = copy.deepcopy(normalized.source)
        self.operation_zone_rows = normalized.operation_zones
        self.goal_pose_rows = normalized.goal_poses
        self.patrol_area_rows = normalized.patrol_areas
        self.fms_waypoint_rows = normalized.fms_waypoints
        self.fms_edge_rows = normalized.fms_edges
        self.fms_route_rows = normalized.fms_routes
        self._clear_dirty_row_sets()
        self.apply_active_map(normalized.map_profile)
        self._populate_goal_pose_form_options()
        self._populate_fms_edge_form_options()
        self._populate_fms_route_waypoint_options()
        self._refresh_bundle_tables()
        self._suppress_draft_capture = True
        try:
            self._restore_selected_bundle_selection(selected)
        finally:
            self._suppress_draft_capture = False
        self._update_coordinate_draft_status_views()

    def _refresh_bundle_tables(self):
        set_table_rows(
            self.tables["operationZoneTable"],
            self.operation_zone_rows,
            OPERATION_ZONE_TABLE_COLUMNS,
        )
        set_table_rows(
            self.tables["goalPoseTable"],
            self.goal_pose_rows,
            GOAL_POSE_TABLE_COLUMNS,
        )
        set_table_rows(
            self.tables["patrolAreaTable"],
            self.patrol_area_rows,
            PATROL_AREA_TABLE_COLUMNS,
        )
        set_table_rows(
            self.tables["fmsWaypointTable"],
            self.fms_waypoint_rows,
            FMS_WAYPOINT_TABLE_COLUMNS,
        )
        set_table_rows(
            self.tables["fmsEdgeTable"],
            self.fms_edge_rows,
            FMS_EDGE_TABLE_COLUMNS,
        )
        set_table_rows(
            self.tables["fmsRouteTable"],
            self.fms_route_rows,
            FMS_ROUTE_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()

    def _draft_status_config(self, table_name):
        return DRAFT_STATUS_TABLES.get(table_name)

    def _dirty_row_ids_for_table(self, table_name):
        config = self._draft_status_config(table_name)
        if not config:
            return set()
        return getattr(self, config["dirty_attr"])

    def _rows_for_draft_table(self, table_name):
        config = self._draft_status_config(table_name)
        if not config:
            return []
        rows = getattr(self, config["rows_attr"])
        return rows if isinstance(rows, list) else []

    def _server_row_by_id(self, table_name, row_id):
        config = self._draft_status_config(table_name)
        if not config:
            return None
        rows = self.server_bundle_snapshot.get(config["snapshot_key"])
        if not isinstance(rows, list):
            return None
        return self._find_row_by_id(rows, config["row_key"], row_id)

    def _replace_server_snapshot_row(self, table_name, row):
        config = self._draft_status_config(table_name)
        if not config:
            return
        rows = self.server_bundle_snapshot.get(config["snapshot_key"])
        replacement = replace_row_by_key(rows, row, config["row_key"])
        self.server_bundle_snapshot[config["snapshot_key"]] = replacement.rows

    def _selected_draft_row_identity(self):
        if self.selected_edit_type == "operation_zone":
            if self.operation_zone_mode == "create" or not self.selected_operation_zone:
                return None
            return ("operation_zone", self.selected_operation_zone.get("zone_id"))
        if self.selected_edit_type == "goal_pose" and self.selected_goal_pose:
            return ("goal_pose", self.selected_goal_pose.get("goal_pose_id"))
        if self.selected_edit_type == "fms_waypoint":
            if self.fms_waypoint_mode == "create" or not self.selected_fms_waypoint:
                return None
            return ("fms_waypoint", self.selected_fms_waypoint.get("waypoint_id"))
        if self.selected_edit_type == "fms_edge":
            if self.fms_edge_mode == "create" or not self.selected_fms_edge:
                return None
            return ("fms_edge", self.selected_fms_edge.get("edge_id"))
        if self.selected_edit_type == "fms_route":
            if self.fms_route_mode == "create" or not self.selected_fms_route:
                return None
            return ("fms_route", self.selected_fms_route.get("route_id"))
        return None

    def _selected_draft_row_is_dirty(self):
        if self.selected_edit_type == "operation_zone":
            return self.operation_zone_mode != "create" and (
                self.operation_zone_dirty
                or self._operation_zone_form_has_metadata_change()
            )
        if self.selected_edit_type == "goal_pose":
            return self.goal_pose_dirty
        if self.selected_edit_type == "fms_waypoint":
            return self.fms_waypoint_mode != "create" and self.fms_waypoint_dirty
        if self.selected_edit_type == "fms_edge":
            return self.fms_edge_mode != "create" and self.fms_edge_dirty
        if self.selected_edit_type == "fms_route":
            return self.fms_route_mode != "create" and self.fms_route_dirty
        return False

    def _has_local_form_dirty_state(self):
        return any(
            [
                self.operation_zone_dirty,
                self.goal_pose_dirty,
                self.patrol_area_dirty,
                self.fms_waypoint_dirty,
                self.fms_edge_dirty,
                self.fms_route_dirty,
            ]
        )

    def _draft_row_has_local_change(self, table_name, row_id):
        dirty_row_ids = self._dirty_row_ids_for_table(table_name)
        if row_id in dirty_row_ids:
            return True
        selected_identity = self._selected_draft_row_identity()
        return (
            selected_identity == (table_name, row_id)
            and self._selected_draft_row_is_dirty()
        )

    def _selected_enabled_value_for_table(self, table_name):
        selected_identity = self._selected_draft_row_identity()
        if not selected_identity or selected_identity[0] != table_name:
            return None
        if table_name == "operation_zone":
            return self.operation_zone_enabled_check.isChecked()
        if table_name == "goal_pose":
            return self.goal_pose_enabled_check.isChecked()
        if table_name == "fms_waypoint":
            return self.fms_waypoint_enabled_check.isChecked()
        if table_name == "fms_edge":
            return self.fms_edge_enabled_check.isChecked()
        if table_name == "fms_route":
            return self.fms_route_enabled_check.isChecked()
        return None

    def _draft_enabled_value(self, table_name, row):
        selected_enabled = self._selected_enabled_value_for_table(table_name)
        if selected_enabled is not None:
            config = self._draft_status_config(table_name)
            row_id = row.get(config["row_key"]) if config else None
            selected_identity = self._selected_draft_row_identity()
            if selected_identity == (table_name, row_id):
                return selected_enabled
        return row.get("is_enabled")

    def _draft_row_status_text(self, table_name, row):
        row = row if isinstance(row, dict) else {}
        config = self._draft_status_config(table_name)
        if not config:
            return "-"
        row_id = row.get(config["row_key"])
        if (table_name, row_id) in self.failed_coordinate_row_errors:
            return "저장 실패"
        if not self._draft_row_has_local_change(table_name, row_id):
            return "-"
        original_row = self._server_row_by_id(table_name, row_id) or {}
        draft_enabled = self._draft_enabled_value(table_name, row)
        if bool(original_row.get("is_enabled")) and draft_enabled is False:
            return "비활성화 예정"
        return "변경됨"

    def _pending_draft_counts_by_table(self):
        counts = {}
        for table_name in DRAFT_STATUS_TABLES:
            counts[table_name] = len(self._dirty_row_ids_for_table(table_name))
        selected_identity = self._selected_draft_row_identity()
        if selected_identity and self._selected_draft_row_is_dirty():
            table_name, row_id = selected_identity
            if row_id not in self._dirty_row_ids_for_table(table_name):
                counts[table_name] = counts.get(table_name, 0) + 1
        return counts

    def _update_change_summary(self):
        if not hasattr(self, "change_summary_label"):
            return
        counts = self._pending_draft_counts_by_table()
        total_count = sum(counts.values())
        failure_count = len(self.failed_coordinate_row_errors)
        if total_count == 0 and failure_count == 0:
            self.change_summary_label.setText("미저장 변경 없음")
            return
        parts = []
        for table_name, config in DRAFT_STATUS_TABLES.items():
            count = counts.get(table_name, 0)
            if count:
                parts.append(f"{config['label']} {count}")
        text = f"미저장 변경 {total_count}개"
        if parts:
            text = f"{text} - {', '.join(parts)}"
        if failure_count:
            text = f"{text} / 저장 실패 {failure_count}개"
        self.change_summary_label.setText(text)

    def _sync_revert_row_button(self):
        for buttons in self.table_action_buttons.values():
            revert_button = buttons.get("revert")
            if revert_button is not None:
                revert_button.setEnabled(False)
        selected_identity = self._selected_draft_row_identity()
        if not selected_identity:
            return
        table_name, row_id = selected_identity
        can_revert = (
            self._draft_row_has_local_change(
                table_name,
                row_id,
            )
            or (table_name, row_id) in self.failed_coordinate_row_errors
        )
        revert_button = self.table_action_buttons.get(table_name, {}).get("revert")
        if revert_button is not None:
            revert_button.setEnabled(can_revert)

    def _clear_failed_coordinate_row_error(self, table_name, row_id):
        self.failed_coordinate_row_errors.pop((table_name, row_id), None)

    def _clear_failed_coordinate_error_for_selected_row(self):
        selected_identity = self._selected_draft_row_identity()
        if selected_identity:
            self._clear_failed_coordinate_row_error(*selected_identity)

    def _update_coordinate_draft_status_views(self):
        for table_name, config in DRAFT_STATUS_TABLES.items():
            table = self.tables.get(config["object_name"])
            if table is None or table.columnCount() == 0:
                continue
            status_column = table.columnCount() - 1
            for row_index, row in enumerate(self._rows_for_draft_table(table_name)):
                if row_index >= table.rowCount():
                    continue
                status_text = self._draft_row_status_text(table_name, row)
                table.setItem(
                    row_index,
                    status_column,
                    QTableWidgetItem(status_text),
                )
        self._update_change_summary()
        self._sync_revert_row_button()

    def _selected_operation_zone_boundary_draft_snapshot(self, row_id):
        if (
            not self.operation_zone_boundary_dirty
            or not self.selected_operation_zone
            or self.selected_operation_zone.get("zone_id") != row_id
        ):
            return None
        return {
            "vertices": [
                dict(vertex) for vertex in self.operation_zone_boundary_vertices
            ],
            "selected_index": self.selected_operation_zone_boundary_vertex_index,
        }

    def _restore_operation_zone_boundary_draft_snapshot(self, snapshot):
        if not snapshot:
            return
        self.operation_zone_boundary_vertices = [
            dict(vertex) for vertex in snapshot.get("vertices") or []
        ]
        self.selected_operation_zone_boundary_vertex_index = snapshot.get(
            "selected_index"
        )
        self.operation_zone_boundary_dirty = True
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._sync_operation_zone_overlay()

    def _capture_selected_bundle_selection(self):
        if (
            self.selected_edit_type == "operation_zone"
            and self.operation_zone_mode == "create"
        ):
            return ("operation_zone_create", None)
        if self.selected_edit_type == "operation_zone" and self.selected_operation_zone:
            return (
                "operation_zone",
                self.selected_operation_zone.get("zone_id"),
            )
        if self.selected_edit_type == "goal_pose" and self.selected_goal_pose:
            return ("goal_pose", self.selected_goal_pose.get("goal_pose_id"))
        if self.selected_edit_type == "patrol_area" and self.selected_patrol_area:
            return ("patrol_area", self.selected_patrol_area.get("patrol_area_id"))
        if self.selected_edit_type == "fms_waypoint" and self.selected_fms_waypoint:
            return ("fms_waypoint", self.selected_fms_waypoint.get("waypoint_id"))
        if self.selected_edit_type == "fms_edge" and self.selected_fms_edge:
            return ("fms_edge", self.selected_fms_edge.get("edge_id"))
        if self.selected_edit_type == "fms_route" and self.selected_fms_route:
            return ("fms_route", self.selected_fms_route.get("route_id"))
        return None

    def _restore_selected_bundle_selection(self, selected):
        if not isinstance(selected, tuple) or len(selected) != 2:
            return
        edit_type, row_id = selected
        if edit_type == "operation_zone":
            row_index = find_row_index_by_value(
                self.operation_zone_rows,
                "zone_id",
                row_id,
            )
            if row_index is not None:
                self.select_operation_zone(row_index)
                return
        elif edit_type == "goal_pose":
            row_index = find_row_index_by_value(
                self.goal_pose_rows,
                "goal_pose_id",
                row_id,
            )
            if row_index is not None:
                self.select_goal_pose(row_index)
                return
        elif edit_type == "patrol_area":
            row_index = find_row_index_by_value(
                self.patrol_area_rows,
                "patrol_area_id",
                row_id,
            )
            if row_index is not None:
                self.select_patrol_area(row_index)
                return
        elif edit_type == "fms_waypoint":
            row_index = find_row_index_by_value(
                self.fms_waypoint_rows,
                "waypoint_id",
                row_id,
            )
            if row_index is not None:
                self.select_fms_waypoint(row_index)
                return
        elif edit_type == "fms_edge":
            row_index = find_row_index_by_value(
                self.fms_edge_rows,
                "edge_id",
                row_id,
            )
            if row_index is not None:
                self.select_fms_edge(row_index)
                return
        elif edit_type == "fms_route":
            row_index = find_row_index_by_value(
                self.fms_route_rows,
                "route_id",
                row_id,
            )
            if row_index is not None:
                self.select_fms_route(row_index)
                return
        self._clear_current_edit_selection()

    def _clear_current_edit_selection(self):
        self.selected_edit_type = None
        self.operation_zone_mode = None
        self.selected_operation_zone = None
        self.selected_operation_zone_index = None
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = False
        self.operation_zone_boundary_vertices = []
        self.selected_operation_zone_boundary_vertex_index = None
        self.selected_goal_pose = None
        self.selected_goal_pose_index = None
        self.goal_pose_dirty = False
        self.selected_patrol_area = None
        self.selected_patrol_area_index = None
        self.patrol_area_dirty = False
        self.patrol_waypoint_rows = []
        self.selected_patrol_waypoint_index = None
        self.selected_fms_waypoint = None
        self.selected_fms_waypoint_index = None
        self.fms_waypoint_mode = None
        self.fms_waypoint_dirty = False
        self.selected_fms_edge = None
        self.selected_fms_edge_index = None
        self.fms_edge_mode = None
        self.fms_edge_dirty = False
        self.selected_fms_route = None
        self.selected_fms_route_index = None
        self.fms_route_mode = None
        self.fms_route_dirty = False
        self.fms_route_waypoint_rows = []
        self.selected_fms_route_waypoint_index = None
        self.edit_mode_label.setText("선택 모드")
        self.edit_placeholder_label.setHidden(False)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.map_canvas.clear_configuration_overlay()
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self._sync_deactivate_row_button()
        self._sync_revert_row_button()

    def _clear_dirty_row_sets(self):
        self.operation_zone_dirty_row_ids.clear()
        self.goal_pose_dirty_row_ids.clear()
        self.fms_waypoint_dirty_row_ids.clear()
        self.fms_edge_dirty_row_ids.clear()
        self.fms_route_dirty_row_ids.clear()
        self.failed_coordinate_row_errors.clear()

    def _has_pending_draft_changes(self):
        return any(
            [
                self.operation_zone_dirty_row_ids,
                self.goal_pose_dirty_row_ids,
                self.fms_waypoint_dirty_row_ids,
                self.fms_edge_dirty_row_ids,
                self.fms_route_dirty_row_ids,
            ]
        )

    def _any_save_thread_running(self):
        return any(
            thread is not None
            for thread in [
                self.coordinate_batch_save_thread,
                self.operation_zone_save_thread,
                self.goal_pose_save_thread,
                self.patrol_area_save_thread,
                self.fms_waypoint_save_thread,
                self.fms_edge_save_thread,
                self.fms_route_save_thread,
            ]
        )

    def _sync_page_save_state(self, *, expected_edit_type, dirty):
        selected_dirty = self.selected_edit_type == expected_edit_type and bool(dirty)
        pending_dirty = self._has_pending_draft_changes()
        can_save = (
            bool(self.map_canvas.map_loaded)
            and not self._any_save_thread_running()
            and (selected_dirty or pending_dirty)
        )
        self.save_button.setEnabled(can_save)
        self.discard_button.setEnabled(selected_dirty or pending_dirty)
        self._sync_deactivate_row_button()
        self._update_coordinate_draft_status_views()

    def _operation_zone_form_has_metadata_change(self):
        if (
            self.selected_edit_type != "operation_zone"
            or self.operation_zone_mode == "create"
            or not self.selected_operation_zone
        ):
            return False
        payload = self._build_operation_zone_save_payload()
        selected = self.selected_operation_zone
        return (
            payload.get("zone_id") != str(selected.get("zone_id") or "").strip()
            or payload.get("zone_name") != str(selected.get("zone_name") or "").strip()
            or payload.get("zone_type") != str(selected.get("zone_type") or "").strip()
            or bool(payload.get("is_enabled")) != bool(selected.get("is_enabled"))
        )

    def _sync_deactivate_row_button(self):
        for table_name, buttons in self.table_action_buttons.items():
            deactivate_button = buttons.get("deactivate")
            if deactivate_button is None:
                continue
            deactivate_button.setEnabled(
                table_name == self.selected_edit_type
                and table_name in DEACTIVATABLE_TABLES
            )

    def _capture_current_form_to_draft(self):
        if self._suppress_draft_capture:
            return
        if self.selected_edit_type == "operation_zone":
            self._capture_operation_zone_form_to_draft()
        elif self.selected_edit_type == "goal_pose":
            self._capture_goal_pose_form_to_draft()
        elif self.selected_edit_type == "fms_waypoint":
            self._capture_fms_waypoint_form_to_draft()
        elif self.selected_edit_type == "fms_edge":
            self._capture_fms_edge_form_to_draft()
        elif self.selected_edit_type == "fms_route":
            self._capture_fms_route_form_to_draft()

    def _capture_operation_zone_form_to_draft(self):
        if (
            not self.operation_zone_dirty
            and not self._operation_zone_form_has_metadata_change()
        ):
            return
        if (
            self.operation_zone_mode == "create"
            or self.selected_operation_zone_index is None
            or not self.selected_operation_zone
        ):
            return
        payload = self._build_operation_zone_save_payload()
        row = {
            **self.selected_operation_zone,
            "zone_id": payload.get("zone_id"),
            "zone_name": payload.get("zone_name"),
            "zone_type": payload.get("zone_type"),
            "is_enabled": payload.get("is_enabled"),
        }
        self.operation_zone_rows[self.selected_operation_zone_index] = row
        self.selected_operation_zone = dict(row)
        self.operation_zone_dirty_row_ids.add(row["zone_id"])
        self._clear_failed_coordinate_row_error("operation_zone", row["zone_id"])
        self.current_bundle["operation_zones"] = self.operation_zone_rows
        set_table_rows(
            self.tables["operationZoneTable"],
            self.operation_zone_rows,
            OPERATION_ZONE_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()

    def _capture_goal_pose_form_to_draft(self):
        if (
            not self.goal_pose_dirty
            or self.selected_goal_pose_index is None
            or not self.selected_goal_pose
        ):
            return
        payload = self._build_goal_pose_update_payload()
        row = {
            **self.selected_goal_pose,
            "goal_pose_id": payload.get("goal_pose_id"),
            "zone_id": payload.get("zone_id"),
            "zone_name": self._zone_name_for_id(payload.get("zone_id")),
            "purpose": payload.get("purpose"),
            "pose_x": payload.get("pose_x"),
            "pose_y": payload.get("pose_y"),
            "pose_yaw": payload.get("pose_yaw"),
            "frame_id": payload.get("frame_id"),
            "is_enabled": payload.get("is_enabled"),
        }
        self.goal_pose_rows[self.selected_goal_pose_index] = row
        self.selected_goal_pose = dict(row)
        self.goal_pose_dirty_row_ids.add(row["goal_pose_id"])
        self._clear_failed_coordinate_row_error("goal_pose", row["goal_pose_id"])
        self.current_bundle["goal_poses"] = self.goal_pose_rows
        set_table_rows(
            self.tables["goalPoseTable"],
            self.goal_pose_rows,
            GOAL_POSE_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()

    def _capture_fms_waypoint_form_to_draft(self):
        if (
            not self.fms_waypoint_dirty
            or self.fms_waypoint_mode == "create"
            or self.selected_fms_waypoint_index is None
            or not self.selected_fms_waypoint
        ):
            return
        row = {
            **self.selected_fms_waypoint,
            **fms_waypoint_row_from_form(self),
        }
        self.fms_waypoint_rows[self.selected_fms_waypoint_index] = row
        self.selected_fms_waypoint = dict(row)
        self.fms_waypoint_dirty_row_ids.add(row["waypoint_id"])
        self._clear_failed_coordinate_row_error("fms_waypoint", row["waypoint_id"])
        self.current_bundle["fms_waypoints"] = self.fms_waypoint_rows
        set_table_rows(
            self.tables["fmsWaypointTable"],
            self.fms_waypoint_rows,
            FMS_WAYPOINT_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()
        self._populate_fms_edge_form_options()
        self._populate_fms_route_waypoint_options()

    def _capture_fms_edge_form_to_draft(self):
        if (
            not self.fms_edge_dirty
            or self.fms_edge_mode == "create"
            or self.selected_fms_edge_index is None
            or not self.selected_fms_edge
        ):
            return
        row = {
            **self.selected_fms_edge,
            **fms_edge_row_from_form(self),
        }
        self.fms_edge_rows[self.selected_fms_edge_index] = row
        self.selected_fms_edge = dict(row)
        self.fms_edge_dirty_row_ids.add(row["edge_id"])
        self._clear_failed_coordinate_row_error("fms_edge", row["edge_id"])
        self.current_bundle["fms_edges"] = self.fms_edge_rows
        set_table_rows(
            self.tables["fmsEdgeTable"],
            self.fms_edge_rows,
            FMS_EDGE_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()

    def _capture_fms_route_form_to_draft(self):
        if (
            not self.fms_route_dirty
            or self.fms_route_mode == "create"
            or self.selected_fms_route_index is None
            or not self.selected_fms_route
        ):
            return
        row = {
            **self.selected_fms_route,
            **fms_route_row_from_form(self),
        }
        self.fms_route_rows[self.selected_fms_route_index] = row
        self.selected_fms_route = dict(row)
        self.fms_route_dirty_row_ids.add(row["route_id"])
        self._clear_failed_coordinate_row_error("fms_route", row["route_id"])
        self.current_bundle["fms_routes"] = self.fms_route_rows
        set_table_rows(
            self.tables["fmsRouteTable"],
            self.fms_route_rows,
            FMS_ROUTE_TABLE_COLUMNS,
        )
        self._update_coordinate_draft_status_views()

    def _zone_name_for_id(self, zone_id):
        for zone in self.operation_zone_rows:
            if isinstance(zone, dict) and zone.get("zone_id") == zone_id:
                return zone.get("zone_name")
        return None

    def apply_load_error(self, message):
        self.map_canvas.clear_map("좌표 설정 맵 로드 실패")
        self.validation_message_label.setText(str(message or "좌표 설정 로드 실패"))
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)

    def select_operation_zone(self, row_index):
        self._capture_current_form_to_draft()
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
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("구역 boundary 편집 모드")
        self._clear_patrol_overlay()
        self._set_operation_zone_form(operation_zone, mode="edit")
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = False
        self._sync_operation_zone_save_state()

    def start_operation_zone_create(self):
        self._capture_current_form_to_draft()
        self.selected_edit_type = "operation_zone"
        self.operation_zone_mode = "create"
        self.selected_operation_zone = None
        self.selected_operation_zone_index = None
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(False)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
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
        self._capture_current_form_to_draft()
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
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("목표 좌표 편집 모드")
        self._clear_patrol_overlay()
        self._set_goal_pose_form(goal_pose)
        self.goal_pose_dirty = False
        self._sync_goal_pose_save_state()

    def select_patrol_area(self, row_index):
        self._capture_current_form_to_draft()
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
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("순찰 경로 편집 모드")
        self._set_patrol_area_form(patrol_area)
        self.patrol_area_dirty = False
        self._sync_patrol_area_save_state()

    def select_fms_waypoint(self, row_index):
        self._capture_current_form_to_draft()
        try:
            row_index = int(row_index)
            waypoint = self.fms_waypoint_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "fms_waypoint"
        self.fms_waypoint_mode = "edit"
        self.selected_fms_waypoint_index = row_index
        self.selected_fms_waypoint = dict(waypoint)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(False)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("FMS waypoint 편집 모드")
        self._set_fms_waypoint_form(waypoint, mode="edit")
        self.fms_waypoint_dirty = False
        self._sync_fms_waypoint_save_state()

    def start_fms_waypoint_create(self):
        self._capture_current_form_to_draft()
        next_index = len(self.fms_waypoint_rows) + 1
        waypoint_id = f"waypoint_{next_index:02d}"
        existing_ids = {
            str(row.get("waypoint_id") or "")
            for row in self.fms_waypoint_rows
            if isinstance(row, dict)
        }
        while waypoint_id in existing_ids:
            next_index += 1
            waypoint_id = f"waypoint_{next_index:02d}"

        waypoint = {
            "waypoint_id": waypoint_id,
            "display_name": "새 waypoint",
            "waypoint_type": "CORRIDOR",
            "pose_x": 0.0,
            "pose_y": 0.0,
            "pose_yaw": 0.0,
            "frame_id": self._active_map_frame_id(),
            "snap_group": None,
            "is_enabled": True,
            "updated_at": None,
        }

        self.selected_edit_type = "fms_waypoint"
        self.fms_waypoint_mode = "create"
        self.selected_fms_waypoint_index = None
        self.selected_fms_waypoint = dict(waypoint)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(False)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("FMS waypoint 생성 모드")
        self._set_fms_waypoint_form(waypoint, mode="create")
        self.fms_waypoint_dirty = True
        self.validation_message_label.setText(
            "맵을 클릭해 새 FMS waypoint 위치를 지정하세요."
        )
        self._sync_fms_waypoint_save_state()

    def select_fms_edge(self, row_index):
        self._capture_current_form_to_draft()
        try:
            row_index = int(row_index)
            edge = self.fms_edge_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "fms_edge"
        self.fms_edge_mode = "edit"
        self.selected_fms_edge_index = row_index
        self.selected_fms_edge = dict(edge)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(False)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("FMS edge 편집 모드")
        self._set_fms_edge_form(edge, mode="edit")
        self.fms_edge_dirty = False
        self._sync_fms_edge_save_state()

    def start_fms_edge_create(self):
        self._capture_current_form_to_draft()
        next_index = len(self.fms_edge_rows) + 1
        edge_id = f"edge_{next_index:02d}"
        existing_ids = {
            str(row.get("edge_id") or "")
            for row in self.fms_edge_rows
            if isinstance(row, dict)
        }
        while edge_id in existing_ids:
            next_index += 1
            edge_id = f"edge_{next_index:02d}"

        first = self.fms_waypoint_rows[0] if self.fms_waypoint_rows else {}
        second = self.fms_waypoint_rows[1] if len(self.fms_waypoint_rows) > 1 else {}
        edge = {
            "edge_id": edge_id,
            "from_waypoint_id": first.get("waypoint_id"),
            "to_waypoint_id": second.get("waypoint_id"),
            "is_bidirectional": True,
            "traversal_cost": 1.0,
            "priority": 0,
            "is_enabled": True,
            "updated_at": None,
        }

        self.selected_edit_type = "fms_edge"
        self.fms_edge_mode = "create"
        self.selected_fms_edge_index = None
        self.selected_fms_edge = dict(edge)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(False)
        self.fms_route_form.setHidden(True)
        self.edit_mode_label.setText("FMS edge 생성 모드")
        self._set_fms_edge_form(edge, mode="create")
        self.fms_edge_dirty = True
        self.validation_message_label.setText(
            "FMS edge의 시작/도착 waypoint를 선택하세요."
        )
        self._sync_fms_edge_save_state()

    def select_fms_route(self, row_index):
        self._capture_current_form_to_draft()
        try:
            row_index = int(row_index)
            route = self.fms_route_rows[row_index]
        except (IndexError, TypeError, ValueError):
            return

        self.selected_edit_type = "fms_route"
        self.fms_route_mode = "edit"
        self.selected_fms_route_index = row_index
        self.selected_fms_route = dict(route)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(False)
        self.edit_mode_label.setText("FMS route 편집 모드")
        self._set_fms_route_form(route, mode="edit")
        self.fms_route_dirty = False
        self._sync_fms_route_save_state()

    def start_fms_route_create(self):
        self._capture_current_form_to_draft()
        next_index = len(self.fms_route_rows) + 1
        route_id = f"route_{next_index:02d}"
        existing_ids = {
            str(row.get("route_id") or "")
            for row in self.fms_route_rows
            if isinstance(row, dict)
        }
        while route_id in existing_ids:
            next_index += 1
            route_id = f"route_{next_index:02d}"

        sequence = [
            {
                "sequence_no": index + 1,
                "waypoint_id": row.get("waypoint_id"),
                "yaw_policy": "AUTO_NEXT",
                "fixed_pose_yaw": None,
                "stop_required": True,
                "dwell_sec": None,
            }
            for index, row in enumerate(self.fms_waypoint_rows[:2])
            if isinstance(row, dict) and row.get("waypoint_id")
        ]
        route = {
            "route_id": route_id,
            "route_name": "새 route",
            "route_scope": "COMMON",
            "revision": None,
            "waypoint_sequence": sequence,
            "is_enabled": True,
        }

        self.selected_edit_type = "fms_route"
        self.fms_route_mode = "create"
        self.selected_fms_route_index = None
        self.selected_fms_route = dict(route)
        self.edit_placeholder_label.setHidden(True)
        self.operation_zone_form.setHidden(True)
        self.goal_pose_form.setHidden(True)
        self.patrol_area_form.setHidden(True)
        self.fms_waypoint_form.setHidden(True)
        self.fms_edge_form.setHidden(True)
        self.fms_route_form.setHidden(False)
        self.edit_mode_label.setText("FMS route 생성 모드")
        self._set_fms_route_form(route, mode="create")
        self.fms_route_dirty = True
        self.validation_message_label.setText("FMS route waypoint 순서를 설정하세요.")
        self._sync_fms_route_save_state()

    def handle_map_click(self, world_pose):
        if self.selected_edit_type == "operation_zone":
            self.handle_map_click_for_operation_zone(world_pose)
        elif self.selected_edit_type == "goal_pose":
            self.handle_map_click_for_goal_pose(world_pose)
        elif self.selected_edit_type == "patrol_area":
            self.handle_map_click_for_patrol_area(world_pose)
        elif self.selected_edit_type == "fms_waypoint":
            self.handle_map_click_for_fms_waypoint(world_pose)

    def handle_map_drag(self, world_pose):
        if self.selected_edit_type == "operation_zone":
            self.move_selected_operation_zone_boundary_vertex(world_pose)
        elif self.selected_edit_type == "goal_pose":
            self.handle_map_click_for_goal_pose(world_pose)
        elif self.selected_edit_type == "patrol_area":
            self.move_selected_patrol_waypoint_to_world(world_pose)
        elif self.selected_edit_type == "fms_waypoint":
            self.handle_map_click_for_fms_waypoint(world_pose)

    def handle_map_click_for_operation_zone(self, world_pose):
        if self.selected_edit_type != "operation_zone" or not isinstance(
            world_pose, dict
        ):
            return
        if self.operation_zone_mode == "create":
            self.validation_message_label.setText(
                "새 구역은 먼저 저장한 뒤 boundary를 편집할 수 있습니다."
            )
            return
        vertex = coerce_point2d(world_pose)
        if vertex is None:
            return
        if not self.map_canvas.contains_world_pose(vertex):
            self.validation_message_label.setText(
                "구역 boundary 꼭짓점이 맵 범위를 벗어나 추가할 수 없습니다."
            )
            return

        selected = nearest_pose_index(
            self.operation_zone_boundary_vertices,
            vertex,
        )
        if selected is not None:
            self.select_operation_zone_boundary_vertex(selected)
            return

        edit = append_boundary_vertex(self.operation_zone_boundary_vertices, vertex)
        if edit is None:
            return
        self.operation_zone_boundary_vertices = edit.vertices
        self.selected_operation_zone_boundary_vertex_index = edit.selected_index
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def handle_map_click_for_goal_pose(self, world_pose):
        if self.selected_edit_type != "goal_pose" or not isinstance(world_pose, dict):
            return
        point = coerce_point2d(world_pose)
        if point is None:
            return
        self.goal_pose_x_spin.setValue(point["x"])
        self.goal_pose_y_spin.setValue(point["y"])
        self._mark_goal_pose_dirty()

    def handle_map_click_for_patrol_area(self, world_pose):
        if self.selected_edit_type != "patrol_area" or not isinstance(world_pose, dict):
            return
        pose = coerce_pose2d(world_pose)
        if pose is None:
            return
        if not self.map_canvas.contains_world_pose(pose):
            self.validation_message_label.setText(
                "순찰 waypoint가 맵 범위를 벗어나 추가할 수 없습니다."
            )
            return

        selected = nearest_pose_index(self.patrol_waypoint_rows, pose)
        if selected is not None:
            self.select_patrol_waypoint(selected)
            return

        edit = append_patrol_waypoint(self.patrol_waypoint_rows, pose)
        if edit is None:
            return
        self.patrol_waypoint_rows = edit.waypoints
        self.selected_patrol_waypoint_index = edit.selected_index
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def handle_map_click_for_fms_waypoint(self, world_pose):
        if self.selected_edit_type != "fms_waypoint" or not self.selected_fms_waypoint:
            return
        point = coerce_point2d(world_pose)
        if point is None:
            return
        self.fms_waypoint_x_spin.setValue(point["x"])
        self.fms_waypoint_y_spin.setValue(point["y"])
        self._mark_fms_waypoint_dirty()
        self._sync_fms_waypoint_overlay()

    def deactivate_selected_row(self):
        if self.selected_edit_type == "operation_zone":
            if self.operation_zone_mode == "create":
                self._clear_current_edit_selection()
                return
            self.operation_zone_enabled_check.setChecked(False)
            self._mark_operation_zone_dirty()
        elif self.selected_edit_type == "goal_pose":
            self.goal_pose_enabled_check.setChecked(False)
            self._mark_goal_pose_dirty()
        elif self.selected_edit_type == "fms_waypoint":
            if self.fms_waypoint_mode == "create":
                self._clear_current_edit_selection()
                return
            self.fms_waypoint_enabled_check.setChecked(False)
            self._mark_fms_waypoint_dirty()
            self._capture_fms_waypoint_form_to_draft()
        elif self.selected_edit_type == "fms_edge":
            if self.fms_edge_mode == "create":
                self._clear_current_edit_selection()
                return
            self.fms_edge_enabled_check.setChecked(False)
            self._mark_fms_edge_dirty()
            self._capture_fms_edge_form_to_draft()
        elif self.selected_edit_type == "fms_route":
            if self.fms_route_mode == "create":
                self._clear_current_edit_selection()
                return
            self.fms_route_enabled_check.setChecked(False)
            self._mark_fms_route_dirty()
            self._capture_fms_route_form_to_draft()

    def revert_selected_row(self):
        selected_identity = self._selected_draft_row_identity()
        if not selected_identity:
            return
        table_name, row_id = selected_identity
        original_row = self._server_row_by_id(table_name, row_id)
        if original_row is None:
            self.validation_message_label.setText(
                "선택 row를 서버 snapshot에서 찾을 수 없습니다."
            )
            return

        original_row = copy.deepcopy(original_row)
        self._dirty_row_ids_for_table(table_name).discard(row_id)
        self._clear_failed_coordinate_row_error(table_name, row_id)

        if table_name == "operation_zone":
            self._replace_operation_zone_row(original_row)
            self.selected_operation_zone = dict(original_row)
            self.operation_zone_dirty = False
            self._set_operation_zone_form(original_row, mode="edit")
        elif table_name == "goal_pose":
            self._replace_goal_pose_row(original_row)
            self.selected_goal_pose = dict(original_row)
            self.goal_pose_dirty = False
            self._set_goal_pose_form(original_row)
        elif table_name == "fms_waypoint":
            self._replace_fms_waypoint_row(original_row)
            self.selected_fms_waypoint = dict(original_row)
            self.fms_waypoint_dirty = False
            self._set_fms_waypoint_form(original_row, mode="edit")
        elif table_name == "fms_edge":
            self._replace_fms_edge_row(original_row)
            self.selected_fms_edge = dict(original_row)
            self.fms_edge_dirty = False
            self._set_fms_edge_form(original_row, mode="edit")
        elif table_name == "fms_route":
            self._replace_fms_route_row(original_row)
            self.selected_fms_route = dict(original_row)
            self.fms_route_dirty = False
            self._set_fms_route_form(original_row, mode="edit")

        self.validation_message_label.setText("선택 row 변경을 되돌렸습니다.")
        self._sync_current_edit_save_state()

    def save_current_edit(self):
        self._capture_current_form_to_draft()
        operations = self._build_coordinate_batch_save_operations()
        if operations:
            self._save_coordinate_batch_operations(operations)
            return

        if self.selected_edit_type == "operation_zone":
            self.save_selected_operation_zone()
        elif self.selected_edit_type == "goal_pose":
            self.save_selected_goal_pose()
        elif self.selected_edit_type == "patrol_area":
            self.save_selected_patrol_area_path()
        elif self.selected_edit_type == "fms_waypoint":
            self.save_selected_fms_waypoint()
        elif self.selected_edit_type == "fms_edge":
            self.save_selected_fms_edge()
        elif self.selected_edit_type == "fms_route":
            self.save_selected_fms_route()

    def _save_coordinate_batch_operations(self, operations):
        if self.coordinate_batch_save_thread is not None:
            self.validation_message_label.setText(
                "이전 좌표 설정 저장 요청을 처리하는 중입니다."
            )
            return
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("변경 사항을 저장하는 중입니다.")
        self.coordinate_batch_save_thread, self.coordinate_batch_save_worker = (
            start_worker_thread(
                self,
                worker=CoordinateConfigBatchSaveWorker(operations=operations),
                finished_handler=self._handle_coordinate_batch_save_finished,
                clear_handler=self._clear_coordinate_batch_save_thread,
            )
        )

    def _build_coordinate_batch_save_operations(self):
        self._capture_current_form_to_draft()
        operations = []
        for zone_id in sorted(self.operation_zone_dirty_row_ids):
            row = self._find_row_by_id(self.operation_zone_rows, "zone_id", zone_id)
            if row is None:
                continue
            operations.append(
                {
                    "table": "operation_zone",
                    "row_id": zone_id,
                    "method": "update_operation_zone",
                    "payload": {
                        "zone_id": row.get("zone_id"),
                        "expected_revision": row.get("revision"),
                        "zone_name": row.get("zone_name"),
                        "zone_type": row.get("zone_type"),
                        "is_enabled": bool(row.get("is_enabled")),
                    },
                }
            )
        for goal_pose_id in sorted(self.goal_pose_dirty_row_ids):
            row = self._find_row_by_id(
                self.goal_pose_rows,
                "goal_pose_id",
                goal_pose_id,
            )
            if row is None:
                continue
            operations.append(
                {
                    "table": "goal_pose",
                    "row_id": goal_pose_id,
                    "method": "update_goal_pose",
                    "payload": {
                        "goal_pose_id": row.get("goal_pose_id"),
                        "expected_updated_at": row.get("updated_at"),
                        "zone_id": row.get("zone_id"),
                        "purpose": row.get("purpose"),
                        "pose_x": row.get("pose_x"),
                        "pose_y": row.get("pose_y"),
                        "pose_yaw": row.get("pose_yaw"),
                        "frame_id": row.get("frame_id"),
                        "is_enabled": bool(row.get("is_enabled")),
                    },
                }
            )
        for waypoint_id in sorted(self.fms_waypoint_dirty_row_ids):
            row = self._find_row_by_id(
                self.fms_waypoint_rows,
                "waypoint_id",
                waypoint_id,
            )
            if row is None:
                continue
            operations.append(
                {
                    "table": "fms_waypoint",
                    "row_id": waypoint_id,
                    "method": "upsert_waypoint",
                    "payload": build_fms_waypoint_payload(
                        row,
                        expected_updated_at=row.get("updated_at"),
                    ),
                }
            )
        for edge_id in sorted(self.fms_edge_dirty_row_ids):
            row = self._find_row_by_id(self.fms_edge_rows, "edge_id", edge_id)
            if row is None:
                continue
            operations.append(
                {
                    "table": "fms_edge",
                    "row_id": edge_id,
                    "method": "upsert_edge",
                    "payload": build_fms_edge_payload(
                        row,
                        expected_updated_at=row.get("updated_at"),
                    ),
                }
            )
        for route_id in sorted(self.fms_route_dirty_row_ids):
            row = self._find_row_by_id(self.fms_route_rows, "route_id", route_id)
            if row is None:
                continue
            operations.append(
                {
                    "table": "fms_route",
                    "row_id": route_id,
                    "method": "upsert_route",
                    "payload": build_fms_route_payload(
                        row,
                        expected_revision=row.get("revision"),
                    ),
                }
            )
        return operations

    @staticmethod
    def _find_row_by_id(rows, key, row_id):
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get(key) == row_id:
                return row
        return None

    def discard_current_edit(self):
        if self._has_pending_draft_changes():
            self._clear_dirty_row_sets()
            self.apply_bundle(copy.deepcopy(self.server_bundle_snapshot))
            self.validation_message_label.setText("변경 사항을 취소했습니다.")
            self._sync_current_edit_save_state()
            return

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
                self.validation_message_label.setText("운영 구역 변경을 취소했습니다.")
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
        elif self.selected_edit_type == "fms_waypoint" and self.selected_fms_waypoint:
            if self.fms_waypoint_mode == "create":
                self._clear_current_edit_selection()
                self.validation_message_label.setText(
                    "새 FMS waypoint 입력을 취소했습니다."
                )
                return
            self._set_fms_waypoint_form(
                self.selected_fms_waypoint,
                mode=self.fms_waypoint_mode or "edit",
            )
            self.fms_waypoint_dirty = False
            self.validation_message_label.setText("FMS waypoint 변경을 취소했습니다.")
            self._sync_fms_waypoint_save_state()
        elif self.selected_edit_type == "fms_edge" and self.selected_fms_edge:
            if self.fms_edge_mode == "create":
                self._clear_current_edit_selection()
                self.validation_message_label.setText(
                    "새 FMS edge 입력을 취소했습니다."
                )
                return
            self._set_fms_edge_form(
                self.selected_fms_edge,
                mode=self.fms_edge_mode or "edit",
            )
            self.fms_edge_dirty = False
            self.validation_message_label.setText("FMS edge 변경을 취소했습니다.")
            self._sync_fms_edge_save_state()
        elif self.selected_edit_type == "fms_route" and self.selected_fms_route:
            if self.fms_route_mode == "create":
                self._clear_current_edit_selection()
                self.validation_message_label.setText(
                    "새 FMS route 입력을 취소했습니다."
                )
                return
            self._set_fms_route_form(
                self.selected_fms_route,
                mode=self.fms_route_mode or "edit",
            )
            self.fms_route_dirty = False
            self.validation_message_label.setText("FMS route 변경을 취소했습니다.")
            self._sync_fms_route_save_state()

    def save_selected_operation_zone(self):
        if self.operation_zone_save_thread is not None:
            self.validation_message_label.setText(
                "이전 운영 구역 저장 요청을 처리하는 중입니다."
            )
            return
        if self.operation_zone_boundary_dirty and not self.operation_zone_dirty:
            self.save_selected_operation_zone_boundary()
            return
        if not self.operation_zone_dirty:
            self.validation_message_label.setText(
                "저장할 운영 구역 변경 사항이 없습니다."
            )
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
        self._clear_failed_coordinate_error_for_selected_row()
        self.validation_message_label.setText("운영 구역 변경 사항이 저장 전입니다.")
        self._sync_operation_zone_save_state()

    def _set_operation_zone_boundary_form(self, operation_zone):
        boundary = (
            operation_zone.get("boundary_json")
            if isinstance(operation_zone, dict)
            else None
        )
        self.operation_zone_boundary_vertices = boundary_vertices_from_json(boundary)
        self.selected_operation_zone_boundary_vertex_index = (
            0 if self.operation_zone_boundary_vertices else None
        )
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._sync_operation_zone_overlay()

    def _populate_operation_zone_boundary_table(self):
        table_rows = boundary_table_rows(self.operation_zone_boundary_vertices)
        self.operation_zone_boundary_table.setRowCount(len(table_rows))
        for row_index, row_values in enumerate(table_rows):
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
        selected = selected_boundary_vertex(
            self.operation_zone_boundary_vertices,
            row_index,
        )
        enabled = selected is not None
        button_state = boundary_vertex_buttons_state(
            self.operation_zone_boundary_vertices,
            row_index,
        )
        self._syncing_operation_zone_boundary_form = True
        try:
            self.operation_zone_boundary_x_spin.setEnabled(enabled)
            self.operation_zone_boundary_y_spin.setEnabled(enabled)
            self.operation_zone_boundary_delete_button.setEnabled(
                button_state["delete"]
            )
            self.operation_zone_boundary_clear_button.setEnabled(button_state["clear"])
            if enabled:
                self.operation_zone_boundary_x_spin.setValue(
                    _float_or_default(selected.get("x"))
                )
                self.operation_zone_boundary_y_spin.setValue(
                    _float_or_default(selected.get("y"))
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
        edit = replace_selected_boundary_vertex(
            self.operation_zone_boundary_vertices,
            index,
            x=self.operation_zone_boundary_x_spin.value(),
            y=self.operation_zone_boundary_y_spin.value(),
        )
        if edit is None:
            return
        self.operation_zone_boundary_vertices = edit.vertices
        self._populate_operation_zone_boundary_table()
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def delete_selected_operation_zone_boundary_vertex(self):
        index = self.selected_operation_zone_boundary_vertex_index
        edit = delete_boundary_vertex(self.operation_zone_boundary_vertices, index)
        if edit is None:
            return
        self.operation_zone_boundary_vertices = edit.vertices
        self.selected_operation_zone_boundary_vertex_index = edit.selected_index
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(
            self.selected_operation_zone_boundary_vertex_index
        )
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def clear_operation_zone_boundary(self):
        edit = clear_boundary_vertex_list(self.operation_zone_boundary_vertices)
        if edit is None:
            return
        self.operation_zone_boundary_vertices = edit.vertices
        self.selected_operation_zone_boundary_vertex_index = edit.selected_index
        self._populate_operation_zone_boundary_table()
        self._set_operation_zone_boundary_vertex_form(None)
        self._mark_operation_zone_boundary_dirty()
        self._sync_operation_zone_overlay()

    def move_selected_operation_zone_boundary_vertex(self, world_pose):
        if self.selected_edit_type != "operation_zone" or not isinstance(
            world_pose, dict
        ):
            return
        index = self.selected_operation_zone_boundary_vertex_index
        if index is None or not 0 <= index < len(self.operation_zone_boundary_vertices):
            return
        edit = move_boundary_vertex_to_world(
            self.operation_zone_boundary_vertices,
            index,
            world_pose,
        )
        if edit is None:
            return
        vertex = edit.vertices[edit.selected_index]
        if not self.map_canvas.contains_world_pose(vertex):
            return
        self.operation_zone_boundary_vertices = edit.vertices
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
        dirty = (
            self.operation_zone_dirty
            or self.operation_zone_boundary_dirty
            or self._operation_zone_form_has_metadata_change()
        )
        self._sync_page_save_state(
            expected_edit_type="operation_zone",
            dirty=dirty,
        )

    def _build_operation_zone_save_payload(self):
        return build_operation_zone_save_payload(
            mode=self.operation_zone_mode,
            selected_operation_zone=self.selected_operation_zone,
            map_profile=self.current_bundle.get("map_profile"),
            zone_id=self.operation_zone_id_input.text(),
            zone_name=self.operation_zone_name_input.text(),
            zone_type=self.operation_zone_type_combo.currentText(),
            is_enabled=self.operation_zone_enabled_check.isChecked(),
        )

    def save_selected_operation_zone_boundary(self):
        if self.operation_zone_save_thread is not None:
            self.validation_message_label.setText(
                "이전 운영 구역 저장 요청을 처리하는 중입니다."
            )
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
        return build_operation_zone_boundary_save_payload(
            selected_operation_zone=self.selected_operation_zone,
            boundary_vertices=self.operation_zone_boundary_vertices,
            frame_id=self._active_map_frame_id(),
        )

    def _handle_operation_zone_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.operation_zone_dirty = True
            self._sync_operation_zone_save_state()
            return

        operation_zone = operation_zone_from_save_response(response)
        if operation_zone is None:
            self.validation_message_label.setText(
                "운영 구역 저장 결과가 비어 있습니다."
            )
            self.operation_zone_dirty = True
            self._sync_operation_zone_save_state()
            return

        boundary_dirty = self.operation_zone_boundary_dirty
        pending_boundary_vertices = [
            dict(vertex) for vertex in self.operation_zone_boundary_vertices
        ]
        pending_boundary_index = self.selected_operation_zone_boundary_vertex_index
        self._replace_operation_zone_row(operation_zone)
        self.selected_operation_zone = dict(operation_zone)
        self.operation_zone_mode = "edit"
        self._set_operation_zone_form(operation_zone, mode="edit")
        self.operation_zone_dirty = False
        self.operation_zone_boundary_dirty = boundary_dirty
        if boundary_dirty:
            self.operation_zone_boundary_vertices = pending_boundary_vertices
            self.selected_operation_zone_boundary_vertex_index = pending_boundary_index
            self._populate_operation_zone_boundary_table()
            self._set_operation_zone_boundary_vertex_form(
                self.selected_operation_zone_boundary_vertex_index
            )
            self._sync_operation_zone_overlay()
        self.validation_message_label.setText("운영 구역을 저장했습니다.")
        self._populate_goal_pose_form_options()
        self._sync_operation_zone_save_state()

    def _handle_operation_zone_boundary_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.operation_zone_boundary_dirty = True
            self._sync_operation_zone_save_state()
            return

        operation_zone = operation_zone_from_save_response(response)
        if operation_zone is None:
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
        replacement = replace_row_by_key(
            self.operation_zone_rows,
            operation_zone,
            "zone_id",
        )
        self.operation_zone_rows = replacement.rows
        self.selected_operation_zone_index = replacement.selected_index

        self.current_bundle["operation_zones"] = self.operation_zone_rows
        set_table_rows(
            self.tables["operationZoneTable"],
            self.operation_zone_rows,
            OPERATION_ZONE_TABLE_COLUMNS,
        )

    def save_selected_patrol_area_path(self):
        if self.patrol_area_save_thread is not None:
            return
        if not self.patrol_area_dirty or not self.selected_patrol_area:
            return

        payload = self._build_patrol_area_path_save_payload()
        poses = patrol_path_poses_from_save_payload(payload)
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
        table_rows = patrol_waypoint_table_rows(self.patrol_waypoint_rows)
        self.patrol_waypoint_table.setRowCount(len(table_rows))
        for row_index, row_values in enumerate(table_rows):
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
        selected = selected_patrol_waypoint(self.patrol_waypoint_rows, row_index)
        enabled = selected is not None
        self._syncing_patrol_waypoint_form = True
        try:
            for widget in [
                self.patrol_waypoint_x_spin,
                self.patrol_waypoint_y_spin,
                self.patrol_waypoint_yaw_spin,
            ]:
                widget.setEnabled(enabled)
            if enabled:
                self.patrol_waypoint_x_spin.setValue(
                    _float_or_default(selected.get("x"))
                )
                self.patrol_waypoint_y_spin.setValue(
                    _float_or_default(selected.get("y"))
                )
                self.patrol_waypoint_yaw_spin.setValue(
                    _float_or_default(selected.get("yaw"))
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

        edit = replace_selected_patrol_waypoint(
            self.patrol_waypoint_rows,
            index,
            x=self.patrol_waypoint_x_spin.value(),
            y=self.patrol_waypoint_y_spin.value(),
            yaw=self.patrol_waypoint_yaw_spin.value(),
        )
        if edit is None:
            return
        self.patrol_waypoint_rows = edit.waypoints
        self._populate_patrol_waypoint_table()
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def delete_selected_patrol_waypoint(self):
        index = self.selected_patrol_waypoint_index
        edit = delete_patrol_waypoint(self.patrol_waypoint_rows, index)
        if edit is None:
            return
        self.patrol_waypoint_rows = edit.waypoints
        self.selected_patrol_waypoint_index = edit.selected_index
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def move_selected_patrol_waypoint(self, offset):
        index = self.selected_patrol_waypoint_index
        edit = move_patrol_waypoint(self.patrol_waypoint_rows, index, offset)
        if edit is None:
            return
        self.patrol_waypoint_rows = edit.waypoints
        self.selected_patrol_waypoint_index = edit.selected_index
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(self.selected_patrol_waypoint_index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def move_selected_patrol_waypoint_to_world(self, world_pose):
        if self.selected_edit_type != "patrol_area" or not isinstance(world_pose, dict):
            return
        index = self.selected_patrol_waypoint_index
        if index is None or not 0 <= index < len(self.patrol_waypoint_rows):
            return
        edit = move_patrol_waypoint_to_world(
            self.patrol_waypoint_rows,
            index,
            world_pose,
        )
        if edit is None:
            return
        pose = edit.waypoints[edit.selected_index]
        if not self.map_canvas.contains_world_pose(pose):
            return
        self.patrol_waypoint_rows = edit.waypoints
        self._populate_patrol_waypoint_table()
        self._set_patrol_waypoint_form(index)
        self._mark_patrol_area_dirty()
        self._sync_patrol_overlay()

    def _sync_patrol_waypoint_buttons(self):
        state = patrol_waypoint_buttons_state(
            self.patrol_waypoint_rows,
            self.selected_patrol_waypoint_index,
        )
        self.patrol_waypoint_delete_button.setEnabled(state["delete"])
        self.patrol_waypoint_up_button.setEnabled(state["up"])
        self.patrol_waypoint_down_button.setEnabled(state["down"])

    def _mark_patrol_area_dirty(self):
        if self.selected_edit_type != "patrol_area":
            return
        self.patrol_area_dirty = True
        self.validation_message_label.setText("순찰 경로 변경 사항이 저장 전입니다.")
        self._sync_patrol_area_save_state()

    def _sync_patrol_area_save_state(self):
        self._sync_page_save_state(
            expected_edit_type="patrol_area",
            dirty=self.patrol_area_dirty,
        )

    def _build_patrol_area_path_save_payload(self):
        return build_patrol_area_path_save_payload(
            selected_patrol_area=self.selected_patrol_area,
            patrol_area_id=self.patrol_area_id_label.text(),
            frame_id=self._active_map_frame_id(),
            waypoints=self.patrol_waypoint_rows,
        )

    def _handle_patrol_area_path_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.patrol_area_dirty = True
            self._sync_patrol_area_save_state()
            return

        patrol_area = patrol_area_from_path_save_response(response)
        if patrol_area is None:
            self.validation_message_label.setText(
                "순찰 경로 저장 결과가 비어 있습니다."
            )
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
        replacement = replace_row_by_key(
            self.patrol_area_rows,
            updated_patrol_area,
            "patrol_area_id",
        )
        self.patrol_area_rows = replacement.rows
        self.selected_patrol_area_index = replacement.selected_index

        self.current_bundle["patrol_areas"] = self.patrol_area_rows
        set_table_rows(
            self.tables["patrolAreaTable"],
            self.patrol_area_rows,
            PATROL_AREA_TABLE_COLUMNS,
        )

    def _active_map_frame_id(self):
        map_profile = self.current_bundle.get("map_profile") or {}
        return str(map_profile.get("frame_id") or "map").strip()

    def _sync_operation_zone_overlay(self):
        vertex_pixel_points = [
            pixel
            for pixel in (
                self.map_canvas.world_to_pixel(vertex)
                for vertex in self.operation_zone_boundary_vertices
            )
            if pixel is not None
        ]
        self.map_canvas.show_zone_boundary_editor(
            vertex_pixel_points=vertex_pixel_points,
            selected_index=self.selected_operation_zone_boundary_vertex_index,
        )

    def _sync_goal_pose_overlay(self):
        goal_pose_pixel_points = []
        goal_pose_yaws = []
        for row in self.goal_pose_rows:
            pixel = self.map_canvas.world_to_pixel(
                {"x": row.get("pose_x"), "y": row.get("pose_y")}
            )
            if pixel is None:
                continue
            goal_pose_pixel_points.append(pixel)
            goal_pose_yaws.append(_float_or_default(row.get("pose_yaw")))
        self.map_canvas.show_goal_pose_editor(
            goal_pose_pixel_points=goal_pose_pixel_points,
            goal_pose_yaws=goal_pose_yaws,
            selected_pixel_point=self.map_canvas.world_to_pixel(
                {
                    "x": self.goal_pose_x_spin.value(),
                    "y": self.goal_pose_y_spin.value(),
                }
            ),
            selected_yaw=self.goal_pose_yaw_spin.value(),
        )

    def _sync_patrol_overlay(self):
        route_pixel_points = []
        route_yaws = []
        for pose in self.patrol_waypoint_rows:
            pixel = self.map_canvas.world_to_pixel(pose)
            if pixel is None:
                continue
            route_pixel_points.append(pixel)
            route_yaws.append(_float_or_default(pose.get("yaw")))
        self.map_canvas.show_patrol_path_editor(
            route_pixel_points=route_pixel_points,
            route_yaws=route_yaws,
            selected_waypoint_index=self.selected_patrol_waypoint_index,
        )

    def _sync_fms_waypoint_overlay(self):
        pixel_points = []
        labels = []
        yaws = []
        for row in self.fms_waypoint_rows:
            pixel = self.map_canvas.world_to_pixel(
                {"x": row.get("pose_x"), "y": row.get("pose_y")}
            )
            if pixel is None:
                continue
            pixel_points.append(pixel)
            labels.append(_display(row.get("display_name")))
            yaws.append(_float_or_default(row.get("pose_yaw")))

        selected_pixel = self.map_canvas.world_to_pixel(
            {
                "x": self.fms_waypoint_x_spin.value(),
                "y": self.fms_waypoint_y_spin.value(),
            }
        )
        self.map_canvas.show_fms_waypoint_editor(
            fms_waypoint_pixel_points=pixel_points,
            fms_waypoint_labels=labels,
            fms_waypoint_yaws=yaws,
            selected_pixel_point=selected_pixel,
            selected_yaw=self.fms_waypoint_yaw_spin.value(),
        )

    def _sync_fms_edge_overlay(self):
        waypoint_pixels = {}
        pixel_points = []
        labels = []
        for row in self.fms_waypoint_rows:
            waypoint_id = row.get("waypoint_id")
            pixel = self.map_canvas.world_to_pixel(
                {"x": row.get("pose_x"), "y": row.get("pose_y")}
            )
            if not waypoint_id or pixel is None:
                continue
            waypoint_pixels[waypoint_id] = pixel
            pixel_points.append(pixel)
            labels.append(_display(row.get("display_name")))

        edge_pairs = []
        for edge in self.fms_edge_rows:
            pair = self._fms_edge_pixel_pair(edge, waypoint_pixels=waypoint_pixels)
            if pair is not None:
                edge_pairs.append(pair)

        selected_pair = self._fms_edge_pixel_pair(
            {
                "from_waypoint_id": self.fms_edge_from_waypoint_combo.currentData(),
                "to_waypoint_id": self.fms_edge_to_waypoint_combo.currentData(),
            },
            waypoint_pixels=waypoint_pixels,
        )
        self.map_canvas.show_fms_edge_editor(
            fms_waypoint_pixel_points=pixel_points,
            fms_waypoint_labels=labels,
            fms_edge_pixel_pairs=edge_pairs,
            selected_edge_pixel_pair=selected_pair,
        )

    def _sync_fms_route_overlay(self):
        waypoint_by_id = {
            row.get("waypoint_id"): row
            for row in self.fms_waypoint_rows
            if isinstance(row, dict) and row.get("waypoint_id")
        }
        route_pixel_points = []
        route_labels = []
        for waypoint in self.fms_route_waypoint_rows:
            waypoint_row = waypoint_by_id.get(waypoint.get("waypoint_id"))
            if not waypoint_row:
                continue
            pixel = self.map_canvas.world_to_pixel(
                {"x": waypoint_row.get("pose_x"), "y": waypoint_row.get("pose_y")}
            )
            if pixel is None:
                continue
            route_pixel_points.append(pixel)
            route_labels.append(_display(waypoint_row.get("display_name")))

        self.map_canvas.show_fms_route_editor(
            route_pixel_points=route_pixel_points,
            route_labels=route_labels,
            selected_route_index=self.selected_fms_route_waypoint_index,
        )

    @staticmethod
    def _fms_edge_pixel_pair(edge, *, waypoint_pixels):
        if not isinstance(edge, dict):
            return None
        start = waypoint_pixels.get(edge.get("from_waypoint_id"))
        end = waypoint_pixels.get(edge.get("to_waypoint_id"))
        if start is None or end is None:
            return None
        return (start, end)

    def _clear_patrol_overlay(self):
        self.map_canvas.clear_configuration_overlay()

    def save_selected_goal_pose(self):
        if self.goal_pose_save_thread is not None:
            return
        if not self.goal_pose_dirty or not self.selected_goal_pose:
            return

        payload = self._build_goal_pose_update_payload()
        world_point = goal_pose_world_point_from_payload(payload)
        if world_point is None or not self.map_canvas.contains_world_pose(world_point):
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
        self._clear_failed_coordinate_error_for_selected_row()
        self.validation_message_label.setText("목표 좌표 변경 사항이 저장 전입니다.")
        self._sync_goal_pose_overlay()
        self._sync_goal_pose_save_state()

    def _sync_goal_pose_save_state(self):
        self._sync_page_save_state(
            expected_edit_type="goal_pose",
            dirty=self.goal_pose_dirty,
        )

    def _build_goal_pose_update_payload(self):
        return build_goal_pose_update_payload(
            selected_goal_pose=self.selected_goal_pose,
            goal_pose_id=self.goal_pose_id_label.text(),
            zone_id=self.goal_pose_zone_combo.currentData(),
            purpose=self.goal_pose_purpose_combo.currentText(),
            pose_x=self.goal_pose_x_spin.value(),
            pose_y=self.goal_pose_y_spin.value(),
            pose_yaw=self.goal_pose_yaw_spin.value(),
            frame_id=self.goal_pose_frame_id_label.text(),
            is_enabled=self.goal_pose_enabled_check.isChecked(),
        )

    def _handle_goal_pose_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.goal_pose_dirty = True
            self._sync_goal_pose_save_state()
            return

        updated_goal_pose = goal_pose_from_save_response(response)
        if updated_goal_pose is None:
            self.validation_message_label.setText(
                "목표 좌표 저장 결과가 비어 있습니다."
            )
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
        replacement = replace_row_by_key(
            self.goal_pose_rows,
            updated_goal_pose,
            "goal_pose_id",
        )
        self.goal_pose_rows = replacement.rows
        self.selected_goal_pose_index = replacement.selected_index

        self.current_bundle["goal_poses"] = self.goal_pose_rows
        set_table_rows(
            self.tables["goalPoseTable"],
            self.goal_pose_rows,
            GOAL_POSE_TABLE_COLUMNS,
        )

    def save_selected_fms_waypoint(self):
        if self.fms_waypoint_save_thread is not None:
            return
        if not self.fms_waypoint_dirty or not self.selected_fms_waypoint:
            return

        payload = self._build_fms_waypoint_save_payload()
        if not payload["waypoint_id"] or not payload["display_name"]:
            self.validation_message_label.setText(
                "FMS waypoint ID와 표시 이름을 입력해야 합니다."
            )
            return
        if self.fms_waypoint_mode == "create":
            existing_ids = {
                str(row.get("waypoint_id") or "")
                for row in self.fms_waypoint_rows
                if isinstance(row, dict)
            }
            if payload["waypoint_id"] in existing_ids:
                self.validation_message_label.setText(
                    "이미 존재하는 FMS waypoint ID입니다."
                )
                return

        world_point = fms_waypoint_world_point_from_payload(payload)
        if world_point is None or not self.map_canvas.contains_world_pose(world_point):
            self.validation_message_label.setText(
                "FMS waypoint 좌표가 맵 범위를 벗어나 저장할 수 없습니다."
            )
            return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("FMS waypoint를 저장하는 중입니다.")
        (
            self.fms_waypoint_save_thread,
            self.fms_waypoint_save_worker,
        ) = start_worker_thread(
            self,
            worker=FmsWaypointSaveWorker(payload=payload),
            finished_handler=self._handle_fms_waypoint_save_finished,
            clear_handler=self._clear_fms_waypoint_save_thread,
        )

    def _set_fms_waypoint_form(self, waypoint, *, mode):
        waypoint = waypoint if isinstance(waypoint, dict) else {}
        self._syncing_fms_waypoint_form = True
        try:
            self.fms_waypoint_mode = mode
            self.fms_waypoint_id_input.setReadOnly(mode != "create")
            self.fms_waypoint_id_input.setText(_display(waypoint.get("waypoint_id")))
            self.fms_waypoint_name_input.setText(_display(waypoint.get("display_name")))
            self._set_combo_text(
                self.fms_waypoint_type_combo,
                _display(waypoint.get("waypoint_type") or "CORRIDOR"),
            )
            self.fms_waypoint_x_spin.setValue(_float_or_default(waypoint.get("pose_x")))
            self.fms_waypoint_y_spin.setValue(_float_or_default(waypoint.get("pose_y")))
            self.fms_waypoint_yaw_spin.setValue(
                _float_or_default(waypoint.get("pose_yaw"))
            )
            self.fms_waypoint_frame_id_label.setText(
                _display(waypoint.get("frame_id") or self._active_map_frame_id())
            )
            self.fms_waypoint_snap_group_input.setText(
                _display(waypoint.get("snap_group"))
            )
            self.fms_waypoint_enabled_check.setChecked(
                bool(waypoint.get("is_enabled", True))
            )
        finally:
            self._syncing_fms_waypoint_form = False
        self._sync_fms_waypoint_overlay()

    def _mark_fms_waypoint_dirty(self):
        if self._syncing_fms_waypoint_form:
            return
        if self.selected_edit_type != "fms_waypoint":
            return
        self.fms_waypoint_dirty = True
        self._clear_failed_coordinate_error_for_selected_row()
        self._sync_fms_waypoint_save_state()
        self._sync_fms_waypoint_overlay()

    def _sync_fms_waypoint_save_state(self):
        self._sync_page_save_state(
            expected_edit_type="fms_waypoint",
            dirty=self.fms_waypoint_dirty,
        )

    def _build_fms_waypoint_save_payload(self):
        expected_updated_at = None
        if self.fms_waypoint_mode != "create" and self.selected_fms_waypoint:
            expected_updated_at = self.selected_fms_waypoint.get("updated_at")
        return build_fms_waypoint_payload(
            fms_waypoint_row_from_form(self),
            expected_updated_at=expected_updated_at,
        )

    def _handle_fms_waypoint_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.fms_waypoint_dirty = True
            self._sync_fms_waypoint_save_state()
            return

        updated_waypoint = fms_waypoint_from_save_response(response)
        if updated_waypoint is None:
            self.validation_message_label.setText(
                "FMS waypoint 저장 결과가 비어 있습니다."
            )
            self.fms_waypoint_dirty = True
            self._sync_fms_waypoint_save_state()
            return

        self._replace_fms_waypoint_row(updated_waypoint)
        self.selected_fms_waypoint = dict(updated_waypoint)
        self._set_fms_waypoint_form(updated_waypoint, mode="edit")
        self.fms_waypoint_dirty = False
        self.fms_waypoint_mode = "edit"
        self.validation_message_label.setText("FMS waypoint를 저장했습니다.")
        self._sync_fms_waypoint_save_state()

    def _replace_fms_waypoint_row(self, updated_waypoint):
        replacement = replace_row_by_key(
            self.fms_waypoint_rows,
            updated_waypoint,
            "waypoint_id",
        )
        self.fms_waypoint_rows = replacement.rows
        self.selected_fms_waypoint_index = replacement.selected_index

        self.current_bundle["fms_waypoints"] = self.fms_waypoint_rows
        set_table_rows(
            self.tables["fmsWaypointTable"],
            self.fms_waypoint_rows,
            FMS_WAYPOINT_TABLE_COLUMNS,
        )
        self._sync_fms_waypoint_overlay()
        self._populate_fms_edge_form_options()
        self._populate_fms_route_waypoint_options()
        if self.selected_edit_type == "fms_route":
            self._sync_fms_route_overlay()

    def save_selected_fms_edge(self):
        if self.fms_edge_save_thread is not None:
            return
        if not self.fms_edge_dirty or not self.selected_fms_edge:
            return

        payload = self._build_fms_edge_save_payload()
        if not payload["edge_id"]:
            self.validation_message_label.setText("FMS edge ID를 입력해야 합니다.")
            return
        if not payload["from_waypoint_id"] or not payload["to_waypoint_id"]:
            self.validation_message_label.setText(
                "FMS edge endpoint waypoint를 선택해야 합니다."
            )
            return
        if payload["from_waypoint_id"] == payload["to_waypoint_id"]:
            self.validation_message_label.setText(
                "FMS edge 시작/도착 waypoint는 달라야 합니다."
            )
            return
        if self.fms_edge_mode == "create":
            existing_ids = {
                str(row.get("edge_id") or "")
                for row in self.fms_edge_rows
                if isinstance(row, dict)
            }
            if payload["edge_id"] in existing_ids:
                self.validation_message_label.setText(
                    "이미 존재하는 FMS edge ID입니다."
                )
                return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("FMS edge를 저장하는 중입니다.")
        self.fms_edge_save_thread, self.fms_edge_save_worker = start_worker_thread(
            self,
            worker=FmsEdgeSaveWorker(payload=payload),
            finished_handler=self._handle_fms_edge_save_finished,
            clear_handler=self._clear_fms_edge_save_thread,
        )

    def _set_fms_edge_form(self, edge, *, mode):
        edge = edge if isinstance(edge, dict) else {}
        self._syncing_fms_edge_form = True
        try:
            self.fms_edge_mode = mode
            self.fms_edge_id_input.setReadOnly(mode != "create")
            self.fms_edge_id_input.setText(_display_empty(edge.get("edge_id")))
            self._populate_fms_edge_form_options()
            self._set_combo_data(
                self.fms_edge_from_waypoint_combo,
                edge.get("from_waypoint_id"),
            )
            self._set_combo_data(
                self.fms_edge_to_waypoint_combo,
                edge.get("to_waypoint_id"),
            )
            self.fms_edge_bidirectional_check.setChecked(
                bool(edge.get("is_bidirectional", True))
            )
            self.fms_edge_traversal_cost_spin.setValue(
                _float_or_default(edge.get("traversal_cost"), default=1.0)
            )
            self.fms_edge_priority_spin.setValue(
                int(_float_or_default(edge.get("priority"), default=0.0))
            )
            self.fms_edge_enabled_check.setChecked(bool(edge.get("is_enabled", True)))
        finally:
            self._syncing_fms_edge_form = False
        self._sync_fms_edge_overlay()

    def _populate_fms_edge_form_options(self):
        if not hasattr(self, "fms_edge_from_waypoint_combo"):
            return
        current_from = self.fms_edge_from_waypoint_combo.currentData()
        current_to = self.fms_edge_to_waypoint_combo.currentData()
        for combo, current_value in [
            (self.fms_edge_from_waypoint_combo, current_from),
            (self.fms_edge_to_waypoint_combo, current_to),
        ]:
            combo.blockSignals(True)
            try:
                combo.clear()
                for waypoint in self.fms_waypoint_rows:
                    waypoint_id = waypoint.get("waypoint_id")
                    if not waypoint_id:
                        continue
                    display_name = waypoint.get("display_name") or waypoint_id
                    combo.addItem(f"{display_name} ({waypoint_id})", waypoint_id)
                self._set_combo_data(combo, current_value)
            finally:
                combo.blockSignals(False)

    def _mark_fms_edge_dirty(self):
        if self._syncing_fms_edge_form:
            return
        if self.selected_edit_type != "fms_edge":
            return
        self.fms_edge_dirty = True
        self._clear_failed_coordinate_error_for_selected_row()
        self.validation_message_label.setText("FMS edge 변경 사항이 저장 전입니다.")
        self._sync_fms_edge_save_state()
        self._sync_fms_edge_overlay()

    def _sync_fms_edge_save_state(self):
        self._sync_page_save_state(
            expected_edit_type="fms_edge",
            dirty=self.fms_edge_dirty,
        )

    def _build_fms_edge_save_payload(self):
        expected_updated_at = None
        if self.fms_edge_mode != "create" and self.selected_fms_edge:
            expected_updated_at = self.selected_fms_edge.get("updated_at")
        return build_fms_edge_payload(
            fms_edge_row_from_form(self),
            expected_updated_at=expected_updated_at,
        )

    def _handle_fms_edge_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.fms_edge_dirty = True
            self._sync_fms_edge_save_state()
            return

        updated_edge = fms_edge_from_save_response(response)
        if updated_edge is None:
            self.validation_message_label.setText("FMS edge 저장 결과가 비어 있습니다.")
            self.fms_edge_dirty = True
            self._sync_fms_edge_save_state()
            return

        self._replace_fms_edge_row(updated_edge)
        self.selected_fms_edge = dict(updated_edge)
        self._set_fms_edge_form(updated_edge, mode="edit")
        self.fms_edge_dirty = False
        self.fms_edge_mode = "edit"
        self.validation_message_label.setText("FMS edge를 저장했습니다.")
        self._sync_fms_edge_save_state()

    def _replace_fms_edge_row(self, updated_edge):
        replacement = replace_row_by_key(
            self.fms_edge_rows,
            updated_edge,
            "edge_id",
        )
        self.fms_edge_rows = replacement.rows
        self.selected_fms_edge_index = replacement.selected_index

        self.current_bundle["fms_edges"] = self.fms_edge_rows
        set_table_rows(
            self.tables["fmsEdgeTable"],
            self.fms_edge_rows,
            FMS_EDGE_TABLE_COLUMNS,
        )
        self._sync_fms_edge_overlay()

    def save_selected_fms_route(self):
        if self.fms_route_save_thread is not None:
            return
        if not self.fms_route_dirty or not self.selected_fms_route:
            return

        payload = self._build_fms_route_save_payload()
        if not payload["route_id"] or not payload["route_name"]:
            self.validation_message_label.setText(
                "FMS route ID와 이름을 입력해야 합니다."
            )
            return
        if len(payload["waypoint_sequence"]) < 2:
            self.validation_message_label.setText(
                "FMS route는 최소 2개 waypoint가 필요합니다."
            )
            return
        if self.fms_route_mode == "create":
            existing_ids = {
                str(row.get("route_id") or "")
                for row in self.fms_route_rows
                if isinstance(row, dict)
            }
            if payload["route_id"] in existing_ids:
                self.validation_message_label.setText(
                    "이미 존재하는 FMS route ID입니다."
                )
                return

        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.validation_message_label.setText("FMS route를 저장하는 중입니다.")
        self.fms_route_save_thread, self.fms_route_save_worker = start_worker_thread(
            self,
            worker=FmsRouteSaveWorker(payload=payload),
            finished_handler=self._handle_fms_route_save_finished,
            clear_handler=self._clear_fms_route_save_thread,
        )

    def _set_fms_route_form(self, route, *, mode):
        route = route if isinstance(route, dict) else {}
        self._syncing_fms_route_form = True
        try:
            self.fms_route_mode = mode
            self.fms_route_id_input.setReadOnly(mode != "create")
            self.fms_route_id_input.setText(_display_empty(route.get("route_id")))
            self.fms_route_name_input.setText(_display_empty(route.get("route_name")))
            self._set_combo_text(
                self.fms_route_scope_combo,
                _display_empty(route.get("route_scope")) or "COMMON",
            )
            self.fms_route_revision_label.setText(_display(route.get("revision")))
            self.fms_route_enabled_check.setChecked(bool(route.get("is_enabled", True)))
            self.fms_route_waypoint_rows = [
                dict(row)
                for row in route.get("waypoint_sequence") or []
                if isinstance(row, dict)
            ]
            self.selected_fms_route_waypoint_index = (
                0 if self.fms_route_waypoint_rows else None
            )
        finally:
            self._syncing_fms_route_form = False
        self._populate_fms_route_waypoint_options()
        self._populate_fms_route_waypoint_table()
        self._set_fms_route_waypoint_form(self.selected_fms_route_waypoint_index)
        self._sync_fms_route_overlay()

    def _populate_fms_route_waypoint_options(self):
        if not hasattr(self, "fms_route_waypoint_combo"):
            return
        current_waypoint_id = self.fms_route_waypoint_combo.currentData()
        self.fms_route_waypoint_combo.blockSignals(True)
        try:
            self.fms_route_waypoint_combo.clear()
            for waypoint in self.fms_waypoint_rows:
                waypoint_id = waypoint.get("waypoint_id")
                if not waypoint_id:
                    continue
                display_name = waypoint.get("display_name") or waypoint_id
                self.fms_route_waypoint_combo.addItem(
                    f"{display_name} ({waypoint_id})",
                    waypoint_id,
                )
            self._set_combo_data(self.fms_route_waypoint_combo, current_waypoint_id)
        finally:
            self.fms_route_waypoint_combo.blockSignals(False)

    def _populate_fms_route_waypoint_table(self):
        table_rows = fms_route_waypoint_table_rows(self.fms_route_waypoint_rows)
        self.fms_route_waypoint_table.setRowCount(len(table_rows))
        columns = [
            "sequence_no",
            "waypoint_id",
            "stop_required",
            "yaw_policy",
            "dwell_sec",
        ]
        for row_index, row in enumerate(table_rows):
            for column_index, column in enumerate(columns):
                self.fms_route_waypoint_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(str(row.get(column) or "")),
                )

    def select_fms_route_waypoint(self, row_index):
        try:
            row_index = int(row_index)
        except (TypeError, ValueError):
            return
        if not 0 <= row_index < len(self.fms_route_waypoint_rows):
            return
        self.selected_fms_route_waypoint_index = row_index
        self._set_fms_route_waypoint_form(row_index)
        self._sync_fms_route_overlay()

    def _set_fms_route_waypoint_form(self, row_index):
        enabled = row_index is not None and 0 <= row_index < len(
            self.fms_route_waypoint_rows
        )
        row = self.fms_route_waypoint_rows[row_index] if enabled else {}
        self._syncing_fms_route_waypoint_form = True
        try:
            for widget in [
                self.fms_route_waypoint_combo,
                self.fms_route_yaw_policy_combo,
                self.fms_route_fixed_yaw_spin,
                self.fms_route_stop_required_check,
                self.fms_route_dwell_sec_spin,
            ]:
                widget.setEnabled(enabled)
            if enabled:
                self._set_combo_data(
                    self.fms_route_waypoint_combo,
                    row.get("waypoint_id"),
                )
                self._set_combo_text(
                    self.fms_route_yaw_policy_combo,
                    str(row.get("yaw_policy") or "AUTO_NEXT"),
                )
                self.fms_route_fixed_yaw_spin.setValue(
                    _float_or_default(row.get("fixed_pose_yaw"))
                )
                self.fms_route_stop_required_check.setChecked(
                    bool(row.get("stop_required", True))
                )
                self.fms_route_dwell_sec_spin.setValue(
                    _float_or_default(row.get("dwell_sec"))
                )
            else:
                self._set_combo_data(self.fms_route_waypoint_combo, None)
                self._set_combo_text(self.fms_route_yaw_policy_combo, "AUTO_NEXT")
                self.fms_route_fixed_yaw_spin.setValue(0.0)
                self.fms_route_stop_required_check.setChecked(True)
                self.fms_route_dwell_sec_spin.setValue(0.0)
        finally:
            self._syncing_fms_route_waypoint_form = False
        self._sync_fms_route_waypoint_buttons()

    def _update_selected_fms_route_waypoint_from_form(self):
        if (
            self._syncing_fms_route_waypoint_form
            or self.selected_edit_type != "fms_route"
        ):
            return
        index = self.selected_fms_route_waypoint_index
        if index is None or not 0 <= index < len(self.fms_route_waypoint_rows):
            return
        yaw_policy = self.fms_route_yaw_policy_combo.currentText().strip().upper()
        fixed_yaw = (
            self.fms_route_fixed_yaw_spin.value() if yaw_policy == "FIXED" else None
        )
        self.fms_route_waypoint_rows[index] = {
            "sequence_no": index + 1,
            "waypoint_id": self.fms_route_waypoint_combo.currentData(),
            "yaw_policy": yaw_policy,
            "fixed_pose_yaw": fixed_yaw,
            "stop_required": self.fms_route_stop_required_check.isChecked(),
            "dwell_sec": self.fms_route_dwell_sec_spin.value(),
        }
        self._populate_fms_route_waypoint_table()
        self._mark_fms_route_dirty()
        self._sync_fms_route_overlay()

    def add_fms_route_waypoint(self):
        waypoint_id = self.fms_route_waypoint_combo.currentData()
        if not waypoint_id:
            return
        self.fms_route_waypoint_rows.append(
            {
                "sequence_no": len(self.fms_route_waypoint_rows) + 1,
                "waypoint_id": waypoint_id,
                "yaw_policy": self.fms_route_yaw_policy_combo.currentText().strip()
                or "AUTO_NEXT",
                "fixed_pose_yaw": None,
                "stop_required": True,
                "dwell_sec": None,
            }
        )
        self.selected_fms_route_waypoint_index = len(self.fms_route_waypoint_rows) - 1
        self._renumber_fms_route_waypoints()
        self._populate_fms_route_waypoint_table()
        self._set_fms_route_waypoint_form(self.selected_fms_route_waypoint_index)
        self._mark_fms_route_dirty()
        self._sync_fms_route_overlay()

    def delete_selected_fms_route_waypoint(self):
        index = self.selected_fms_route_waypoint_index
        if index is None or not 0 <= index < len(self.fms_route_waypoint_rows):
            return
        del self.fms_route_waypoint_rows[index]
        self.selected_fms_route_waypoint_index = (
            min(index, len(self.fms_route_waypoint_rows) - 1)
            if self.fms_route_waypoint_rows
            else None
        )
        self._renumber_fms_route_waypoints()
        self._populate_fms_route_waypoint_table()
        self._set_fms_route_waypoint_form(self.selected_fms_route_waypoint_index)
        self._mark_fms_route_dirty()
        self._sync_fms_route_overlay()

    def move_selected_fms_route_waypoint(self, offset):
        index = self.selected_fms_route_waypoint_index
        if index is None or not 0 <= index < len(self.fms_route_waypoint_rows):
            return
        next_index = index + int(offset)
        if not 0 <= next_index < len(self.fms_route_waypoint_rows):
            return
        rows = self.fms_route_waypoint_rows
        rows[index], rows[next_index] = rows[next_index], rows[index]
        self.selected_fms_route_waypoint_index = next_index
        self._renumber_fms_route_waypoints()
        self._populate_fms_route_waypoint_table()
        self._set_fms_route_waypoint_form(next_index)
        self._mark_fms_route_dirty()
        self._sync_fms_route_overlay()

    def _renumber_fms_route_waypoints(self):
        for index, row in enumerate(self.fms_route_waypoint_rows, start=1):
            if isinstance(row, dict):
                row["sequence_no"] = index

    def _sync_fms_route_waypoint_buttons(self):
        index = self.selected_fms_route_waypoint_index
        count = len(self.fms_route_waypoint_rows)
        selected = index is not None and 0 <= index < count
        self.fms_route_waypoint_delete_button.setEnabled(selected)
        self.fms_route_waypoint_up_button.setEnabled(selected and index > 0)
        self.fms_route_waypoint_down_button.setEnabled(selected and index < count - 1)

    def _mark_fms_route_dirty(self):
        if self._syncing_fms_route_form:
            return
        if self.selected_edit_type != "fms_route":
            return
        self.fms_route_dirty = True
        self._clear_failed_coordinate_error_for_selected_row()
        self.validation_message_label.setText("FMS route 변경 사항이 저장 전입니다.")
        self._sync_fms_route_save_state()
        self._sync_fms_route_overlay()

    def _sync_fms_route_save_state(self):
        self._sync_page_save_state(
            expected_edit_type="fms_route",
            dirty=self.fms_route_dirty,
        )

    def _build_fms_route_save_payload(self):
        expected_revision = None
        if self.fms_route_mode != "create" and self.selected_fms_route:
            expected_revision = self.selected_fms_route.get("revision")
        return build_fms_route_payload(
            fms_route_row_from_form(self),
            expected_revision=expected_revision,
        )

    def _handle_fms_route_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self.fms_route_dirty = True
            self._sync_fms_route_save_state()
            return

        updated_route = fms_route_from_save_response(response)
        if updated_route is None:
            self.validation_message_label.setText(
                "FMS route 저장 결과가 비어 있습니다."
            )
            self.fms_route_dirty = True
            self._sync_fms_route_save_state()
            return

        self._replace_fms_route_row(updated_route)
        self.selected_fms_route = dict(updated_route)
        self._set_fms_route_form(updated_route, mode="edit")
        self.fms_route_dirty = False
        self.fms_route_mode = "edit"
        self.validation_message_label.setText("FMS route를 저장했습니다.")
        self._sync_fms_route_save_state()

    def _replace_fms_route_row(self, updated_route):
        replacement = replace_row_by_key(
            self.fms_route_rows,
            updated_route,
            "route_id",
        )
        self.fms_route_rows = replacement.rows
        self.selected_fms_route_index = replacement.selected_index

        self.current_bundle["fms_routes"] = self.fms_route_rows
        set_table_rows(
            self.tables["fmsRouteTable"],
            self.fms_route_rows,
            FMS_ROUTE_TABLE_COLUMNS,
        )
        self._sync_fms_route_overlay()

    def _handle_coordinate_batch_save_finished(self, ok, response):
        if not ok:
            self.validation_message_label.setText(str(response))
            self._sync_current_edit_save_state()
            self._update_coordinate_draft_status_views()
            return

        response = response if isinstance(response, dict) else {}
        successes = response.get("successes") or []
        failures = response.get("failures") or []

        for success in successes:
            self._apply_batch_save_success(success)

        for failure in failures:
            table = failure.get("table")
            row_id = failure.get("row_id")
            if table and row_id:
                self.failed_coordinate_row_errors[(table, row_id)] = (
                    failure.get("error") or failure.get("reason_code") or "저장 실패"
                )

        if failures:
            self.validation_message_label.setText(
                f"{len(failures)}개 변경 사항 저장에 실패했습니다: "
                f"{failures[0].get('error') or failures[0].get('row_id')}"
            )
        else:
            self.server_bundle_snapshot = copy.deepcopy(self.current_bundle)
            self.validation_message_label.setText("변경 사항을 저장했습니다.")

        continue_boundary_save = self._should_continue_operation_zone_boundary_save(
            successes,
            failures,
        )
        self._sync_current_edit_save_state()
        if continue_boundary_save:
            self.save_selected_operation_zone_boundary()

    def _apply_batch_save_success(self, success):
        table = success.get("table")
        row_id = success.get("row_id")
        response = success.get("response")
        self._clear_failed_coordinate_row_error(table, row_id)

        if table == "operation_zone":
            row = operation_zone_from_save_response(response)
            if row is not None:
                boundary_snapshot = (
                    self._selected_operation_zone_boundary_draft_snapshot(row_id)
                )
                self._replace_operation_zone_row(row)
                self._replace_server_snapshot_row(table, row)
                self.operation_zone_dirty_row_ids.discard(row_id)
                if self.selected_operation_zone and (
                    self.selected_operation_zone.get("zone_id") == row_id
                ):
                    self.selected_operation_zone = dict(row)
                    self.operation_zone_dirty = False
                    self._set_operation_zone_form(row, mode="edit")
                    self._restore_operation_zone_boundary_draft_snapshot(
                        boundary_snapshot
                    )
        elif table == "goal_pose":
            row = goal_pose_from_save_response(response)
            if row is not None:
                self._replace_goal_pose_row(row)
                self._replace_server_snapshot_row(table, row)
                self.goal_pose_dirty_row_ids.discard(row_id)
                if self.selected_goal_pose and (
                    self.selected_goal_pose.get("goal_pose_id") == row_id
                ):
                    self.selected_goal_pose = dict(row)
                    self.goal_pose_dirty = False
                    self._set_goal_pose_form(row)
        elif table == "fms_waypoint":
            row = fms_waypoint_from_save_response(response)
            if row is not None:
                self._replace_fms_waypoint_row(row)
                self._replace_server_snapshot_row(table, row)
                self.fms_waypoint_dirty_row_ids.discard(row_id)
                if self.selected_fms_waypoint and (
                    self.selected_fms_waypoint.get("waypoint_id") == row_id
                ):
                    self.selected_fms_waypoint = dict(row)
                    self.fms_waypoint_dirty = False
                    self._set_fms_waypoint_form(row, mode="edit")
        elif table == "fms_edge":
            row = fms_edge_from_save_response(response)
            if row is not None:
                self._replace_fms_edge_row(row)
                self._replace_server_snapshot_row(table, row)
                self.fms_edge_dirty_row_ids.discard(row_id)
                if self.selected_fms_edge and (
                    self.selected_fms_edge.get("edge_id") == row_id
                ):
                    self.selected_fms_edge = dict(row)
                    self.fms_edge_dirty = False
                    self._set_fms_edge_form(row, mode="edit")
        elif table == "fms_route":
            row = fms_route_from_save_response(response)
            if row is not None:
                self._replace_fms_route_row(row)
                self._replace_server_snapshot_row(table, row)
                self.fms_route_dirty_row_ids.discard(row_id)
                if self.selected_fms_route and (
                    self.selected_fms_route.get("route_id") == row_id
                ):
                    self.selected_fms_route = dict(row)
                    self.fms_route_dirty = False
                    self._set_fms_route_form(row, mode="edit")

    def _should_continue_operation_zone_boundary_save(self, successes, failures):
        if (
            self.selected_edit_type != "operation_zone"
            or self.operation_zone_dirty
            or not self.operation_zone_boundary_dirty
            or not self.selected_operation_zone
        ):
            return False
        selected_zone_id = self.selected_operation_zone.get("zone_id")
        if not selected_zone_id:
            return False
        for failure in failures:
            if (
                failure.get("table") == "operation_zone"
                and failure.get("row_id") == selected_zone_id
            ):
                return False
        return any(
            success.get("table") == "operation_zone"
            and success.get("row_id") == selected_zone_id
            for success in successes
        )

    def _sync_current_edit_save_state(self):
        if self.selected_edit_type == "operation_zone":
            self._sync_operation_zone_save_state()
        elif self.selected_edit_type == "goal_pose":
            self._sync_goal_pose_save_state()
        elif self.selected_edit_type == "patrol_area":
            self._sync_patrol_area_save_state()
        elif self.selected_edit_type == "fms_waypoint":
            self._sync_fms_waypoint_save_state()
        elif self.selected_edit_type == "fms_edge":
            self._sync_fms_edge_save_state()
        elif self.selected_edit_type == "fms_route":
            self._sync_fms_route_save_state()
        else:
            self.save_button.setEnabled(
                bool(self.map_canvas.map_loaded)
                and not self._any_save_thread_running()
                and self._has_pending_draft_changes()
            )
            self.discard_button.setEnabled(self._has_pending_draft_changes())
            self._sync_deactivate_row_button()
            self._update_coordinate_draft_status_views()

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

    def _clear_coordinate_batch_save_thread(self):
        self.coordinate_batch_save_thread = None
        self.coordinate_batch_save_worker = None
        self._sync_current_edit_save_state()

    def _clear_goal_pose_save_thread(self):
        self.goal_pose_save_thread = None
        self.goal_pose_save_worker = None
        self._sync_goal_pose_save_state()

    def _clear_fms_waypoint_save_thread(self):
        self.fms_waypoint_save_thread = None
        self.fms_waypoint_save_worker = None
        self._sync_fms_waypoint_save_state()

    def _clear_fms_edge_save_thread(self):
        self.fms_edge_save_thread = None
        self.fms_edge_save_worker = None
        self._sync_fms_edge_save_state()

    def _clear_fms_route_save_thread(self):
        self.fms_route_save_thread = None
        self.fms_route_save_worker = None
        self._sync_fms_route_save_state()

    def _clear_operation_zone_save_thread(self):
        self.operation_zone_save_thread = None
        self.operation_zone_save_worker = None
        self._sync_operation_zone_save_state()

    def _clear_patrol_area_save_thread(self):
        self.patrol_area_save_thread = None
        self.patrol_area_save_worker = None
        self._sync_patrol_area_save_state()

    def _stop_load_thread(self):
        return stop_worker_thread(
            self.load_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_load_thread,
        )

    def shutdown(self):
        self._stop_load_thread()
        self._stop_coordinate_batch_save_thread()
        self._stop_operation_zone_save_thread()
        self._stop_goal_pose_save_thread()
        self._stop_patrol_area_save_thread()
        self._stop_fms_waypoint_save_thread()
        self._stop_fms_edge_save_thread()
        self._stop_fms_route_save_thread()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def _stop_goal_pose_save_thread(self):
        return stop_worker_thread(
            self.goal_pose_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_goal_pose_save_thread,
        )

    def _stop_coordinate_batch_save_thread(self):
        return stop_worker_thread(
            self.coordinate_batch_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_coordinate_batch_save_thread,
        )

    def _stop_fms_waypoint_save_thread(self):
        return stop_worker_thread(
            self.fms_waypoint_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_fms_waypoint_save_thread,
        )

    def _stop_fms_edge_save_thread(self):
        return stop_worker_thread(
            self.fms_edge_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_fms_edge_save_thread,
        )

    def _stop_fms_route_save_thread(self):
        return stop_worker_thread(
            self.fms_route_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_fms_route_save_thread,
        )

    def _stop_operation_zone_save_thread(self):
        return stop_worker_thread(
            self.operation_zone_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_operation_zone_save_thread,
        )

    def _stop_patrol_area_save_thread(self):
        return stop_worker_thread(
            self.patrol_area_save_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_patrol_area_save_thread,
        )


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
        pose for pose in (coerce_pose2d(pose) for pose in poses) if pose is not None
    ]


def _patrol_path_frame_id(patrol_area):
    path_json = patrol_area.get("path_json") if isinstance(patrol_area, dict) else {}
    header = path_json.get("header") if isinstance(path_json, dict) else {}
    if isinstance(header, dict) and header.get("frame_id"):
        return str(header.get("frame_id")).strip()
    if isinstance(patrol_area, dict) and patrol_area.get("path_frame_id"):
        return str(patrol_area.get("path_frame_id")).strip()
    return ""


__all__ = [
    "CoordinateConfigBatchSaveWorker",
    "CoordinateConfigLoadWorker",
    "CoordinateZoneSettingsPage",
    "FmsEdgeSaveWorker",
    "FmsRouteSaveWorker",
    "FmsWaypointSaveWorker",
    "GoalPoseSaveWorker",
    "OperationZoneBoundarySaveWorker",
    "OperationZoneSaveWorker",
    "PatrolAreaPathSaveWorker",
]
