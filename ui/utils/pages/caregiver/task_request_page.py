from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QApplication, QPushButton, QComboBox, QTextEdit, QScrollArea, QSpinBox,
    QSizePolicy
)
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from ui.utils.config.network_config import CONTROL_SERVER_TIMEOUT
from ui.utils.network.service_clients import DeliveryRequestRemoteService
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.common import InlineStatusMixin
from ui.utils.widgets.form_controls import (
    configure_searchable_combo,
    create_priority_segment,
    make_field_group,
)
from ui.utils.pages.caregiver.task_request_builders import (
    PayloadValidationError,
    build_delivery_create_payload,
    build_delivery_preview,
    build_patrol_create_payload,
    build_patrol_preview,
    normalize_delivery_response,
)
from ui.utils.pages.caregiver.task_request_side_panel import TaskRequestSidePanel


class DeliveryItemsLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            self.finished.emit(
                True,
                {
                    "items": service.get_delivery_items(),
                    "destinations": service.get_delivery_destinations(),
                    "patrol_areas": service.get_patrol_areas(),
                },
            )
        except Exception as exc:
            self.finished.emit(False, str(exc))


class DeliverySubmitWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.create_delivery_task(**self.payload) or {}
            result_code = str(response.get("result_code", "")).upper()
            self.finished.emit(result_code == "ACCEPTED", response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"물품 요청 처리 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": None,
                    "task_status": None,
                    "assigned_robot_id": None,
                },
            )


class DeliveryRequestForm(QWidget, InlineStatusMixin):
    preview_changed = pyqtSignal(object)
    result_received = pyqtSignal(object)
    options_loaded = pyqtSignal(object)

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
        self._items_loaded = False
        self.load_thread = None
        self.load_worker = None
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
        if not self._items_loaded and self.load_thread is None:
            self._items_loaded = True
            self._load_items()

    def _load_items(self):
        if self.load_thread is not None:
            return

        print("[task_request] delivery items load started")
        self.item_combo.clear()
        self.item_combo.addItem("물품 목록 불러오는 중...")
        self.item_combo.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("불러오는 중...")

        self.load_thread = QThread(self)
        self.load_worker = DeliveryItemsLoadWorker()
        self.load_worker.moveToThread(self.load_thread)

        self.load_thread.started.connect(self.load_worker.run)
        self.load_worker.finished.connect(self._handle_items_loaded)
        self.load_worker.finished.connect(self.load_thread.quit)
        self.load_worker.finished.connect(self.load_worker.deleteLater)
        self.load_thread.finished.connect(self.load_thread.deleteLater)
        self.load_thread.finished.connect(self._clear_load_thread)

        self.load_thread.start()

    def _handle_items_loaded(self, ok, payload):
        print(f"[task_request] delivery items load finished: ok={ok}")
        self.item_combo.clear()
        self.destination_combo.clear()

        if not ok:
            self._items_loaded = False
            self.item_combo.addItem("물품 목록 불러오기 실패")
            self.destination_combo.addItem("목적지 목록 불러오기 실패")
            self.destination_combo.setEnabled(False)
            self.show_inline_status(f"물품 목록을 불러오지 못했습니다. {payload}", "error")
            self.submit_btn.setText("물품 요청 등록")
            return

        options = payload if isinstance(payload, dict) else {"items": payload}
        items = options.get("items") or []
        destinations = options.get("destinations") or []

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
        self._items_loaded = False
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
        print("[task_request] delivery submit started")

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
        print(f"[task_request] delivery submit finished: success={success}")
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


class TaskRequestPage(QWidget):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current_form = None
        self._build_ui()
        self._initialize_forms()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        top_tabs = QHBoxLayout()
        top_tabs.setSpacing(12)

        self.delivery_btn = QPushButton("물품 운반")
        self.patrol_btn = QPushButton("순찰")
        self.guide_btn = QPushButton("안내 (준비 중)")
        self.follow_btn = QPushButton("추종 (준비 중)")

        for btn in [
            self.delivery_btn,
            self.patrol_btn,
            self.guide_btn,
            self.follow_btn,
        ]:
            btn.setObjectName("scenarioTabButton")
            btn.setCheckable(True)
            top_tabs.addWidget(btn)

        self.content_row = QHBoxLayout()
        self.content_row.setSpacing(18)

        self.left_card = QFrame()
        self.left_card.setObjectName("formCard")
        self.left_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        lc = QVBoxLayout(self.left_card)
        lc.setContentsMargins(24, 24, 24, 24)
        lc.setSpacing(16)

        self.form_host = QFrame()
        self.form_host.setObjectName("formHost")
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(0)
        self.form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.form_scroll.setWidget(self.form_host)
        lc.addWidget(self.form_scroll)

        self.side_panel = TaskRequestSidePanel()
        self.side_scroll = QScrollArea()
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.side_scroll.setWidget(self.side_panel)

        self.delivery_btn.clicked.connect(self.show_delivery_page)
        self.patrol_btn.clicked.connect(self.show_patrol_page)
        self.guide_btn.clicked.connect(self.show_guide_page)
        self.follow_btn.clicked.connect(self.show_follow_page)

        self.content_row.addWidget(
            self.left_card,
            2,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        self.content_row.addWidget(self.side_scroll, 1)

        self.preview_card = self.side_panel.preview_card
        self.result_card = self.side_panel.result_card
        self.preview_caregiver_id = self.side_panel.preview_caregiver_id
        self.preview_item = self.side_panel.preview_item
        self.preview_quantity = self.side_panel.preview_quantity
        self.preview_destination = self.side_panel.preview_destination
        self.preview_priority = self.side_panel.preview_priority
        self.result_code_label = self.side_panel.result_code_label
        self.result_message_label = self.side_panel.result_message_label
        self.reason_code_label = self.side_panel.reason_code_label
        self.task_id_label = self.side_panel.task_id_label
        self.task_status_label = self.side_panel.task_status_label
        self.assigned_robot_id_label = self.side_panel.assigned_robot_id_label
        self.robot_status_card = self.side_panel.robot_status_card
        self.robot_map_placeholder = self.side_panel.robot_map_placeholder
        self.robot_id_label = self.side_panel.robot_id_label
        self.robot_state_label = self.side_panel.robot_state_label
        self.robot_pose_label = self.side_panel.robot_pose_label
        self.robot_destination_label = self.side_panel.robot_destination_label
        self.robot_map_label = self.side_panel.robot_map_label

        root.addWidget(
            PageHeader("작업 요청", "작업 종류를 선택하여 해당 요청을 등록하세요.")
        )
        root.addLayout(top_tabs)
        root.addLayout(self.content_row, 1)

    def _initialize_forms(self):
        print("[task_request] initialize forms")
        self.delivery_form = DeliveryRequestForm()
        self.patrol_form = PatrolRequestForm()
        self.guide_form = GuideRequestForm()
        self.follow_form = FollowRequestForm()
        self.forms = [
            self.delivery_form,
            self.patrol_form,
            self.guide_form,
            self.follow_form,
        ]

        self.delivery_form.preview_changed.connect(self.side_panel.update_preview)
        self.delivery_form.result_received.connect(self.side_panel.show_delivery_result)
        self.delivery_form.options_loaded.connect(self._handle_request_options_loaded)
        self.patrol_form.preview_changed.connect(self.side_panel.update_preview)

        for form in self.forms:
            form.hide()
            form.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            self.form_layout.addWidget(form)

        self._show_form(self.delivery_form)
        self.delivery_form.emit_preview_changed()
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)

    def _show_form(self, form):
        if self.current_form is form:
            self._resize_form_container(form)
            self._set_active_tab(form)
            return

        focused_widget = QApplication.focusWidget()
        if focused_widget is not None:
            focused_widget.clearFocus()

        for page in self.forms:
            page.hide()

        form.show()
        self.current_form = form
        self._resize_form_container(form)
        self._set_active_tab(form)

    def _handle_request_options_loaded(self, options):
        if not isinstance(options, dict):
            return
        self.patrol_form.set_patrol_areas(options.get("patrol_areas") or [])

    def _resize_form_container(self, form):
        form.adjustSize()
        form_height = form.sizeHint().height()
        self.form_scroll.setFixedHeight(form_height)
        self.form_host.setFixedHeight(form_height)
        self.left_card.updateGeometry()

    def _set_active_tab(self, form):
        form_to_button = {
            self.delivery_form: self.delivery_btn,
            self.patrol_form: self.patrol_btn,
            self.guide_form: self.guide_btn,
            self.follow_form: self.follow_btn,
        }
        for target_form, button in form_to_button.items():
            button.setChecked(target_form is form)

    def show_delivery_page(self):
        self._show_form(self.delivery_form)
        self.side_panel.set_delivery_context()
        self.delivery_form.emit_preview_changed()
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)
        print("[task_request] switched to delivery page")

    def show_patrol_page(self):
        self._show_form(self.patrol_form)
        self.patrol_form.emit_preview_changed()
        print("[task_request] switched to patrol page")

    def show_guide_page(self):
        self._show_form(self.guide_form)
        print("[task_request] switched to guide page")

    def show_follow_page(self):
        self._show_form(self.follow_form)
        print("[task_request] switched to follow page")

    def reset_page(self):
        for form in self.forms:
            if hasattr(form, "reset_form"):
                form.reset_form()

        self.form_scroll.verticalScrollBar().setValue(0)
        self._show_form(self.delivery_form)
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)
