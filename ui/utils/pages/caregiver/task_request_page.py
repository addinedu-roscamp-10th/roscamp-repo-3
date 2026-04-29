from uuid import uuid4

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QApplication, QPushButton, QComboBox, QTextEdit, QScrollArea, QSpinBox,
    QButtonGroup, QCompleter, QSizePolicy
)
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from ui.utils.network.service_clients import DeliveryRequestRemoteService
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.common import InlineStatusMixin


class DeliveryItemsLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            items = service.get_delivery_items()
            self.finished.emit(True, items)
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

    DESTINATION_OPTIONS = (
        ("301호", "delivery_room_301"),
    )
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
        self._configure_searchable_combo(self.item_combo, "물품명 또는 item_id 검색")
        self.item_combo.setMinimumHeight(44)

        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(999)
        self.quantity_input.setValue(1)
        self.quantity_input.setMinimumHeight(44)

        self.destination_combo = QComboBox()
        self._configure_searchable_combo(self.destination_combo, "목적지 검색")
        for label, destination_id in self.DESTINATION_OPTIONS:
            self.destination_combo.addItem(label, destination_id)
        self.destination_combo.setMinimumHeight(44)

        self.priority_combo = QComboBox(self)
        self.priority_combo.addItems(["일반", "긴급", "최우선"])
        self.priority_combo.hide()

        self.priority_group = QButtonGroup(self)
        self.priority_group.setExclusive(True)
        self.priority_buttons = {}
        self.priority_segment = QFrame()
        self.priority_segment.setObjectName("prioritySegment")
        priority_layout = QHBoxLayout(self.priority_segment)
        priority_layout.setContentsMargins(4, 4, 4, 4)
        priority_layout.setSpacing(6)

        for code in ["NORMAL", "URGENT", "HIGHEST"]:
            button = QPushButton(self.PRIORITY_CODE_TO_LABEL[code])
            button.setObjectName("prioritySegmentButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, priority=code: self.set_priority(priority)
            )
            self.priority_buttons[code] = button
            self.priority_group.addButton(button)
            priority_layout.addWidget(button)

        self.detail_input = QTextEdit()
        self.detail_input.setObjectName("deliveryNotesInput")
        self.detail_input.setPlaceholderText("배송 시 주의사항이나 수령인 정보를 입력하세요.")
        self.detail_input.setFixedHeight(84)
        self.init_inline_status()

        self.submit_btn = QPushButton("물품 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit_request)

        self.form_grid.addWidget(self._field_group("운반 물품", self.item_combo), 0, 0)
        self.form_grid.addWidget(self._field_group("수량", self.quantity_input), 0, 1)
        self.form_grid.addWidget(
            self._field_group("목적지", self.destination_combo),
            1,
            0,
            1,
            2,
        )
        self.form_grid.addWidget(
            self._field_group("우선순위", self.priority_segment),
            2,
            0,
            1,
            2,
        )
        self.notes_field_group = self._field_group(
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

    @staticmethod
    def _configure_searchable_combo(combo, placeholder):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.lineEdit().setPlaceholderText(placeholder)

        completer = QCompleter(combo.model(), combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer)

    @staticmethod
    def _field_group(label_text, widget, object_name="formFieldGroup", spacing=6):
        group = QFrame()
        group.setObjectName(object_name)
        group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(label)
        layout.addWidget(widget)
        return group

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

        if not ok:
            self.item_combo.addItem("물품 목록 불러오기 실패")
            self.show_inline_status(f"물품 목록을 불러오지 못했습니다. {payload}", "error")
            self.submit_btn.setText("물품 요청 등록")
            return

        items = payload

        if not items:
            self.item_combo.addItem("등록된 물품 없음")
            self.item_combo.setEnabled(False)
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("물품 요청 등록")
            return

        self.item_combo.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("물품 요청 등록")
        for item in items:
            item_name = str(item.get("item_name", "")).strip()
            if not item_name:
                continue

            display_name = self._build_item_display_name(item)
            self.item_combo.addItem(display_name, item)
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

    def _build_create_delivery_task_payload(self, current_user):
        item = self.item_combo.currentData()
        if not isinstance(item, dict):
            self.show_inline_status("유효한 물품을 선택하세요.", "warning")
            return None

        item_id = str(item.get("item_id") or "").strip()
        if not item_id or not item_id.isdecimal():
            self.show_inline_status("물품 식별자를 확인할 수 없습니다.", "warning")
            return None

        caregiver_id = str(current_user.user_id or "").strip()
        if not caregiver_id or not caregiver_id.isdecimal():
            self.show_inline_status("caregiver_id를 확인할 수 없습니다.", "warning")
            return None

        destination_id = str(self.destination_combo.currentData() or "").strip()
        if not destination_id:
            self.show_inline_status("목적지를 선택하세요.", "warning")
            return None

        request_id = f"req_{uuid4().hex}"
        return {
            "request_id": request_id,
            "caregiver_id": int(caregiver_id),
            "item_id": int(item_id),
            "quantity": self.quantity_input.value(),
            "destination_id": destination_id,
            "priority": self.get_priority_code(),
            "notes": self.detail_input.toPlainText().strip() or None,
            "idempotency_key": f"idem_{uuid4().hex}",
        }

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
        current_user = SessionManager.current_user()
        item = self.item_combo.currentData()
        destination_id = str(self.destination_combo.currentData() or "-")
        priority = self.get_priority_code()

        if isinstance(item, dict):
            item_id = str(item.get("item_id") or "-")
            item_name = str(item.get("item_name") or "-")
        else:
            item_id = "-"
            item_name = "-"

        return {
            "caregiver_id": str(current_user.user_id) if current_user else "-",
            "item_id": item_id,
            "item_name": item_name,
            "quantity": self.quantity_input.value(),
            "destination_id": destination_id,
            "priority": priority,
        }

    @staticmethod
    def _normalize_delivery_response(success, response):
        if isinstance(response, dict):
            payload = dict(response)
        else:
            payload = {
                "result_code": "ACCEPTED" if success else "REJECTED",
                "result_message": str(response or ""),
            }

        payload.setdefault("result_code", "ACCEPTED" if success else "REJECTED")
        payload.setdefault("result_message", None)
        payload.setdefault("reason_code", None)
        payload.setdefault("task_id", None)
        payload.setdefault("task_status", None)
        payload.setdefault("assigned_robot_id", None)
        return payload

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


class PatrolRequestForm(NotReadyScenarioForm):
    def __init__(self):
        super().__init__(
            "순찰",
            ["patrol_area_id", "patrol_area_name", "priority", "notes"],
            "pinky3 순찰 workflow가 서버와 연결되면 이 입력 구조를 실제 폼으로 전환합니다.",
        )


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


class TaskRequestSidePanel(QWidget):
    PRIORITY_CODE_TO_LABEL = {
        "NORMAL": "일반",
        "URGENT": "긴급",
        "HIGHEST": "최우선",
    }

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self.preview_card = QFrame()
        self.preview_card.setObjectName("requestPreviewCard")
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(22, 22, 22, 22)
        preview_layout.setSpacing(10)

        preview_title = QLabel("요청 미리보기")
        preview_title.setObjectName("sectionTitle")

        caregiver_row, self.preview_caregiver_id = self._metric_row("요청자")
        item_row, self.preview_item = self._metric_row("물품")
        quantity_row, self.preview_quantity = self._metric_row("수량", "1개")
        destination_row, self.preview_destination = self._metric_row("목적지")
        priority_row, self.preview_priority = self._metric_row(
            "우선순위",
            "일반",
            "priorityChip",
        )

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(caregiver_row)
        preview_layout.addWidget(item_row)
        preview_layout.addWidget(quantity_row)
        preview_layout.addWidget(destination_row)
        preview_layout.addWidget(priority_row)

        self.robot_status_card = QFrame()
        self.robot_status_card.setObjectName("robotStatusCard")
        robot_layout = QVBoxLayout(self.robot_status_card)
        robot_layout.setContentsMargins(22, 22, 22, 22)
        robot_layout.setSpacing(10)

        robot_title = QLabel("실시간 로봇 상태")
        robot_title.setObjectName("sectionTitle")

        robot_id_row, self.robot_id_label = self._metric_row("로봇", "pinky2")
        robot_state_row, self.robot_state_label = self._metric_row(
            "상태",
            "feedback 수신 전",
            "robotStateChip",
        )
        robot_pose_row, self.robot_pose_label = self._metric_row("위치", "미수신")
        robot_destination_row, self.robot_destination_label = self._metric_row("목적지")

        self.robot_map_placeholder = QFrame()
        self.robot_map_placeholder.setObjectName("robotMapPlaceholder")
        map_layout = QVBoxLayout(self.robot_map_placeholder)
        map_layout.setContentsMargins(16, 16, 16, 16)
        map_label = QLabel("지도 / 위치 placeholder")
        map_label.setObjectName("mutedText")
        map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(map_label)

        robot_layout.addWidget(robot_title)
        robot_layout.addWidget(robot_id_row)
        robot_layout.addWidget(robot_state_row)
        robot_layout.addWidget(robot_pose_row)
        robot_layout.addWidget(robot_destination_row)
        robot_layout.addWidget(self.robot_map_placeholder)

        self.result_card = QFrame()
        self.result_card.setObjectName("resultPanel")
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setContentsMargins(22, 22, 22, 22)
        result_layout.setSpacing(10)

        result_title = QLabel("최근 요청 결과")
        result_title.setObjectName("sectionTitle")

        self.result_message_label = QLabel("아직 요청 결과가 없습니다.")
        self.result_message_label.setObjectName("resultMessage")
        self.result_message_label.setWordWrap(True)

        result_code_row, self.result_code_label = self._metric_row("결과")
        reason_row, self.reason_code_label = self._metric_row("사유")
        task_id_row, self.task_id_label = self._metric_row("task_id")
        task_status_row, self.task_status_label = self._metric_row("상태")
        assigned_robot_row, self.assigned_robot_id_label = self._metric_row("배정 로봇")

        result_layout.addWidget(result_title)
        result_layout.addWidget(self.result_message_label)
        result_layout.addWidget(result_code_row)
        result_layout.addWidget(reason_row)
        result_layout.addWidget(task_id_row)
        result_layout.addWidget(task_status_row)
        result_layout.addWidget(assigned_robot_row)

        notice_card = QFrame()
        notice_card.setObjectName("noticeCard")
        notice_layout = QVBoxLayout(notice_card)
        notice_layout.setContentsMargins(20, 18, 20, 18)
        notice_layout.setSpacing(8)

        notice_title = QLabel("주의사항")
        notice_title.setObjectName("noticeTitle")
        notice_text = QLabel(
            "로봇 경로에 장애물이 없는지 확인하세요. 중량이 큰 물품이나 "
            "응급 상황은 운영 절차에 따라 별도 처리해야 합니다."
        )
        notice_text.setObjectName("noticeText")
        notice_text.setWordWrap(True)

        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(notice_text)

        root.addWidget(self.preview_card)
        root.addWidget(self.robot_status_card)
        root.addWidget(self.result_card)
        root.addWidget(notice_card)
        root.addStretch()

    @staticmethod
    def _metric_row(label_text, value_text="-", value_object_name="sideMetricValue"):
        row = QFrame()
        row.setObjectName("sideMetricRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(10)

        label = QLabel(label_text)
        label.setObjectName("sideMetricLabel")
        value = QLabel(value_text)
        value.setObjectName(value_object_name)
        value.setWordWrap(True)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row_layout.addWidget(label)
        row_layout.addStretch(1)
        row_layout.addWidget(value)
        return row, value

    def update_preview(self, preview):
        preview = preview or {}
        item_id = self._display(preview.get("item_id"))
        item_name = self._display(preview.get("item_name"))
        item_text = "-"
        if item_id != "-" or item_name != "-":
            item_text = f"{item_name} (item_id: {item_id})"

        self.preview_caregiver_id.setText(self._display(preview.get("caregiver_id")))
        self.preview_item.setText(item_text)
        self.preview_quantity.setText(f"{self._display(preview.get('quantity'))}개")
        destination_id = self._display(preview.get("destination_id"))
        self.preview_destination.setText(destination_id)
        self.preview_priority.setText(
            self._priority_label(preview.get("priority"))
        )
        self.robot_destination_label.setText(destination_id)

    def show_delivery_result(self, response):
        response = response or {}
        self.result_code_label.setText(self._display(response.get("result_code")))
        self.result_message_label.setText(
            self._display(response.get("result_message"))
        )
        self.reason_code_label.setText(self._display(response.get("reason_code")))
        self.task_id_label.setText(self._display(response.get("task_id")))
        self.task_status_label.setText(self._display(response.get("task_status")))
        self.assigned_robot_id_label.setText(
            self._display(response.get("assigned_robot_id"))
        )
        assigned_robot_id = response.get("assigned_robot_id") or "pinky2"
        self.robot_id_label.setText(self._display(assigned_robot_id))

    def _priority_label(self, priority_code):
        return self.PRIORITY_CODE_TO_LABEL.get(
            self._display(priority_code),
            self._display(priority_code),
        )

    @staticmethod
    def _display(value):
        if value is None or value == "":
            return "-"
        return str(value)


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
        self.patrol_btn = QPushButton("순찰 (준비 중)")
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
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)
        print("[task_request] switched to delivery page")

    def show_patrol_page(self):
        self._show_form(self.patrol_form)
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
