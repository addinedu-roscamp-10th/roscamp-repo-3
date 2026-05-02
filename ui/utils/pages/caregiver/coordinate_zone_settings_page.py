from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

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


class CoordinateZoneSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_map_labels = {}
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


__all__ = ["CoordinateZoneSettingsPage"]
