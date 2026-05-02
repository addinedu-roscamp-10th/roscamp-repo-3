import base64
import binascii

from PyQt6.QtCore import QObject, Qt, pyqtSignal
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


class CoordinateZoneSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_map_labels = {}
        self.tables = {}
        self.load_thread = None
        self.load_worker = None
        self._worker_stop_wait_ms = 1500
        self.current_bundle = {}
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
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Edit Panel")
        title.setObjectName("sectionTitle")
        body = QLabel(
            "목록 또는 맵 marker를 선택하면 구역, 목표 좌표, 순찰 waypoint "
            "편집 폼이 여기에 표시됩니다."
        )
        body.setObjectName("mutedText")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
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
        self.apply_active_map(bundle.get("map_profile") or {})
        self._set_table_rows(
            self.tables["operationZoneTable"],
            bundle.get("operation_zones") or [],
            [
                "zone_id",
                "zone_name",
                "zone_type",
                ("is_enabled", _enabled_text),
            ],
        )
        self._set_table_rows(
            self.tables["goalPoseTable"],
            bundle.get("goal_poses") or [],
            [
                "goal_pose_id",
                "purpose",
                ("zone_name", _zone_label),
                ("pose", _goal_pose_text),
            ],
        )
        self._set_table_rows(
            self.tables["patrolAreaTable"],
            bundle.get("patrol_areas") or [],
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

    def _handle_load_finished(self, ok, payload):
        if ok:
            self.apply_loaded_coordinate_config(payload)
        else:
            self.apply_load_error(payload)
        self.refresh_button.setEnabled(True)

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None

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


__all__ = ["CoordinateConfigLoadWorker", "CoordinateZoneSettingsPage"]
