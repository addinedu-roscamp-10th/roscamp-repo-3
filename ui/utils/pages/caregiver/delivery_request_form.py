import logging

from PyQt6.QtCore import Qt, pyqtSignal
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
from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.pages.caregiver.task_request_builders import (
    PayloadValidationError,
    build_delivery_create_payload,
    build_delivery_preview,
    normalize_delivery_response,
)
from ui.utils.pages.caregiver.task_request_constants import (
    PRIORITY_CODE_TO_LABEL as TASK_PRIORITY_CODE_TO_LABEL,
    PRIORITY_LABEL_TO_CODE as TASK_PRIORITY_LABEL_TO_CODE,
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

    PRIORITY_LABEL_TO_CODE = TASK_PRIORITY_LABEL_TO_CODE
    PRIORITY_CODE_TO_LABEL = TASK_PRIORITY_CODE_TO_LABEL

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
        configure_searchable_combo(self.item_combo, "물품명 검색")
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

        self.load_thread, self.load_worker = start_worker_thread(
            self,
            worker=TaskRequestOptionsLoadWorker(),
            finished_handler=self._handle_items_loaded,
            clear_handler=self._clear_load_thread,
        )

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

        self.submit_thread, self.submit_worker = start_worker_thread(
            self,
            worker=DeliverySubmitWorker(payload),
            finished_handler=self._handle_submit_finished,
            clear_handler=self._clear_submit_thread,
        )

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
        quantity = item.get("quantity")
        if quantity is None:
            return item_name

        return f"{item_name} / 재고 {quantity}개"

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


__all__ = ["DeliveryRequestForm"]
