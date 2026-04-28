from uuid import uuid4

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QApplication, QPushButton, QComboBox, QLineEdit, QTextEdit, QScrollArea,
    QListWidget, QListWidgetItem, QSpinBox
)
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from ui.utils.network.service_clients import DeliveryRequestRemoteService
from ui.utils.session.session_manager import SessionManager
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
    finished = pyqtSignal(bool, str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        service = DeliveryRequestRemoteService()

        try:
            response = service.create_delivery_task(**self.payload)
            result_code = str(response.get("result_code", ""))

            if result_code == "ACCEPTED":
                task_id = response.get("task_id")
                message = response.get("result_message") or "물품 요청이 접수되었습니다."
                if task_id:
                    message = f"{message} (task_id={task_id})"
                self.finished.emit(True, message)
                return

            message = response.get("result_message") or str(
                response.get("reason_code", "물품 요청 처리에 실패했습니다.")
            )
            self.finished.emit(False, message)
        except Exception as exc:
            self.finished.emit(False, f"물품 요청 처리 중 오류가 발생했습니다.\n{exc}")


class DeliveryRequestForm(QWidget, InlineStatusMixin):
    DESTINATION_OPTIONS = (
        ("301호", "delivery_room_301"),
    )
    PRIORITY_LABEL_TO_CODE = {
        "일반": "NORMAL",
        "긴급": "URGENT",
        "최우선": "HIGHEST",
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
        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.item_combo = QComboBox()
        self.item_combo.setMinimumHeight(44)

        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(999)
        self.quantity_input.setValue(1)
        self.quantity_input.setMinimumHeight(44)

        self.destination_combo = QComboBox()
        for label, destination_id in self.DESTINATION_OPTIONS:
            self.destination_combo.addItem(label, destination_id)
        self.destination_combo.setMinimumHeight(44)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["일반", "긴급", "최우선"])
        self.priority_combo.setMinimumHeight(44)

        self.detail_input = QTextEdit()
        self.detail_input.setPlaceholderText("요청 상세 내용을 입력하세요.")
        self.detail_input.setMinimumHeight(120)
        self.init_inline_status()

        self.submit_btn = QPushButton("물품 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit_request)

        root.addWidget(QLabel("물품 종류"))
        root.addWidget(self.item_combo)

        root.addWidget(QLabel("수량"))
        root.addWidget(self.quantity_input)

        root.addWidget(QLabel("목적지"))
        root.addWidget(self.destination_combo)

        root.addWidget(QLabel("우선순위"))
        root.addWidget(self.priority_combo)

        root.addWidget(QLabel("설명"))
        root.addWidget(self.detail_input)
        root.addWidget(self.status_label)

        root.addWidget(self.submit_btn)

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

    def _handle_submit_finished(self, success, message):
        print(f"[task_request] delivery submit finished: success={success}")
        self.submit_btn.setText("물품 요청 등록")
        self.submit_btn.setEnabled(self.item_combo.isEnabled())

        if success:
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
        if not item_id:
            self.show_inline_status("물품 식별자를 확인할 수 없습니다.", "warning")
            return None

        destination_id = str(self.destination_combo.currentData() or "").strip()
        if not destination_id:
            self.show_inline_status("목적지를 선택하세요.", "warning")
            return None

        request_id = f"req_{uuid4().hex}"
        return {
            "request_id": request_id,
            "caregiver_id": current_user.user_id,
            "item_id": item_id,
            "quantity": self.quantity_input.value(),
            "destination_id": destination_id,
            "priority": self.PRIORITY_LABEL_TO_CODE.get(
                self.priority_combo.currentText(),
                "NORMAL",
            ),
            "notes": self.detail_input.toPlainText().strip() or None,
            "idempotency_key": f"idem_{uuid4().hex}",
        }

    @staticmethod
    def _build_item_display_name(item):
        item_name = str(item.get("item_name", "")).strip()
        quantity = item.get("quantity")

        if quantity is None:
            return item_name

        return f"{item_name} (재고 {quantity})"

    def reset_form(self):
        self.quantity_input.setValue(1)
        self.destination_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.detail_input.clear()
        if self.item_combo.count() > 0:
            self.item_combo.setCurrentIndex(0)
        self.hide_inline_status()

class FollowRequestForm(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        self.submit_btn = None
        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.target_combo = QComboBox()
        self.target_combo.addItems(["어르신 추종", "보호사 추종", "방문객 안내 추종"])
        self.target_combo.setMinimumHeight(44)

        self.robot_combo = QComboBox()
        self.robot_combo.addItems(["자동 선택", "Pinky-01", "Pinky-02", "Pinky-03"])
        self.robot_combo.setMinimumHeight(44)

        self.detail_input = QTextEdit()
        self.detail_input.setPlaceholderText("추종 시작 위치, 대상, 특이사항을 입력하세요.")
        self.detail_input.setMinimumHeight(120)
        self.init_inline_status()

        self.submit_btn = QPushButton("추종 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit_request)

        root.addWidget(QLabel("추종 유형"))
        root.addWidget(self.target_combo)
        root.addWidget(QLabel("배정 로봇"))
        root.addWidget(self.robot_combo)
        root.addWidget(QLabel("설명"))
        root.addWidget(self.detail_input)
        root.addWidget(self.status_label)
        root.addWidget(self.submit_btn)

    def submit_request(self):
        self.show_inline_status("추종 요청이 접수되었습니다.", "success")

    def reset_form(self):
        self.target_combo.setCurrentIndex(0)
        self.robot_combo.setCurrentIndex(0)
        self.detail_input.clear()
        self.hide_inline_status()


class PatrolRequestForm(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        self.submit_btn = None
        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.zone_combo = QComboBox()
        self.zone_combo.addItems([
            "3층 복도",
            "간호 스테이션 주변",
            "면회실 구역",
            "엘리베이터 앞",
            "야간 순찰 구역",
        ])
        self.zone_combo.setMinimumHeight(44)

        self.robot_combo = QComboBox()
        self.robot_combo.addItems(["자동 선택", "Pinky-01", "Pinky-02", "Pinky-03"])
        self.robot_combo.setMinimumHeight(44)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["일반", "긴급", "최우선"])
        self.priority_combo.setMinimumHeight(44)

        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems([
            "즉시 시작",
            "오전 순찰",
            "점심 전 순찰",
            "오후 순찰",
            "야간 순찰",
        ])
        self.schedule_combo.setMinimumHeight(44)

        self.detail_input = QTextEdit()
        self.detail_input.setPlaceholderText("순찰 메모를 입력하세요.")
        self.detail_input.setMinimumHeight(120)
        self.init_inline_status()

        self.submit_btn = QPushButton("순찰 요청 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit_request)

        root.addWidget(QLabel("순찰 구역"))
        root.addWidget(self.zone_combo)
        root.addWidget(QLabel("배정 로봇"))
        root.addWidget(self.robot_combo)
        root.addWidget(QLabel("우선순위"))
        root.addWidget(self.priority_combo)
        root.addWidget(QLabel("순찰 일정"))
        root.addWidget(self.schedule_combo)
        root.addWidget(QLabel("설명"))
        root.addWidget(self.detail_input)
        root.addWidget(self.status_label)
        root.addWidget(self.submit_btn)

    def submit_request(self):
        zone = self.zone_combo.currentText()
        robot = self.robot_combo.currentText()
        priority = self.priority_combo.currentText()
        schedule = self.schedule_combo.currentText()

        self.show_inline_status(
            f"{zone} 순찰 요청이 접수되었습니다. 일정: {schedule}, 로봇: {robot}, 우선순위: {priority}",
            "success",
        )

    def reset_form(self):
        self.zone_combo.setCurrentIndex(0)
        self.robot_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.schedule_combo.setCurrentIndex(0)
        self.detail_input.clear()
        self.hide_inline_status()


class SchedulerCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("formCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("로봇 스케쥴러")
        title.setObjectName("sectionTitle")

        subtitle = QLabel("현재 예약된 작업 예시")
        subtitle.setObjectName("mutedText")

        schedule_list = QListWidget()
        items = [
            "09:00  Pinky-01  3층 복도 순찰",
            "10:30  Pinky-02  약품 키트 305호 전달",
            "13:00  Pinky-03  방문객 안내 추종",
            "15:30  Pinky-01  면회실 주변 순찰",
        ]
        for item in items:
            QListWidgetItem(item, schedule_list)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(schedule_list)


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

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("작업 요청")
        title.setObjectName("pageTitle")
        subtitle = QLabel("작업 종류를 선택하여 해당 요청을 등록하세요.")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        chip = QLabel("Task Request")
        chip.setObjectName("chipBlue")

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(chip)

        top_tabs = QHBoxLayout()
        top_tabs.setSpacing(12)

        self.delivery_btn = QPushButton("물품 요청")
        self.follow_btn = QPushButton("추종")
        self.patrol_btn = QPushButton("순찰")

        for btn in [self.delivery_btn, self.follow_btn, self.patrol_btn]:
            btn.setObjectName("secondaryButton")
            top_tabs.addWidget(btn)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        left_card = QFrame()
        left_card.setObjectName("formCard")
        lc = QVBoxLayout(left_card)
        lc.setContentsMargins(24, 24, 24, 24)
        lc.setSpacing(16)

        self.form_host = QFrame()
        self.form_host.setObjectName("formHost")
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(0)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.form_scroll.setWidget(self.form_host)
        lc.addWidget(self.form_scroll, 1)

        right_card = SchedulerCard()

        self.delivery_btn.clicked.connect(self.show_delivery_page)
        self.follow_btn.clicked.connect(self.show_follow_page)
        self.patrol_btn.clicked.connect(self.show_patrol_page)

        content_row.addWidget(left_card, 2)
        content_row.addWidget(right_card, 1)

        root.addLayout(header)
        root.addLayout(top_tabs)
        root.addLayout(content_row, 1)

    def _initialize_forms(self):
        print("[task_request] initialize forms")
        self.delivery_form = DeliveryRequestForm()
        self.follow_form = FollowRequestForm()
        self.patrol_form = PatrolRequestForm()
        self.forms = [self.delivery_form, self.follow_form, self.patrol_form]

        for form in self.forms:
            form.hide()
            self.form_layout.addWidget(form)

        self._show_form(self.delivery_form)
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)

    def _show_form(self, form):
        if self.current_form is form:
            return

        focused_widget = QApplication.focusWidget()
        if focused_widget is not None:
            focused_widget.clearFocus()

        for page in self.forms:
            page.hide()

        form.show()
        self.current_form = form

    def show_delivery_page(self):
        self._show_form(self.delivery_form)
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)
        print("[task_request] switched to delivery page")

    def show_follow_page(self):
        self._show_form(self.follow_form)
        print("[task_request] switched to follow page")

    def show_patrol_page(self):
        self._show_form(self.patrol_form)
        print("[task_request] switched to patrol page")

    def reset_page(self):
        for form in self.forms:
            if hasattr(form, "reset_form"):
                form.reset_form()

        self.form_scroll.verticalScrollBar().setValue(0)
        self._show_form(self.delivery_form)
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)
