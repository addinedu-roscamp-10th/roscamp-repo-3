import logging

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.utils.config.network_config import CONTROL_SERVER_TIMEOUT
from ui.utils.pages.caregiver.task_request_builders import (
    PayloadValidationError,
    build_delivery_create_payload,
    build_delivery_preview,
    build_patrol_create_payload,
    build_patrol_preview,
    normalize_delivery_response,
)
from ui.utils.pages.caregiver.task_request_workers import (
    DeliverySubmitWorker,
    TaskRequestOptionsLoadWorker,
)
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.common import InlineStatusMixin
from ui.utils.widgets.form_controls import (
    configure_searchable_combo,
    create_priority_segment,
    make_field_group,
)


logger = logging.getLogger(__name__)


class DeliveryRequestForm(QWidget, InlineStatusMixin):
    preview_changed = pyqtSignal(object)
    result_received = pyqtSignal(object)
    options_loaded = pyqtSignal(object)
    LOAD_STATE_IDLE = "idle"
    LOAD_STATE_LOADING = "loading"
    LOAD_STATE_LOADED = "loaded"
    LOAD_STATE_FAILED = "failed"

    PRIORITY_LABEL_TO_CODE = {
        "일반": "NORMAL",
        "긴급": "URGENT",
        "최우선": "HIGHEST",
    }
    PRIORITY_CODE_TO_LABEL = {
        code: label
        for label, code in PRIORITY_LABEL_TO_CODE.items()
    }

    def __init__(self):
        super().__init__()
        self._items_load_state = self.LOAD_STATE_IDLE
        self.load_thread = None
        self.load_worker = None
        self.submit_thread = None
        self.submit_worker = None
        self._worker_stop_wait_ms = max(
            1000,
            int((CONTROL_SERVER_TIMEOUT * 2 + 0.5) * 1000),
        )
        self._build_ui()

    @property
    def items_load_state(self):
        return self._items_load_state

    def _build_ui(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        form_title = QLabel("운반 작업 설정")
        form_title.setObjectName("sectionTitle")
        form_title.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.form_grid = QGridLayout()
        self.form_grid.setObjectName("deliveryFormGrid")
        self.form_grid.setHorizontalSpacing(18)
        self.form_grid.setVerticalSpacing(6)
        self.form_grid.setColumnStretch(0, 1)
        self.form_grid.setColumnStretch(1, 1)

        self.item_combo = QComboBox()
        configure_searchable_combo(self.item_combo, "물품명 또는 item_id 검색")
        self.item_combo.setMinimumHeight(44)

        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(999)
        self.quantity_input.setValue(1)
        self.quantity_input.setMinimumHeight(44)

        self.destination_combo = QComboBox()
        configure_searchable_combo(self.destination_combo, "목적지 검색")
        self.destination_combo.addItem("목적지 목록 불러오는 중...")
        self.destination_combo.setEnabled(False)
        self.destination_combo.setMinimumHeight(44)

        self.priority_combo = QComboBox(self)
        self.priority_combo.addItems(["일반", "긴급", "최우선"])
        self.priority_combo.hide()

        (
            self.priority_segment,
            self.priority_group,
            self.priority_buttons,
        ) = create_priority_segment(
            self.PRIORITY_CODE_TO_LABEL,
            on_selected=self.set_priority,
            parent=self,
        )

        self.detail_input = QTextEdit()
        self.detail_input.setObjectName("deliveryNotesInput")
        self.detail_input.setPlaceholderText("배송 시 주의사항이나 수령인 정보를 입력하세요.")
        self.detail_input.setFixedHeight(84)
        self.init_inline_status()

        self.submit_btn = QPushButton("물품 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit_request)

        self.form_grid.addWidget(make_field_group("운반 물품", self.item_combo), 0, 0)
        self.form_grid.addWidget(make_field_group("수량", self.quantity_input), 0, 1)
        self.form_grid.addWidget(
            make_field_group("목적지", self.destination_combo),
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
            "추가 메모",
            self.detail_input,
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

        self.item_combo.currentIndexChanged.connect(self.emit_preview_changed)
        self.quantity_input.valueChanged.connect(self.emit_preview_changed)
        self.destination_combo.currentIndexChanged.connect(self.emit_preview_changed)
        self.priority_combo.currentTextChanged.connect(
            self._handle_priority_combo_changed
        )
        self.detail_input.textChanged.connect(self.emit_preview_changed)
        self.set_priority("NORMAL")

    def _handle_priority_combo_changed(self, label):
        self.set_priority(
            self.PRIORITY_LABEL_TO_CODE.get(label, "NORMAL"),
            sync_combo=False,
        )

    def set_priority(self, priority_code, sync_combo=True):
        normalized = str(priority_code or "NORMAL").upper()
        if normalized not in self.priority_buttons:
            normalized = "NORMAL"

        self._priority_code = normalized
        self.priority_buttons[normalized].setChecked(True)

        if sync_combo:
            label = self.PRIORITY_CODE_TO_LABEL[normalized]
            if self.priority_combo.currentText() != label:
                was_blocked = self.priority_combo.blockSignals(True)
                self.priority_combo.setCurrentText(label)
                self.priority_combo.blockSignals(was_blocked)

        self.emit_preview_changed()

    def get_priority_code(self):
        return getattr(self, "_priority_code", "NORMAL")

    def ensure_items_loaded(self):
        if self.load_thread is not None:
            return

        if self._items_load_state == self.LOAD_STATE_LOADED:
            return

        self._items_load_state = self.LOAD_STATE_LOADING
        self._load_items()

    def _load_items(self):
        if self.load_thread is not None:
            return

        logger.debug("delivery items load started")
        self.item_combo.clear()
        self.item_combo.addItem("물품 목록 불러오는 중...")
        self.item_combo.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("불러오는 중...")

        self.load_thread = QThread(self)
        self.load_worker = TaskRequestOptionsLoadWorker()
        self.load_worker.moveToThread(self.load_thread)

        self.load_thread.started.connect(self.load_worker.run)
        self.load_worker.finished.connect(self._handle_items_loaded)
        self.load_worker.finished.connect(self.load_thread.quit)
        self.load_worker.finished.connect(self.load_worker.deleteLater)
        self.load_thread.finished.connect(self.load_thread.deleteLater)
        self.load_thread.finished.connect(self._clear_load_thread)

        self.load_thread.start()

    def _handle_items_loaded(self, ok, payload):
        logger.debug("delivery items load finished: ok=%s", ok)
        self.item_combo.clear()
        self.destination_combo.clear()

        if not ok:
            self._items_load_state = self.LOAD_STATE_FAILED
            self.item_combo.addItem("물품 목록 불러오기 실패")
            self.destination_combo.addItem("목적지 목록 불러오기 실패")
            self.destination_combo.setEnabled(False)
            self.show_inline_status(f"물품 목록을 불러오지 못했습니다. {payload}", "error")
            self.submit_btn.setText("물품 요청 등록")
            return

        options = payload if isinstance(payload, dict) else {"items": payload}
        items = options.get("items") or []
        destinations = options.get("destinations") or []
        self._items_load_state = self.LOAD_STATE_LOADED

        if not items or not destinations:
            self.item_combo.addItem("등록된 물품 없음")
            if not destinations:
                self.destination_combo.addItem("등록된 목적지 없음")
            self.item_combo.setEnabled(False)
            self.destination_combo.setEnabled(False)
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("물품 요청 등록")
            self.options_loaded.emit(options)
            return

        self.item_combo.setEnabled(True)
        self.destination_combo.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("물품 요청 등록")
        for item in items:
            item_name = str(item.get("item_name", "")).strip()
            if not item_name:
                continue

            display_name = self._build_item_display_name(item)
            self.item_combo.addItem(display_name, item)
        for destination in destinations:
            destination_id = str(destination.get("destination_id") or "").strip()
            if not destination_id:
                continue
            display_name = str(
                destination.get("display_name")
                or destination.get("destination_name")
                or destination_id
            ).strip()
            self.destination_combo.addItem(display_name, destination_id)
        self.options_loaded.emit(options)
        self.emit_preview_changed()

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None

    def refresh_data(self):
        self._items_load_state = self.LOAD_STATE_IDLE
        self.ensure_items_loaded()

    def submit_request(self):
        if self.submit_thread is not None:
            return

        current_user = SessionManager.current_user()

        if current_user is None:
            self.show_inline_status("로그인 사용자 정보가 없습니다.", "warning")
            return

        payload = self._build_create_delivery_task_payload(current_user)
        if payload is None:
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("등록 중...")
        logger.debug("delivery submit started")

        self.submit_thread = QThread(self)
        self.submit_worker = DeliverySubmitWorker(payload)
        self.submit_worker.moveToThread(self.submit_thread)

        self.submit_thread.started.connect(self.submit_worker.run)
        self.submit_worker.finished.connect(self._handle_submit_finished)
        self.submit_worker.finished.connect(self.submit_thread.quit)
        self.submit_worker.finished.connect(self.submit_worker.deleteLater)
        self.submit_thread.finished.connect(self.submit_thread.deleteLater)
        self.submit_thread.finished.connect(self._clear_submit_thread)

        self.submit_thread.start()

    def _handle_submit_finished(self, success, response):
        logger.debug("delivery submit finished: success=%s", success)
        self.submit_btn.setText("물품 요청 등록")
        self.submit_btn.setEnabled(self.item_combo.isEnabled())

        response_payload = self._normalize_delivery_response(success, response)
        self.result_received.emit(response_payload)

        message = response_payload.get("result_message")
        if not message and success:
            message = "물품 요청이 접수되었습니다."
        if not message:
            message = str(
                response_payload.get("reason_code") or "물품 요청 처리에 실패했습니다."
            )

        if success:
            task_id = response_payload.get("task_id")
            if task_id is not None and "task_id" not in str(message):
                message = f"{message} (task_id={task_id})"
            self.show_inline_status(message, "success")
            self.quantity_input.setValue(1)
            self.detail_input.clear()
            self.refresh_data()
            return

        self.show_inline_status(message, "warning")

    def _clear_submit_thread(self):
        self.submit_thread = None
        self.submit_worker = None

    def _stop_thread(self, thread):
        if thread is None:
            return True
        if thread.isRunning():
            thread.quit()
            return bool(thread.wait(self._worker_stop_wait_ms))
        return True

    def _stop_worker_threads(self):
        if self._stop_thread(self.load_thread):
            self._clear_load_thread()
        if self._stop_thread(self.submit_thread):
            self._clear_submit_thread()

    def closeEvent(self, event):
        self._stop_worker_threads()
        super().closeEvent(event)

    def _build_create_delivery_task_payload(self, current_user):
        try:
            return build_delivery_create_payload(
                current_user=current_user,
                item=self.item_combo.currentData(),
                quantity=self.quantity_input.value(),
                destination_id=self.destination_combo.currentData(),
                priority=self.get_priority_code(),
                notes=self.detail_input.toPlainText(),
            )
        except PayloadValidationError as exc:
            self.show_inline_status(str(exc), "warning")
            return None

    @staticmethod
    def _build_item_display_name(item):
        item_name = str(item.get("item_name", "")).strip()
        item_id = str(item.get("item_id") or "").strip()
        quantity = item.get("quantity")
        parts = [item_name]
        if item_id:
            parts.append(f"item_id {item_id}")

        if quantity is None:
            return " / ".join(parts)

        parts.append(f"재고 {quantity}")
        return " / ".join(parts)

    def emit_preview_changed(self, *_args):
        self.preview_changed.emit(self._build_preview_payload())

    def _build_preview_payload(self):
        return build_delivery_preview(
            current_user=SessionManager.current_user(),
            item=self.item_combo.currentData(),
            quantity=self.quantity_input.value(),
            destination_id=self.destination_combo.currentData(),
            priority=self.get_priority_code(),
        )

    @staticmethod
    def _normalize_delivery_response(success, response):
        return normalize_delivery_response(success, response)

    def reset_form(self):
        self.quantity_input.setValue(1)
        self.destination_combo.setCurrentIndex(0)
        self.set_priority("NORMAL")
        self.detail_input.clear()
        if self.item_combo.count() > 0:
            self.item_combo.setCurrentIndex(0)
        self.hide_inline_status()
        self.emit_preview_changed()


class NotReadyScenarioForm(QWidget):
    def __init__(self, scenario_name: str, field_labels: list[str], note: str):
        super().__init__()
        self.submit_btn = None
        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel(f"{scenario_name} 요청 구조")
        title.setObjectName("sectionTitle")
        description = QLabel(note)
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.not_ready_label = QLabel(
            f"{scenario_name} 요청은 현재 서버 workflow 연동 전입니다. "
            "현재 제출 가능한 시나리오는 물품 운반입니다."
        )
        self.not_ready_label.setObjectName("noticeText")
        self.not_ready_label.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(self.not_ready_label)

        for label in field_labels:
            value = QLabel("준비 중")
            value.setObjectName("mutedText")
            root.addWidget(QLabel(label))
            root.addWidget(value)

        root.addStretch()

        self.submit_btn = QPushButton(f"{scenario_name} 요청 준비 중")
        self.submit_btn.setObjectName("secondaryButton")
        self.submit_btn.setEnabled(False)
        root.addWidget(self.submit_btn)

    def reset_form(self):
        return


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

        (
            self.priority_segment,
            self.priority_group,
            self.priority_buttons,
        ) = create_priority_segment(
            DeliveryRequestForm.PRIORITY_CODE_TO_LABEL,
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
        root.addWidget(self.submit_btn)

        self.patrol_area_combo.currentIndexChanged.connect(self.emit_preview_changed)
        self.notes_input.textChanged.connect(self.emit_preview_changed)
        self.set_priority("NORMAL")

    def set_patrol_areas(self, patrol_areas):
        self.patrol_area_combo.clear()
        areas = patrol_areas or []

        if not areas:
            self.patrol_area_combo.addItem("등록된 순찰 구역 없음")
            self.patrol_area_combo.setEnabled(False)
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


class GuideRequestForm(NotReadyScenarioForm):
    def __init__(self):
        super().__init__(
            "안내",
            ["member_id", "visitor_id", "start_location_id", "destination_id"],
            "방문자 키오스크와 안내 workflow가 연결되면 이 입력 구조를 실제 폼으로 전환합니다.",
        )


class FollowRequestForm(NotReadyScenarioForm):
    def __init__(self):
        super().__init__(
            "추종",
            ["target_caregiver_id", "follow_mode", "start_location_id", "priority"],
            "추종 시나리오의 phase 1 포함 여부가 확정되면 실제 요청 API와 연결합니다.",
        )


__all__ = [
    "DeliveryRequestForm",
    "FollowRequestForm",
    "GuideRequestForm",
    "NotReadyScenarioForm",
    "PatrolRequestForm",
]
