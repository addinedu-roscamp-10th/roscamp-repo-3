import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.utils.config.network_config import CONTROL_SERVER_TIMEOUT
from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.pages.caregiver.task_request_builders import (
    PayloadValidationError,
    build_drive_create_payload,
    build_drive_preview,
    normalize_delivery_response,
)
from ui.utils.pages.caregiver.task_request_workers import DriveSubmitWorker
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.common import InlineStatusMixin
from ui.utils.widgets.form_controls import (
    configure_searchable_combo,
    create_priority_segment,
    make_field_group,
)


logger = logging.getLogger(__name__)

DRIVE_ROBOT_IDS = ("pinky1", "pinky3")
DRIVE_PRIORITY_CODE_TO_LABEL = {
    "NORMAL": "일반",
    "HIGH": "높음",
    "URGENT": "긴급",
}


class DriveRequestForm(QWidget, InlineStatusMixin):
    preview_changed = pyqtSignal(object)
    result_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.submit_thread = None
        self.submit_worker = None
        self._robot_id = DRIVE_ROBOT_IDS[0]
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

        form_title = QLabel("주행 작업 설정")
        form_title.setObjectName("sectionTitle")
        form_title.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.form_grid = QGridLayout()
        self.form_grid.setObjectName("driveFormGrid")
        self.form_grid.setHorizontalSpacing(18)
        self.form_grid.setVerticalSpacing(6)
        self.form_grid.setColumnStretch(0, 1)
        self.form_grid.setColumnStretch(1, 1)

        self.route_combo = QComboBox()
        self.route_combo.setObjectName("driveRouteCombo")
        configure_searchable_combo(
            self.route_combo,
            "FMS 경로명 또는 route_id 검색",
        )
        self.route_combo.addItem("주행 경로 목록 불러오는 중...")
        self.route_combo.setEnabled(False)
        self.route_combo.setMinimumHeight(44)

        self.robot_segment = QFrame()
        self.robot_segment.setObjectName("driveRobotSegment")
        robot_layout = QHBoxLayout(self.robot_segment)
        robot_layout.setContentsMargins(4, 4, 4, 4)
        robot_layout.setSpacing(6)
        self.robot_group = QButtonGroup(self)
        self.robot_group.setExclusive(True)
        self.robot_buttons = {}
        for robot_id in DRIVE_ROBOT_IDS:
            button = QPushButton(robot_id)
            button.setObjectName("driveRobotButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, target_robot_id=robot_id: self.set_robot_id(
                    target_robot_id
                )
            )
            self.robot_buttons[robot_id] = button
            self.robot_group.addButton(button)
            robot_layout.addWidget(button)

        (
            self.priority_segment,
            self.priority_group,
            self.priority_buttons,
        ) = create_priority_segment(
            DRIVE_PRIORITY_CODE_TO_LABEL,
            on_selected=self.set_priority,
            parent=self,
        )

        self.notes_input = QTextEdit()
        self.notes_input.setObjectName("driveNotesInput")
        self.notes_input.setPlaceholderText("주행 테스트 메모를 입력하세요.")
        self.notes_input.setFixedHeight(84)
        self.init_inline_status()

        self.submit_btn = QPushButton("주행 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self.submit_request)

        self.form_grid.addWidget(
            make_field_group("주행 경로", self.route_combo),
            0,
            0,
            1,
            2,
        )
        self.form_grid.addWidget(
            make_field_group("로봇", self.robot_segment),
            1,
            0,
            1,
            2,
        )
        self.form_grid.addWidget(
            make_field_group("우선순위", self.priority_segment),
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
        root.addWidget(self.status_label)
        root.addWidget(self.submit_btn)

        self.route_combo.currentIndexChanged.connect(self.emit_preview_changed)
        self.notes_input.textChanged.connect(self.emit_preview_changed)
        self.set_robot_id(self._robot_id)
        self.set_priority("NORMAL")

    def set_drive_routes(self, routes):
        self.route_combo.clear()
        enabled_routes = [
            route
            for route in routes or []
            if isinstance(route, dict) and route.get("is_enabled", True)
        ]

        if not enabled_routes:
            self.route_combo.addItem("등록된 주행 경로 없음")
            self.route_combo.setEnabled(False)
            self.submit_btn.setEnabled(False)
            self.emit_preview_changed()
            return

        self.route_combo.setEnabled(True)
        self.submit_btn.setEnabled(True)
        for route in enabled_routes:
            route_id = str(route.get("route_id") or "").strip()
            if not route_id:
                continue
            self.route_combo.addItem(self._build_route_display_name(route), route)
        self.emit_preview_changed()

    @staticmethod
    def _build_route_display_name(route):
        name = str(route.get("route_name") or route.get("route_id") or "").strip()
        revision = route.get("revision")
        waypoint_count = route.get("waypoint_count")
        if waypoint_count is None:
            waypoint_count = len(route.get("waypoint_sequence") or [])
        if revision is None:
            return f"{name} ({waypoint_count}점)"
        return f"{name} (rev {revision}, {waypoint_count}점)"

    def set_robot_id(self, robot_id):
        normalized = str(robot_id or DRIVE_ROBOT_IDS[0]).strip()
        if normalized not in self.robot_buttons:
            normalized = DRIVE_ROBOT_IDS[0]

        self._robot_id = normalized
        self.robot_buttons[normalized].setChecked(True)
        self.emit_preview_changed()

    def get_robot_id(self):
        return self._robot_id

    def set_priority(self, priority_code):
        normalized = str(priority_code or "NORMAL").upper()
        if normalized not in self.priority_buttons:
            normalized = "NORMAL"

        self._priority_code = normalized
        self.priority_buttons[normalized].setChecked(True)
        self.emit_preview_changed()

    def get_priority_code(self):
        return getattr(self, "_priority_code", "NORMAL")

    def _selected_route(self):
        route = self.route_combo.currentData()
        return route if isinstance(route, dict) else {}

    def _build_create_drive_task_payload(self, current_user):
        return build_drive_create_payload(
            current_user=current_user,
            route=self._selected_route(),
            robot_id=self.get_robot_id(),
            priority=self.get_priority_code(),
            notes=self.notes_input.toPlainText(),
        )

    def submit_request(self):
        if self.submit_thread is not None:
            return

        current_user = SessionManager.current_user()
        try:
            payload = self._build_create_drive_task_payload(current_user)
        except PayloadValidationError as exc:
            self.show_inline_status(str(exc), "warning")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("등록 중...")
        logger.debug("drive submit started")

        self.submit_thread, self.submit_worker = start_worker_thread(
            self,
            worker=DriveSubmitWorker(payload),
            finished_handler=self._handle_submit_finished,
            clear_handler=self._clear_submit_thread,
        )

    def _handle_submit_finished(self, success, response):
        logger.debug("drive submit finished: success=%s", success)
        self.submit_btn.setText("주행 요청 등록")
        self.submit_btn.setEnabled(self.route_combo.isEnabled())

        response_payload = normalize_delivery_response(success, response)
        response_payload.setdefault("cancellable", False)
        response_payload["cancellable"] = bool(response_payload.get("cancellable"))
        self.result_received.emit(response_payload)

        message = response_payload.get("result_message")
        if not message and success:
            message = "주행 요청이 접수되었습니다."
        if not message:
            message = str(
                response_payload.get("reason_code") or "주행 요청 처리에 실패했습니다."
            )

        if success:
            task_id = response_payload.get("task_id")
            if task_id is not None and "작업 번호" not in str(message):
                message = f"{message} (작업 번호: {task_id})"
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
        return build_drive_preview(
            SessionManager.current_user(),
            self._selected_route(),
            self.get_robot_id(),
            self.get_priority_code(),
        )

    def reset_form(self):
        self.route_combo.setCurrentIndex(0)
        self.set_robot_id(DRIVE_ROBOT_IDS[0])
        self.set_priority("NORMAL")
        self.notes_input.clear()
        self.hide_inline_status()
        self.emit_preview_changed()


__all__ = ["DriveRequestForm"]
