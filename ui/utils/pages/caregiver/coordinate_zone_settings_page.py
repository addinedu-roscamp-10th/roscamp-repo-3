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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.network.service_clients import CoordinateConfigRemoteService
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.map_canvas import MapCanvasWidget


ACTIVE_MAP_FIELDS = [
    ("map_id", "map_id"),
    ("map_name", "map_name"),
    ("map_revision", "map_revision"),
    ("frame_id", "frame_id"),
    ("yaml_path", "yaml_path"),
    ("pgm_path", "pgm_path"),
]
GOAL_POSE_PURPOSES = ["PICKUP", "DESTINATION", "DOCK"]


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


class CoordinateZoneSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_map_labels = {}
        self.tables = {}
        self.load_thread = None
        self.load_worker = None
        self.goal_pose_save_thread = None
        self.goal_pose_save_worker = None
        self._worker_stop_wait_ms = 1500
        self.current_bundle = {}
        self.operation_zone_rows = []
        self.goal_pose_rows = []
        self.patrol_area_rows = []
        self.selected_edit_type = None
        self.selected_goal_pose = None
        self.selected_goal_pose_index = None
        self.goal_pose_dirty = False
        self._syncing_goal_pose_form = False
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
        self.map_canvas = MapCanvasWidget()
        self.map_canvas.setObjectName("coordinateZoneMapCanvas")
        self.map_canvas.clear_map("좌표 설정 맵 미수신")
        self.map_canvas.setMinimumHeight(280)
        self.map_canvas.map_clicked.connect(self.handle_map_click_for_goal_pose)

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
        self.edit_placeholder_label = QLabel(
            "목록 또는 맵 marker를 선택하면 구역, 목표 좌표, 순찰 waypoint "
            "편집 폼이 여기에 표시됩니다."
        )
        self.edit_placeholder_label.setObjectName("mutedText")
        self.edit_placeholder_label.setWordWrap(True)
        self.goal_pose_form = self._build_goal_pose_form()
        self.goal_pose_form.setHidden(True)

        self.edit_panel_layout.addWidget(title)
        self.edit_panel_layout.addWidget(self.edit_placeholder_label)
        self.edit_panel_layout.addWidget(self.goal_pose_form)
        self.edit_panel_layout.addStretch(1)
        return panel

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
        self.goal_pose_form.setHidden(False)
        self._set_goal_pose_form(goal_pose)
        self.goal_pose_dirty = False
        self._sync_goal_pose_save_state()

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

    def save_current_edit(self):
        if self.selected_edit_type == "goal_pose":
            self.save_selected_goal_pose()

    def discard_current_edit(self):
        if self.selected_edit_type == "goal_pose" and self.selected_goal_pose:
            self._set_goal_pose_form(self.selected_goal_pose)
            self.goal_pose_dirty = False
            self.validation_message_label.setText("목표 좌표 변경을 취소했습니다.")
            self._sync_goal_pose_save_state()

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
        self._stop_goal_pose_save_thread()

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


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
]
