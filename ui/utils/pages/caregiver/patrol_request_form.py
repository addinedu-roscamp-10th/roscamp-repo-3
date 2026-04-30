import logging

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.utils.pages.caregiver.task_request_builders import (
    PayloadValidationError,
    build_patrol_create_payload,
    build_patrol_preview,
    normalize_delivery_response,
)
from ui.utils.pages.caregiver.task_request_constants import (
    PRIORITY_CODE_TO_LABEL,
)
from ui.utils.config.network_config import CONTROL_SERVER_TIMEOUT
from ui.utils.pages.caregiver.task_request_workers import PatrolSubmitWorker
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.common import InlineStatusMixin
from ui.utils.widgets.form_controls import (
    configure_searchable_combo,
    create_priority_segment,
    make_field_group,
)


logger = logging.getLogger(__name__)


class PatrolRequestForm(QWidget, InlineStatusMixin):
    preview_changed = pyqtSignal(object)
    result_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.submit_thread = None
        self.submit_worker = None
        self._worker_stop_wait_ms = max(
            1000,
            int((CONTROL_SERVER_TIMEOUT * 2 + 0.5) * 1000),
        )
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
        self.init_inline_status()

        self.submit_btn = QPushButton("순찰 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self.submit_request)

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
        self.notes_field_group = make_field_group(
            "요청 메모",
            self.notes_input,
            object_name="notesFieldGroup",
            spacing=2,
        )
        self.form_grid.addWidget(
            self.notes_field_group,
            2,
            0,
            1,
            2,
        )

        root.addWidget(form_title)
        root.addLayout(self.form_grid)
        root.addWidget(self.status_label)
        root.addWidget(self.submit_btn)

        self.patrol_area_combo.currentIndexChanged.connect(
            self._handle_patrol_area_changed
        )
        self.notes_input.textChanged.connect(self.emit_preview_changed)
        self.set_priority("NORMAL")

    def set_patrol_areas(self, patrol_areas):
        self.patrol_area_combo.clear()
        areas = patrol_areas or []

        if not areas:
            self.patrol_area_combo.addItem("등록된 순찰 구역 없음")
            self.patrol_area_combo.setEnabled(False)
            self.submit_btn.setEnabled(False)
            self.emit_preview_changed()
            return

        self.patrol_area_combo.setEnabled(True)
        self.submit_btn.setEnabled(True)
        for area in areas:
            patrol_area_id = str(area.get("patrol_area_id") or "").strip()
            if not patrol_area_id:
                continue
            self.patrol_area_combo.addItem(
                self._build_patrol_area_display_name(area),
                area,
            )
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
        self.emit_preview_changed()

    def _build_create_patrol_task_payload(self, current_user):
        return build_patrol_create_payload(
            current_user=current_user,
            area=self._selected_area(),
            priority=self.get_priority_code(),
        )

    def submit_request(self):
        if self.submit_thread is not None:
            return

        current_user = SessionManager.current_user()
        try:
            payload = self._build_create_patrol_task_payload(current_user)
        except PayloadValidationError as exc:
            self.show_inline_status(str(exc), "warning")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("등록 중...")
        logger.debug("patrol submit started")

        self.submit_thread = QThread(self)
        self.submit_worker = PatrolSubmitWorker(payload)
        self.submit_worker.moveToThread(self.submit_thread)

        self.submit_thread.started.connect(self.submit_worker.run)
        self.submit_worker.finished.connect(self._handle_submit_finished)
        self.submit_worker.finished.connect(self.submit_thread.quit)
        self.submit_worker.finished.connect(self.submit_worker.deleteLater)
        self.submit_thread.finished.connect(self.submit_thread.deleteLater)
        self.submit_thread.finished.connect(self._clear_submit_thread)

        self.submit_thread.start()

    def _handle_submit_finished(self, success, response):
        logger.debug("patrol submit finished: success=%s", success)
        self.submit_btn.setText("순찰 요청 등록")
        self.submit_btn.setEnabled(self.patrol_area_combo.isEnabled())

        response_payload = normalize_delivery_response(success, response)
        response_payload.setdefault("cancellable", False)
        response_payload["cancellable"] = bool(response_payload.get("cancellable"))
        self.result_received.emit(response_payload)

        message = response_payload.get("result_message")
        if not message and success:
            message = "순찰 요청이 접수되었습니다."
        if not message:
            message = str(
                response_payload.get("reason_code") or "순찰 요청 처리에 실패했습니다."
            )

        if success:
            task_id = response_payload.get("task_id")
            if task_id is not None and "task_id" not in str(message):
                message = f"{message} (task_id={task_id})"
            self.show_inline_status(message, "success")
            self.notes_input.clear()
            return

        self.show_inline_status(message, "warning")

    def _clear_submit_thread(self):
        self.submit_thread = None
        self.submit_worker = None

    def _stop_submit_thread(self):
        if self.submit_thread is None:
            return
        if self.submit_thread.isRunning():
            self.submit_thread.quit()
            self.submit_thread.wait(self._worker_stop_wait_ms)
        self._clear_submit_thread()

    def closeEvent(self, event):
        self._stop_submit_thread()
        super().closeEvent(event)

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
        self.hide_inline_status()
        self.emit_preview_changed()


__all__ = ["PatrolRequestForm"]
