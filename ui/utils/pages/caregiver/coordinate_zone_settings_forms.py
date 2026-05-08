from PyQt6.QtCore import Qt
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
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)


GOAL_POSE_PURPOSES = ["PICKUP", "DESTINATION", "DOCK"]
FMS_WAYPOINT_TYPES = [
    "CORRIDOR",
    "ROOM_ENTRY",
    "DOCK_ENTRY",
    "SUPPLY_ENTRY",
    "WAIT_POINT",
    "INTERSECTION",
    "ELEVATOR_ENTRY",
    "OTHER",
]
FMS_ROUTE_SCOPES = ["COMMON", "DELIVERY", "PATROL", "GUIDE"]
FMS_ROUTE_YAW_POLICIES = ["AUTO_NEXT", "FIXED", "KEEP_WAYPOINT"]
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


def build_operation_zone_form(page):
    form = QFrame()
    form.setObjectName("operationZoneEditForm")
    layout = QGridLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)

    page.operation_zone_id_input = QLineEdit()
    page.operation_zone_id_input.setObjectName("operationZoneIdInput")
    page.operation_zone_name_input = QLineEdit()
    page.operation_zone_name_input.setObjectName("operationZoneNameInput")
    page.operation_zone_type_combo = QComboBox()
    page.operation_zone_type_combo.setObjectName("operationZoneTypeCombo")
    page.operation_zone_type_combo.addItems(OPERATION_ZONE_TYPES)
    page.operation_zone_enabled_check = QCheckBox("활성")
    page.operation_zone_enabled_check.setObjectName("operationZoneEnabledCheck")

    rows = [
        ("구역 ID", page.operation_zone_id_input),
        ("구역명", page.operation_zone_name_input),
        ("구역 유형", page.operation_zone_type_combo),
        ("사용 여부", page.operation_zone_enabled_check),
    ]
    _add_grid_rows(layout, rows)

    for widget in [
        page.operation_zone_id_input,
        page.operation_zone_name_input,
        page.operation_zone_type_combo,
        page.operation_zone_enabled_check,
    ]:
        _connect_operation_zone_dirty_signal(page, widget)

    boundary_title = QLabel("boundary vertices")
    boundary_title.setObjectName("fieldLabel")
    page.operation_zone_boundary_table = QTableWidget(0, 3)
    page.operation_zone_boundary_table.setObjectName("operationZoneBoundaryTable")
    page.operation_zone_boundary_table.setHorizontalHeaderLabels(["#", "x", "y"])
    page.operation_zone_boundary_table.horizontalHeader().setStretchLastSection(True)
    page.operation_zone_boundary_table.cellClicked.connect(
        lambda row, _column: page.select_operation_zone_boundary_vertex(row)
    )
    layout.addWidget(boundary_title, len(rows), 0)
    layout.addWidget(page.operation_zone_boundary_table, len(rows), 1)

    page.operation_zone_boundary_x_spin = coordinate_spin("operationZoneBoundaryXSpin")
    page.operation_zone_boundary_y_spin = coordinate_spin("operationZoneBoundaryYSpin")
    layout.addWidget(QLabel("vertex x"), len(rows) + 1, 0)
    layout.addWidget(page.operation_zone_boundary_x_spin, len(rows) + 1, 1)
    layout.addWidget(QLabel("vertex y"), len(rows) + 2, 0)
    layout.addWidget(page.operation_zone_boundary_y_spin, len(rows) + 2, 1)

    boundary_button_row = QHBoxLayout()
    boundary_button_row.setSpacing(8)
    page.operation_zone_boundary_delete_button = QPushButton("꼭짓점 삭제")
    page.operation_zone_boundary_delete_button.setObjectName(
        "operationZoneBoundaryDeleteButton"
    )
    page.operation_zone_boundary_clear_button = QPushButton("boundary 초기화")
    page.operation_zone_boundary_clear_button.setObjectName(
        "operationZoneBoundaryClearButton"
    )
    page.operation_zone_boundary_delete_button.clicked.connect(
        page.delete_selected_operation_zone_boundary_vertex
    )
    page.operation_zone_boundary_clear_button.clicked.connect(
        page.clear_operation_zone_boundary
    )
    boundary_button_row.addWidget(page.operation_zone_boundary_delete_button)
    boundary_button_row.addWidget(page.operation_zone_boundary_clear_button)
    layout.addLayout(boundary_button_row, len(rows) + 3, 1)

    for widget in [
        page.operation_zone_boundary_x_spin,
        page.operation_zone_boundary_y_spin,
    ]:
        widget.valueChanged.connect(
            lambda _value: (
                page._update_selected_operation_zone_boundary_vertex_from_form()
            )
        )

    return form


def build_goal_pose_form(page):
    form = QFrame()
    form.setObjectName("goalPoseEditForm")
    layout = QGridLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)

    page.goal_pose_id_input = QLineEdit()
    page.goal_pose_id_input.setObjectName("goalPoseIdInput")
    page.goal_pose_zone_combo = QComboBox()
    page.goal_pose_zone_combo.setObjectName("goalPoseZoneCombo")
    page.goal_pose_purpose_combo = QComboBox()
    page.goal_pose_purpose_combo.setObjectName("goalPosePurposeCombo")
    page.goal_pose_purpose_combo.addItems(GOAL_POSE_PURPOSES)
    page.goal_pose_x_spin = coordinate_spin("goalPoseXSpin")
    page.goal_pose_y_spin = coordinate_spin("goalPoseYSpin")
    page.goal_pose_yaw_spin = coordinate_spin("goalPoseYawSpin")
    page.goal_pose_frame_id_label = readonly_value_label("goalPoseFrameIdLabel")
    page.goal_pose_enabled_check = QCheckBox("활성")
    page.goal_pose_enabled_check.setObjectName("goalPoseEnabledCheck")

    _add_grid_rows(
        layout,
        [
            ("좌표 ID", page.goal_pose_id_input),
            ("연결 구역", page.goal_pose_zone_combo),
            ("목적", page.goal_pose_purpose_combo),
            ("x", page.goal_pose_x_spin),
            ("y", page.goal_pose_y_spin),
            ("yaw(rad)", page.goal_pose_yaw_spin),
            ("frame_id", page.goal_pose_frame_id_label),
            ("사용 여부", page.goal_pose_enabled_check),
        ],
    )

    for widget in [
        page.goal_pose_id_input,
        page.goal_pose_zone_combo,
        page.goal_pose_purpose_combo,
        page.goal_pose_x_spin,
        page.goal_pose_y_spin,
        page.goal_pose_yaw_spin,
        page.goal_pose_enabled_check,
    ]:
        _connect_goal_pose_dirty_signal(page, widget)

    return form


def build_patrol_area_form(page):
    form = QFrame()
    form.setObjectName("patrolAreaEditForm")
    layout = QVBoxLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    summary_layout = QGridLayout()
    summary_layout.setHorizontalSpacing(10)
    summary_layout.setVerticalSpacing(8)
    page.patrol_area_id_input = QLineEdit()
    page.patrol_area_id_input.setObjectName("patrolAreaIdInput")
    page.patrol_area_name_input = QLineEdit()
    page.patrol_area_name_input.setObjectName("patrolAreaNameInput")
    page.patrol_area_revision_label = readonly_value_label("patrolAreaRevisionLabel")
    page.patrol_path_frame_label = readonly_value_label("patrolPathFrameLabel")
    page.patrol_area_enabled_check = QCheckBox("활성")
    page.patrol_area_enabled_check.setObjectName("patrolAreaEnabledCheck")

    _add_grid_rows(
        summary_layout,
        [
            ("순찰 구역 ID", page.patrol_area_id_input),
            ("순찰 구역명", page.patrol_area_name_input),
            ("경로 revision", page.patrol_area_revision_label),
            ("frame_id", page.patrol_path_frame_label),
            ("사용 여부", page.patrol_area_enabled_check),
        ],
    )
    layout.addLayout(summary_layout)

    page.patrol_waypoint_table = QTableWidget(0, 4)
    page.patrol_waypoint_table.setObjectName("patrolWaypointTable")
    page.patrol_waypoint_table.setHorizontalHeaderLabels(["#", "x", "y", "yaw"])
    page.patrol_waypoint_table.horizontalHeader().setStretchLastSection(True)
    page.patrol_waypoint_table.cellClicked.connect(
        lambda row, _column: page.select_patrol_waypoint(row)
    )
    layout.addWidget(page.patrol_waypoint_table)

    waypoint_form = QGridLayout()
    waypoint_form.setHorizontalSpacing(10)
    waypoint_form.setVerticalSpacing(8)
    page.patrol_waypoint_x_spin = coordinate_spin("patrolWaypointXSpin")
    page.patrol_waypoint_y_spin = coordinate_spin("patrolWaypointYSpin")
    page.patrol_waypoint_yaw_spin = coordinate_spin("patrolWaypointYawSpin")
    _add_grid_rows(
        waypoint_form,
        [
            ("waypoint x", page.patrol_waypoint_x_spin),
            ("waypoint y", page.patrol_waypoint_y_spin),
            ("waypoint yaw(rad)", page.patrol_waypoint_yaw_spin),
        ],
    )
    layout.addLayout(waypoint_form)

    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    page.patrol_waypoint_up_button = QPushButton("위로")
    page.patrol_waypoint_up_button.setObjectName("patrolWaypointUpButton")
    page.patrol_waypoint_down_button = QPushButton("아래로")
    page.patrol_waypoint_down_button.setObjectName("patrolWaypointDownButton")
    page.patrol_waypoint_delete_button = QPushButton("waypoint 삭제")
    page.patrol_waypoint_delete_button.setObjectName("patrolWaypointDeleteButton")
    page.patrol_waypoint_up_button.clicked.connect(
        lambda: page.move_selected_patrol_waypoint(-1)
    )
    page.patrol_waypoint_down_button.clicked.connect(
        lambda: page.move_selected_patrol_waypoint(1)
    )
    page.patrol_waypoint_delete_button.clicked.connect(
        page.delete_selected_patrol_waypoint
    )
    button_row.addWidget(page.patrol_waypoint_up_button)
    button_row.addWidget(page.patrol_waypoint_down_button)
    button_row.addWidget(page.patrol_waypoint_delete_button)
    layout.addLayout(button_row)

    for widget in [
        page.patrol_area_id_input,
        page.patrol_area_name_input,
        page.patrol_area_enabled_check,
        page.patrol_waypoint_x_spin,
        page.patrol_waypoint_y_spin,
        page.patrol_waypoint_yaw_spin,
    ]:
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _value: page._mark_patrol_area_dirty())
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _value: page._mark_patrol_area_dirty())
        else:
            widget.valueChanged.connect(
                lambda _value: page._update_selected_patrol_waypoint_from_form()
            )

    return form


def build_fms_waypoint_form(page):
    form = QFrame()
    form.setObjectName("fmsWaypointEditForm")
    layout = QGridLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)

    page.fms_waypoint_id_input = QLineEdit()
    page.fms_waypoint_id_input.setObjectName("fmsWaypointIdEdit")
    page.fms_waypoint_name_input = QLineEdit()
    page.fms_waypoint_name_input.setObjectName("fmsWaypointNameEdit")
    page.fms_waypoint_type_combo = QComboBox()
    page.fms_waypoint_type_combo.setObjectName("fmsWaypointTypeCombo")
    page.fms_waypoint_type_combo.addItems(FMS_WAYPOINT_TYPES)
    page.fms_waypoint_x_spin = coordinate_spin("fmsWaypointXSpin")
    page.fms_waypoint_y_spin = coordinate_spin("fmsWaypointYSpin")
    page.fms_waypoint_yaw_spin = coordinate_spin("fmsWaypointYawSpin")
    page.fms_waypoint_frame_id_label = readonly_value_label("fmsWaypointFrameIdLabel")
    page.fms_waypoint_snap_group_input = QLineEdit()
    page.fms_waypoint_snap_group_input.setObjectName("fmsWaypointSnapGroupEdit")
    page.fms_waypoint_enabled_check = QCheckBox("활성")
    page.fms_waypoint_enabled_check.setObjectName("fmsWaypointEnabledCheck")

    _add_grid_rows(
        layout,
        [
            ("waypoint ID", page.fms_waypoint_id_input),
            ("표시 이름", page.fms_waypoint_name_input),
            ("유형", page.fms_waypoint_type_combo),
            ("x", page.fms_waypoint_x_spin),
            ("y", page.fms_waypoint_y_spin),
            ("yaw(rad)", page.fms_waypoint_yaw_spin),
            ("frame_id", page.fms_waypoint_frame_id_label),
            ("snap group", page.fms_waypoint_snap_group_input),
            ("사용 여부", page.fms_waypoint_enabled_check),
        ],
    )

    for widget in [
        page.fms_waypoint_id_input,
        page.fms_waypoint_name_input,
        page.fms_waypoint_snap_group_input,
    ]:
        widget.textChanged.connect(lambda _value: page._mark_fms_waypoint_dirty())

    for widget in [
        page.fms_waypoint_type_combo,
        page.fms_waypoint_x_spin,
        page.fms_waypoint_y_spin,
        page.fms_waypoint_yaw_spin,
        page.fms_waypoint_enabled_check,
    ]:
        _connect_fms_waypoint_dirty_signal(page, widget)

    return form


def build_fms_edge_form(page):
    form = QFrame()
    form.setObjectName("fmsEdgeEditForm")
    layout = QGridLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)

    page.fms_edge_id_input = QLineEdit()
    page.fms_edge_id_input.setObjectName("fmsEdgeIdEdit")
    page.fms_edge_from_waypoint_combo = QComboBox()
    page.fms_edge_from_waypoint_combo.setObjectName("fmsEdgeFromWaypointCombo")
    page.fms_edge_to_waypoint_combo = QComboBox()
    page.fms_edge_to_waypoint_combo.setObjectName("fmsEdgeToWaypointCombo")
    page.fms_edge_bidirectional_check = QCheckBox("양방향")
    page.fms_edge_bidirectional_check.setObjectName("fmsEdgeBidirectionalCheck")
    page.fms_edge_traversal_cost_spin = QDoubleSpinBox()
    page.fms_edge_traversal_cost_spin.setObjectName("fmsEdgeTraversalCostSpin")
    page.fms_edge_traversal_cost_spin.setRange(0.0, 100000.0)
    page.fms_edge_traversal_cost_spin.setDecimals(4)
    page.fms_edge_traversal_cost_spin.setSingleStep(0.1)
    page.fms_edge_priority_spin = QSpinBox()
    page.fms_edge_priority_spin.setObjectName("fmsEdgePrioritySpin")
    page.fms_edge_priority_spin.setRange(-100000, 100000)
    page.fms_edge_enabled_check = QCheckBox("활성")
    page.fms_edge_enabled_check.setObjectName("fmsEdgeEnabledCheck")

    _add_grid_rows(
        layout,
        [
            ("edge ID", page.fms_edge_id_input),
            ("from waypoint", page.fms_edge_from_waypoint_combo),
            ("to waypoint", page.fms_edge_to_waypoint_combo),
            ("방향", page.fms_edge_bidirectional_check),
            ("traversal cost", page.fms_edge_traversal_cost_spin),
            ("priority", page.fms_edge_priority_spin),
            ("사용 여부", page.fms_edge_enabled_check),
        ],
    )

    page.fms_edge_id_input.textChanged.connect(
        lambda _value: page._mark_fms_edge_dirty()
    )
    for widget in [
        page.fms_edge_from_waypoint_combo,
        page.fms_edge_to_waypoint_combo,
    ]:
        widget.currentIndexChanged.connect(lambda _value: page._mark_fms_edge_dirty())
    for widget in [
        page.fms_edge_bidirectional_check,
        page.fms_edge_enabled_check,
    ]:
        widget.toggled.connect(lambda _checked: page._mark_fms_edge_dirty())
    page.fms_edge_traversal_cost_spin.valueChanged.connect(
        lambda _value: page._mark_fms_edge_dirty()
    )
    page.fms_edge_priority_spin.valueChanged.connect(
        lambda _value: page._mark_fms_edge_dirty()
    )

    return form


def build_fms_route_form(page):
    form = QFrame()
    form.setObjectName("fmsRouteEditForm")
    layout = QGridLayout(form)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)

    page.fms_route_id_input = QLineEdit()
    page.fms_route_id_input.setObjectName("fmsRouteIdEdit")
    page.fms_route_name_input = QLineEdit()
    page.fms_route_name_input.setObjectName("fmsRouteNameEdit")
    page.fms_route_scope_combo = QComboBox()
    page.fms_route_scope_combo.setObjectName("fmsRouteScopeCombo")
    page.fms_route_scope_combo.addItems(FMS_ROUTE_SCOPES)
    page.fms_route_revision_label = readonly_value_label("fmsRouteRevisionLabel")
    page.fms_route_enabled_check = QCheckBox("활성")
    page.fms_route_enabled_check.setObjectName("fmsRouteEnabledCheck")

    _add_grid_rows(
        layout,
        [
            ("route ID", page.fms_route_id_input),
            ("route 이름", page.fms_route_name_input),
            ("scope", page.fms_route_scope_combo),
            ("revision", page.fms_route_revision_label),
            ("사용 여부", page.fms_route_enabled_check),
        ],
    )

    table_row = 5
    page.fms_route_waypoint_table = QTableWidget(0, 5)
    page.fms_route_waypoint_table.setObjectName("fmsRouteWaypointTable")
    page.fms_route_waypoint_table.setHorizontalHeaderLabels(
        ["#", "waypoint", "stop", "yaw_policy", "dwell"]
    )
    page.fms_route_waypoint_table.horizontalHeader().setStretchLastSection(True)
    page.fms_route_waypoint_table.cellClicked.connect(
        lambda row, _column: page.select_fms_route_waypoint(row)
    )
    layout.addWidget(QLabel("waypoint sequence"), table_row, 0)
    layout.addWidget(page.fms_route_waypoint_table, table_row, 1)

    page.fms_route_waypoint_combo = QComboBox()
    page.fms_route_waypoint_combo.setObjectName("fmsRouteWaypointCombo")
    page.fms_route_yaw_policy_combo = QComboBox()
    page.fms_route_yaw_policy_combo.setObjectName("fmsRouteYawPolicyCombo")
    page.fms_route_yaw_policy_combo.addItems(FMS_ROUTE_YAW_POLICIES)
    page.fms_route_fixed_yaw_spin = coordinate_spin("fmsRouteFixedYawSpin")
    page.fms_route_stop_required_check = QCheckBox("정차")
    page.fms_route_stop_required_check.setObjectName("fmsRouteStopRequiredCheck")
    page.fms_route_dwell_sec_spin = QDoubleSpinBox()
    page.fms_route_dwell_sec_spin.setObjectName("fmsRouteDwellSecSpin")
    page.fms_route_dwell_sec_spin.setRange(0.0, 3600.0)
    page.fms_route_dwell_sec_spin.setDecimals(2)
    page.fms_route_dwell_sec_spin.setSingleStep(0.5)

    for row_offset, (label_text, widget) in enumerate(
        [
            ("waypoint", page.fms_route_waypoint_combo),
            ("yaw_policy", page.fms_route_yaw_policy_combo),
            ("fixed yaw(rad)", page.fms_route_fixed_yaw_spin),
            ("stop", page.fms_route_stop_required_check),
            ("dwell(sec)", page.fms_route_dwell_sec_spin),
        ],
        start=6,
    ):
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label, row_offset, 0)
        layout.addWidget(widget, row_offset, 1)

    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    page.fms_route_waypoint_add_button = QPushButton("waypoint 추가")
    page.fms_route_waypoint_add_button.setObjectName("fmsRouteWaypointAddButton")
    page.fms_route_waypoint_delete_button = QPushButton("waypoint 삭제")
    page.fms_route_waypoint_delete_button.setObjectName("fmsRouteWaypointDeleteButton")
    page.fms_route_waypoint_up_button = QPushButton("위로")
    page.fms_route_waypoint_up_button.setObjectName("fmsRouteWaypointUpButton")
    page.fms_route_waypoint_down_button = QPushButton("아래로")
    page.fms_route_waypoint_down_button.setObjectName("fmsRouteWaypointDownButton")
    page.fms_route_waypoint_add_button.clicked.connect(page.add_fms_route_waypoint)
    page.fms_route_waypoint_delete_button.clicked.connect(
        page.delete_selected_fms_route_waypoint
    )
    page.fms_route_waypoint_up_button.clicked.connect(
        lambda: page.move_selected_fms_route_waypoint(-1)
    )
    page.fms_route_waypoint_down_button.clicked.connect(
        lambda: page.move_selected_fms_route_waypoint(1)
    )
    button_row.addWidget(page.fms_route_waypoint_add_button)
    button_row.addWidget(page.fms_route_waypoint_delete_button)
    button_row.addWidget(page.fms_route_waypoint_up_button)
    button_row.addWidget(page.fms_route_waypoint_down_button)
    layout.addLayout(button_row, 11, 1)

    page.fms_route_id_input.textChanged.connect(
        lambda _value: page._mark_fms_route_dirty()
    )
    page.fms_route_name_input.textChanged.connect(
        lambda _value: page._mark_fms_route_dirty()
    )
    page.fms_route_scope_combo.currentIndexChanged.connect(
        lambda _index: page._mark_fms_route_dirty()
    )
    page.fms_route_enabled_check.toggled.connect(
        lambda _checked: page._mark_fms_route_dirty()
    )
    for widget in [
        page.fms_route_waypoint_combo,
        page.fms_route_yaw_policy_combo,
    ]:
        widget.currentIndexChanged.connect(
            lambda _index: page._update_selected_fms_route_waypoint_from_form()
        )
    page.fms_route_fixed_yaw_spin.valueChanged.connect(
        lambda _value: page._update_selected_fms_route_waypoint_from_form()
    )
    page.fms_route_stop_required_check.toggled.connect(
        lambda _checked: page._update_selected_fms_route_waypoint_from_form()
    )
    page.fms_route_dwell_sec_spin.valueChanged.connect(
        lambda _value: page._update_selected_fms_route_waypoint_from_form()
    )

    return form


def readonly_value_label(object_name):
    label = QLabel("-")
    label.setObjectName(object_name)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    return label


def coordinate_spin(object_name):
    spin = QDoubleSpinBox()
    spin.setObjectName(object_name)
    spin.setRange(-10000.0, 10000.0)
    spin.setDecimals(4)
    spin.setSingleStep(0.01)
    return spin


def _add_grid_rows(layout, rows):
    for row_index, (label_text, widget) in enumerate(rows):
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label, row_index, 0)
        layout.addWidget(widget, row_index, 1)


def _connect_goal_pose_dirty_signal(page, widget):
    if isinstance(widget, QDoubleSpinBox):
        widget.valueChanged.connect(lambda _value: page._mark_goal_pose_dirty())
    elif isinstance(widget, QComboBox):
        widget.currentIndexChanged.connect(lambda _index: page._mark_goal_pose_dirty())
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(lambda _checked: page._mark_goal_pose_dirty())


def _connect_operation_zone_dirty_signal(page, widget):
    if isinstance(widget, QLineEdit):
        widget.textChanged.connect(lambda _text: page._mark_operation_zone_dirty())
    elif isinstance(widget, QComboBox):
        widget.currentIndexChanged.connect(
            lambda _index: page._mark_operation_zone_dirty()
        )
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(lambda _checked: page._mark_operation_zone_dirty())


def _connect_fms_waypoint_dirty_signal(page, widget):
    if isinstance(widget, QDoubleSpinBox):
        widget.valueChanged.connect(lambda _value: page._mark_fms_waypoint_dirty())
    elif isinstance(widget, QComboBox):
        widget.currentIndexChanged.connect(
            lambda _index: page._mark_fms_waypoint_dirty()
        )
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(lambda _checked: page._mark_fms_waypoint_dirty())


__all__ = [
    "FMS_ROUTE_SCOPES",
    "FMS_ROUTE_YAW_POLICIES",
    "FMS_WAYPOINT_TYPES",
    "build_fms_edge_form",
    "build_fms_route_form",
    "build_fms_waypoint_form",
    "build_goal_pose_form",
    "build_operation_zone_form",
    "build_patrol_area_form",
    "coordinate_spin",
    "readonly_value_label",
]
