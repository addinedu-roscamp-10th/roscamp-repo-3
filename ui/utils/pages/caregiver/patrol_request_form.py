from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.utils.pages.caregiver.task_request_builders import (
    build_patrol_create_payload,
    build_patrol_preview,
)
from ui.utils.pages.caregiver.task_request_constants import (
    PRIORITY_CODE_TO_LABEL,
)
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.form_controls import (
    configure_searchable_combo,
    create_priority_segment,
    make_field_group,
)


class PatrolRequestForm(QWidget):
    preview_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        form_title = QLabel("순찰 작업 설정")
        form_title.setObjectName("sectionTitle")
        form_title.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.form_grid = QGridLayout()
        self.form_grid.setObjectName("patrolFormGrid")
        self.form_grid.setHorizontalSpacing(18)
        self.form_grid.setVerticalSpacing(6)
        self.form_grid.setColumnStretch(0, 1)
        self.form_grid.setColumnStretch(1, 1)

        self.patrol_area_combo = QComboBox()
        self.patrol_area_combo.setObjectName("patrolAreaCombo")
        configure_searchable_combo(
            self.patrol_area_combo,
            "순찰 구역명 또는 patrol_area_id 검색",
        )
        self.patrol_area_combo.addItem("순찰 구역 목록 불러오는 중...")
        self.patrol_area_combo.setEnabled(False)
        self.patrol_area_combo.setMinimumHeight(44)

        self.route_summary_card = self._build_route_summary_card()

        (
            self.priority_segment,
            self.priority_group,
            self.priority_buttons,
        ) = create_priority_segment(
            PRIORITY_CODE_TO_LABEL,
            on_selected=self.set_priority,
            parent=self,
        )

        self.notes_input = QTextEdit()
        self.notes_input.setObjectName("patrolNotesInput")
        self.notes_input.setPlaceholderText(
            "순찰 요청 메모를 입력하세요. PAT-001 payload에는 포함하지 않습니다."
        )
        self.notes_input.setFixedHeight(84)

        self.submit_btn = QPushButton("순찰 요청 연동 준비 중")
        self.submit_btn.setObjectName("secondaryButton")
        self.submit_btn.setEnabled(False)

        self.form_grid.addWidget(
            make_field_group("순찰 구역", self.patrol_area_combo),
            0,
            0,
            1,
            2,
        )
        self.form_grid.addWidget(
            make_field_group("우선순위", self.priority_segment),
            1,
            0,
            1,
            2,
        )
        self.form_grid.addWidget(
            self.route_summary_card,
            2,
            0,
            1,
            2,
        )
        self.notes_field_group = make_field_group(
            "요청 메모",
            self.notes_input,
            object_name="notesFieldGroup",
            spacing=2,
        )
        self.form_grid.addWidget(
            self.notes_field_group,
            3,
            0,
            1,
            2,
        )

        root.addWidget(form_title)
        root.addLayout(self.form_grid)
        root.addWidget(self.submit_btn)

        self.patrol_area_combo.currentIndexChanged.connect(
            self._handle_patrol_area_changed
        )
        self.notes_input.textChanged.connect(self.emit_preview_changed)
        self._sync_selected_area_summary()
        self.set_priority("NORMAL")

    def _build_route_summary_card(self):
        card = QFrame()
        card.setObjectName("patrolRouteSummaryCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(8)

        self.assigned_robot_label = self._add_summary_row(
            layout,
            0,
            "배정 후보",
            "미정",
        )
        self.map_id_label = self._add_summary_row(
            layout,
            0,
            "지도",
            "-",
            column=2,
        )
        self.waypoint_count_label = self._add_summary_row(
            layout,
            1,
            "waypoint",
            "0개",
        )
        self.path_frame_id_label = self._add_summary_row(
            layout,
            1,
            "frame",
            "-",
            column=2,
        )
        return card

    @staticmethod
    def _add_summary_row(layout, row, label_text, value_text, *, column=0):
        label = QLabel(label_text)
        label.setObjectName("patrolSummaryLabel")
        value = QLabel(value_text)
        value.setObjectName("patrolSummaryValue")
        layout.addWidget(label, row, column)
        layout.addWidget(value, row, column + 1)
        return value

    def set_patrol_areas(self, patrol_areas):
        self.patrol_area_combo.clear()
        areas = patrol_areas or []

        if not areas:
            self.patrol_area_combo.addItem("등록된 순찰 구역 없음")
            self.patrol_area_combo.setEnabled(False)
            self._sync_selected_area_summary()
            self.emit_preview_changed()
            return

        self.patrol_area_combo.setEnabled(True)
        for area in areas:
            patrol_area_id = str(area.get("patrol_area_id") or "").strip()
            if not patrol_area_id:
                continue
            self.patrol_area_combo.addItem(
                self._build_patrol_area_display_name(area),
                area,
            )
        self._sync_selected_area_summary()
        self.emit_preview_changed()

    @staticmethod
    def _build_patrol_area_display_name(area):
        name = str(
            area.get("patrol_area_name")
            or area.get("patrol_area_id")
            or ""
        ).strip()
        revision = area.get("patrol_area_revision")
        active = "활성" if area.get("active", True) else "비활성"
        if revision is None:
            return f"{name} ({active})"
        return f"{name} (rev {revision}, {active})"

    def set_priority(self, priority_code):
        normalized = str(priority_code or "NORMAL").upper()
        if normalized not in self.priority_buttons:
            normalized = "NORMAL"

        self._priority_code = normalized
        self.priority_buttons[normalized].setChecked(True)
        self.emit_preview_changed()

    def get_priority_code(self):
        return getattr(self, "_priority_code", "NORMAL")

    def _selected_area(self):
        area = self.patrol_area_combo.currentData()
        return area if isinstance(area, dict) else {}

    def _handle_patrol_area_changed(self):
        self._sync_selected_area_summary()
        self.emit_preview_changed()

    def _sync_selected_area_summary(self):
        area = self._selected_area()
        self.assigned_robot_label.setText(
            self._display_unassigned_robot(area.get("assigned_robot_id"))
        )
        self.map_id_label.setText(self._display_value(area.get("map_id")))
        self.waypoint_count_label.setText(
            f"{self._display_waypoint_count(area.get('waypoint_count'))}개"
        )
        self.path_frame_id_label.setText(
            self._display_value(area.get("path_frame_id"))
        )

    @staticmethod
    def _display_value(value, *, empty="-"):
        if value is None or str(value).strip() == "":
            return empty
        return str(value)

    @classmethod
    def _display_unassigned_robot(cls, value):
        return cls._display_value(value, empty="미정")

    @staticmethod
    def _display_waypoint_count(value):
        if value in (None, ""):
            return "0"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"

    def _build_create_patrol_task_payload(self, current_user):
        return build_patrol_create_payload(
            current_user=current_user,
            area=self._selected_area(),
            priority=self.get_priority_code(),
        )

    def emit_preview_changed(self):
        self.preview_changed.emit(self._build_preview_payload())

    def _build_preview_payload(self):
        return build_patrol_preview(
            SessionManager.current_user(),
            self._selected_area(),
            self.get_priority_code(),
        )

    def reset_form(self):
        self.patrol_area_combo.setCurrentIndex(0)
        self.set_priority("NORMAL")
        self.notes_input.clear()
        self.emit_preview_changed()


__all__ = ["PatrolRequestForm"]
