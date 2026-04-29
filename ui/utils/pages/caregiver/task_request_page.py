import logging

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.utils.pages.caregiver.task_request_forms import (
    DeliveryRequestForm,
    FollowRequestForm,
    GuideRequestForm,
    NotReadyScenarioForm,
    PatrolRequestForm,
)
from ui.utils.pages.caregiver.task_request_side_panel import TaskRequestSidePanel
from ui.utils.pages.caregiver.task_request_workers import DeliveryCancelWorker
from ui.utils.widgets.admin_shell import PageHeader


logger = logging.getLogger(__name__)


class TaskRequestPage(QWidget):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current_form = None
        self.cancel_thread = None
        self.cancel_worker = None
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
        self.side_panel.cancel_task_btn.clicked.connect(self._request_delivery_cancel)

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
        self.cancel_task_btn = self.side_panel.cancel_task_btn
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
        logger.debug("initialize task request forms")
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
        logger.debug("switched to delivery page")

    def show_patrol_page(self):
        self._show_form(self.patrol_form)
        self.patrol_form.emit_preview_changed()
        logger.debug("switched to patrol page")

    def show_guide_page(self):
        self._show_form(self.guide_form)
        logger.debug("switched to guide page")

    def show_follow_page(self):
        self._show_form(self.follow_form)
        logger.debug("switched to follow page")

    def _request_delivery_cancel(self):
        task_id = self.cancel_task_btn.property("task_id")
        if task_id is None or str(task_id).strip() in {"", "-"}:
            return

        if not self._confirm_cancel_task(task_id):
            return

        self.cancel_task_btn.setEnabled(False)
        self.cancel_task_btn.setText("취소 요청 전송 중...")
        self._start_cancel_delivery_task(task_id)

    def _confirm_cancel_task(self, task_id):
        result = QMessageBox.question(
            self,
            "작업 취소 확인",
            (
                "이 작업을 취소하시겠습니까?\n\n"
                f"task_id: {task_id}\n"
                f"상태: {self.task_status_label.text()}\n"
                f"배정 로봇: {self.assigned_robot_id_label.text()}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _start_cancel_delivery_task(self, task_id):
        if self.cancel_thread is not None:
            return

        self.cancel_thread = QThread(self)
        self.cancel_worker = DeliveryCancelWorker(task_id=task_id)
        self.cancel_worker.moveToThread(self.cancel_thread)

        self.cancel_thread.started.connect(self.cancel_worker.run)
        self.cancel_worker.finished.connect(self._handle_cancel_finished)
        self.cancel_worker.finished.connect(self.cancel_thread.quit)
        self.cancel_worker.finished.connect(self.cancel_worker.deleteLater)
        self.cancel_thread.finished.connect(self.cancel_thread.deleteLater)
        self.cancel_thread.finished.connect(self._clear_cancel_thread)

        self.cancel_thread.start()

    def _handle_cancel_finished(self, success, response):
        response = response or {}
        if not isinstance(response, dict):
            response = {
                "result_code": "CLIENT_ERROR",
                "result_message": str(response),
                "reason_code": "CLIENT_RESPONSE_INVALID",
                "cancel_requested": False,
            }
        elif not success and not response.get("result_code"):
            response = {
                **response,
                "result_code": "CLIENT_ERROR",
                "reason_code": response.get("reason_code") or "CLIENT_ERROR",
            }

        self.side_panel.show_delivery_result(response)

    def _clear_cancel_thread(self):
        self.cancel_thread = None
        self.cancel_worker = None

    def _stop_cancel_thread(self):
        if self.cancel_thread is None:
            return
        if self.cancel_thread.isRunning():
            self.cancel_thread.quit()
            self.cancel_thread.wait(1000)
        self._clear_cancel_thread()

    def reset_page(self):
        for form in self.forms:
            if hasattr(form, "reset_form"):
                form.reset_form()

        self.form_scroll.verticalScrollBar().setValue(0)
        self._show_form(self.delivery_form)
        QTimer.singleShot(0, self.delivery_form.ensure_items_loaded)

    def closeEvent(self, event):
        self._stop_cancel_thread()
        super().closeEvent(event)


__all__ = [
    "DeliveryRequestForm",
    "FollowRequestForm",
    "GuideRequestForm",
    "NotReadyScenarioForm",
    "PatrolRequestForm",
    "TaskRequestPage",
]
