import base64
import binascii
import logging

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.utils.pages.caregiver.task_monitor_detail_panels import (
    PatrolRuntimePanel,
    TaskResultInfoPanel,
    _display,
    _format_pose,
    _metric_row,
)
from ui.utils.pages.caregiver.task_event_stream_worker import TaskEventStreamWorker
from ui.utils.pages.caregiver.task_request_workers import PatrolResumeWorker
from ui.utils.core.responses import normalize_ui_response
from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.network.service_clients import TaskMonitorRemoteService
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard


logger = logging.getLogger(__name__)

WAITING_FALL_RESPONSE_PHASES = {
    "WAIT_FALL_RESPONSE",
    "WAITING_FALL_RESPONSE",
}
CANCELLABLE_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}
CANCEL_IN_PROGRESS_STATUSES = {
    "CANCEL_REQUESTED",
    "CANCELLING",
    "PREEMPTING",
}
TERMINAL_TASK_STATUSES = {
    "CANCELLED",
    "COMPLETED",
    "FAILED",
}


def _task_key(value):
    text = str(value or "").strip()
    if text in {"", "-"}:
        return None
    return text


class PatrolResumeDialog(QDialog):
    def __init__(self, *, task_id, parent=None):
        super().__init__(parent)
        self.task_id = str(task_id or "").strip()
        self.setWindowTitle("순찰 재개")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("patrolResumeFormPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(10)

        title = QLabel("현장 조치 후 순찰 재개")
        title.setObjectName("sectionTitle")

        task_row, _task_label, self.task_id_label = _metric_row(
            "task_id",
            _display(self.task_id),
        )

        member_label = QLabel("조치 대상 member_id")
        member_label.setObjectName("fieldLabel")
        self.member_id_input = QLineEdit()
        self.member_id_input.setObjectName("patrolResumeMemberIdInput")
        self.member_id_input.setPlaceholderText("member_id")
        self.member_id_input.setMinimumHeight(42)

        memo_label = QLabel("조치 내용")
        memo_label.setObjectName("fieldLabel")
        self.action_memo_input = QTextEdit()
        self.action_memo_input.setObjectName("patrolResumeActionMemoInput")
        self.action_memo_input.setPlaceholderText("현장 조치 내용을 입력하세요.")
        self.action_memo_input.setFixedHeight(92)

        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedText")
        self.error_label.setWordWrap(True)
        self.error_label.setHidden(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.cancel_btn = QPushButton("닫기")
        self.cancel_btn.setObjectName("secondaryButton")
        self.submit_btn = QPushButton("순찰 재개")
        self.submit_btn.setObjectName("patrolResumeButton")
        self.submit_btn.setEnabled(False)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.submit_btn)

        panel_layout.addWidget(title)
        panel_layout.addWidget(task_row)
        panel_layout.addWidget(member_label)
        panel_layout.addWidget(self.member_id_input)
        panel_layout.addWidget(memo_label)
        panel_layout.addWidget(self.action_memo_input)
        panel_layout.addWidget(self.error_label)
        panel_layout.addLayout(button_row)

        root.addWidget(panel)

        self.member_id_input.textChanged.connect(self._sync_submit_button)
        self.action_memo_input.textChanged.connect(self._sync_submit_button)
        self.cancel_btn.clicked.connect(self.reject)
        self.submit_btn.clicked.connect(self.accept)

    def _sync_submit_button(self):
        member_id = self.member_id_input.text().strip()
        action_memo = self.action_memo_input.toPlainText().strip()
        self.submit_btn.setEnabled(bool(self.task_id) and member_id.isdigit() and bool(action_memo))

    def build_payload(self, *, caregiver_id):
        member_id = self.member_id_input.text().strip()
        action_memo = self.action_memo_input.toPlainText().strip()

        if not self.task_id:
            raise ValueError("재개할 순찰 task_id가 없습니다.")
        if not str(caregiver_id or "").strip():
            raise ValueError("caregiver_id가 없습니다.")
        if not member_id.isdigit():
            raise ValueError("member_id를 숫자로 입력하세요.")
        if not action_memo:
            raise ValueError("현장 조치 메모를 입력하세요.")

        return {
            "task_id": self.task_id,
            "caregiver_id": int(caregiver_id),
            "member_id": int(member_id),
            "action_memo": action_memo,
        }

    def show_error(self, message):
        self.error_label.setText(str(message))
        self.error_label.setHidden(False)


class FallEvidenceImageDialog(QDialog):
    def __init__(self, *, response, parent=None):
        super().__init__(parent)
        self.response = response if isinstance(response, dict) else {}
        self.setObjectName("fallEvidenceImageDialog")
        self.setWindowTitle("낙상 증거사진")
        self.setModal(False)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("patrolResumeFormPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(10)

        title = QLabel("낙상 증거사진")
        title.setObjectName("sectionTitle")

        evidence_row, _label, evidence_label = _metric_row(
            "evidence_image_id",
            _display(self.response.get("evidence_image_id")),
            "fallEvidenceImageIdLabel",
        )
        frame_row, _frame_label, _frame_value = _metric_row(
            "frame_id",
            _display(self.response.get("frame_id")),
        )
        size_text = self._format_image_size()
        size_row, _size_label, _size_value = _metric_row("크기", size_text)

        self.image_label = QLabel()
        self.image_label.setObjectName("fallEvidenceImagePreview")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(420, 280)

        pixmap = self._build_pixmap()
        if pixmap is None:
            self.image_label.setText("이미지를 표시할 수 없습니다.")
        else:
            self.image_label.setPixmap(
                pixmap.scaled(
                    720,
                    520,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        detection_text = self._format_detections()
        self.detection_label = QLabel(detection_text)
        self.detection_label.setObjectName("mutedText")
        self.detection_label.setWordWrap(True)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)

        panel_layout.addWidget(title)
        panel_layout.addWidget(evidence_row)
        panel_layout.addWidget(frame_row)
        panel_layout.addWidget(size_row)
        panel_layout.addWidget(self.image_label)
        panel_layout.addWidget(self.detection_label)
        panel_layout.addLayout(close_row)
        root.addWidget(panel)

        # Keep a direct reference for tests and for later UI updates.
        self.evidence_image_id_label = evidence_label

    def _format_image_size(self):
        width = self.response.get("image_width_px")
        height = self.response.get("image_height_px")
        if width in (None, "") or height in (None, ""):
            return "-"
        return f"{width} x {height}px"

    def _build_pixmap(self):
        image_data = (
            self.response.get("annotated_image_data")
            or self.response.get("image_data")
        )
        if not image_data:
            return None
        try:
            raw = base64.b64decode(str(image_data), validate=False)
        except (binascii.Error, ValueError):
            return None

        pixmap = QPixmap()
        if not pixmap.loadFromData(raw):
            return None

        self._draw_detections(pixmap)
        return pixmap

    def _draw_detections(self, pixmap):
        detections = self.response.get("detections")
        if not isinstance(detections, list):
            return

        painter = QPainter(pixmap)
        try:
            pen = QPen(QColor("#f97316"))
            pen.setWidth(4)
            painter.setPen(pen)
            for detection in detections:
                if not isinstance(detection, dict):
                    continue
                bbox = detection.get("bbox_xyxy")
                if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                    continue
                try:
                    x1, y1, x2, y2 = [int(float(value)) for value in bbox]
                except (TypeError, ValueError):
                    continue
                painter.drawRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
        finally:
            painter.end()

    def _format_detections(self):
        detections = self.response.get("detections")
        if not isinstance(detections, list) or not detections:
            return "감지 bbox 없음"

        parts = []
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            class_name = detection.get("class_name") or detection.get("label") or "object"
            confidence = detection.get("confidence")
            if confidence is None:
                parts.append(str(class_name))
            else:
                try:
                    parts.append(f"{class_name} {float(confidence):.2f}")
                except (TypeError, ValueError):
                    parts.append(str(class_name))
        return ", ".join(parts) or "감지 bbox 없음"


class TaskMonitorSnapshotLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, *, consumer_id):
        super().__init__()
        self.consumer_id = str(consumer_id or "").strip()

    def run(self):
        service = TaskMonitorRemoteService()

        try:
            response = service.get_task_monitor_snapshot(consumer_id=self.consumer_id)
            result_code = str((response or {}).get("result_code") or "").upper()
            self.finished.emit(result_code == "ACCEPTED", response or {})
        except Exception as exc:
            self.finished.emit(False, str(exc))


class FallEvidenceImageLookupWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, *, payload):
        super().__init__()
        self.payload = payload if isinstance(payload, dict) else {}

    def run(self):
        service = TaskMonitorRemoteService()

        try:
            response = service.get_fall_evidence_image(**self.payload)
            result_code = str((response or {}).get("result_code") or "").upper()
            self.finished.emit(result_code == "OK", response or {})
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": str(exc),
                    "reason_code": "CLIENT_EVIDENCE_QUERY_FAILED",
                },
            )


class TaskCancelWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, *, payload):
        super().__init__()
        self.payload = payload if isinstance(payload, dict) else {}

    def run(self):
        service = TaskMonitorRemoteService()

        try:
            response = service.cancel_task(**self.payload) or {}
            result_code = str(response.get("result_code", "")).upper()
            success = bool(response.get("cancel_requested")) or result_code in {
                "ACCEPTED",
                "CANCEL_REQUESTED",
                "CANCELLED",
            }
            self.finished.emit(success, response)
        except Exception as exc:
            self.finished.emit(
                False,
                {
                    "result_code": "CLIENT_ERROR",
                    "result_message": f"작업 취소 요청 중 오류가 발생했습니다.\n{exc}",
                    "reason_code": "CLIENT_EXCEPTION",
                    "task_id": self.payload.get("task_id"),
                    "task_status": None,
                    "assigned_robot_id": None,
                    "cancel_requested": False,
                },
            )


class TaskMonitorPage(QWidget):
    def __init__(self, *, autostart_stream=True):
        super().__init__()
        self.consumer_id = "ui-admin-task-monitor"
        self._tasks = {}
        self._row_by_task_id = {}
        self._selected_task_id = None
        self._last_event_seq = 0
        self._resume_dialog = None
        self.snapshot_thread = None
        self.snapshot_worker = None
        self.task_event_thread = None
        self.task_event_worker = None
        self.patrol_resume_thread = None
        self.patrol_resume_worker = None
        self.fall_evidence_thread = None
        self.fall_evidence_worker = None
        self.task_cancel_thread = None
        self.task_cancel_worker = None
        self._fall_evidence_dialog = None
        self._build_ui()
        if autostart_stream:
            self._start_snapshot_load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            PageHeader(
                "작업 모니터",
                "운반, 순찰, 안내 작업의 진행 상태와 피드백을 확인합니다.",
            ),
            1,
        )
        self.time_card = PageTimeCard(
            status_text="이벤트 스트림 연결 대기",
            refresh_text="새로고침",
            on_refresh=self.refresh_snapshot,
        )
        self.refresh_snapshot_btn = self.time_card.refresh_button
        self.reconnect_stream_btn = QPushButton("스트림 재연결")
        self.reconnect_stream_btn.setObjectName("secondaryButton")
        self.reconnect_stream_btn.clicked.connect(self.reconnect_task_event_stream)
        self.time_card.add_action(self.reconnect_stream_btn)
        self.stream_status_label = self.time_card.status_label
        self.last_update_label = self.time_card.last_update_label
        header_row.addWidget(self.time_card)

        root.addLayout(header_row)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        list_card = QFrame()
        list_card.setObjectName("formCard")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(20, 20, 20, 20)
        list_layout.setSpacing(12)

        list_title = QLabel("작업 목록")
        list_title.setObjectName("sectionTitle")
        list_header = QHBoxLayout()
        list_header.setSpacing(8)
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        self.empty_state_label = QLabel("수신된 작업 이벤트가 없습니다.")
        self.empty_state_label.setObjectName("mutedText")

        self.task_table = QTableWidget(0, 5)
        self.task_table.setObjectName("taskMonitorTable")
        self.task_table.setHorizontalHeaderLabels(
            ["task_id", "유형", "상태", "단계", "로봇"]
        )
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.itemSelectionChanged.connect(self._handle_table_selection_changed)

        list_layout.addLayout(list_header)
        list_layout.addWidget(self.empty_state_label)
        list_layout.addWidget(self.task_table, 1)

        detail_card = QFrame()
        detail_card.setObjectName("formCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(12)

        detail_title = QLabel("작업 상세")
        detail_title.setObjectName("sectionTitle")

        task_id_row, _task_id_text, self.detail_task_id_label = _metric_row("task_id")
        task_type_row, _task_type_text, self.detail_task_type_label = _metric_row("유형")
        status_row, _status_text, self.detail_task_status_label = _metric_row(
            "상태",
            "-",
            "robotStateChip",
        )
        phase_row, _phase_text, self.detail_phase_label = _metric_row("단계")
        robot_row, _robot_text, self.detail_robot_label = _metric_row("로봇")
        feedback_row, _feedback_text, self.detail_feedback_label = _metric_row("피드백")
        pose_row, _pose_text, self.detail_pose_label = _metric_row("위치")

        self.result_info_panel = TaskResultInfoPanel()
        self.detail_result_code_label = self.result_info_panel.result_code_label
        self.detail_reason_code_label = self.result_info_panel.reason_code_label
        self.detail_result_message_label = self.result_info_panel.result_message_label

        detail_action_row = QHBoxLayout()
        detail_action_row.setSpacing(8)
        self.cancel_task_btn = QPushButton("작업 취소")
        self.cancel_task_btn.setObjectName("dangerButton")
        self.cancel_task_btn.setEnabled(False)
        self.cancel_task_btn.clicked.connect(self._request_task_cancel)
        detail_action_row.addStretch(1)
        detail_action_row.addWidget(self.cancel_task_btn)

        self.cancel_status_label = QLabel("")
        self.cancel_status_label.setObjectName("mutedText")
        self.cancel_status_label.setWordWrap(True)
        self.cancel_status_label.setHidden(True)

        self.patrol_runtime_section = PatrolRuntimePanel()
        self.patrol_map_placeholder = self.patrol_runtime_section.patrol_map_placeholder
        self.patrol_map_overlay = self.patrol_runtime_section.patrol_map_overlay
        self.fall_marker_label = self.patrol_runtime_section.fall_marker_label
        self.fall_alert_panel = self.patrol_runtime_section.alert_panel
        self.fall_alert_task_label = self.patrol_runtime_section.fall_alert_task_label
        self.evidence_image_id_label = self.patrol_runtime_section.evidence_image_id_label
        self.fall_frame_id_label = self.patrol_runtime_section.fall_frame_id_label
        self.fall_streak_label = self.patrol_runtime_section.fall_streak_label
        self.evidence_image_btn = self.patrol_runtime_section.evidence_image_btn
        self.evidence_status_label = self.patrol_runtime_section.evidence_status_label
        self.evidence_image_btn.clicked.connect(self.open_fall_evidence_dialog)
        self.resume_patrol_btn = self.patrol_runtime_section.resume_patrol_btn
        self.resume_status_label = self.patrol_runtime_section.resume_status_label
        self.resume_patrol_btn.clicked.connect(self.open_patrol_resume_dialog)

        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(task_id_row)
        detail_layout.addWidget(task_type_row)
        detail_layout.addWidget(status_row)
        detail_layout.addWidget(phase_row)
        detail_layout.addWidget(robot_row)
        detail_layout.addWidget(feedback_row)
        detail_layout.addWidget(pose_row)
        detail_layout.addWidget(self.result_info_panel)
        detail_layout.addLayout(detail_action_row)
        detail_layout.addWidget(self.cancel_status_label)
        detail_layout.addWidget(self.patrol_runtime_section)
        detail_layout.addStretch(1)

        content_row.addWidget(list_card, 3)
        content_row.addWidget(detail_card, 2)
        root.addLayout(content_row, 1)

    def apply_stream_event(self, event):
        event = event or {}
        event_type = str(event.get("event_type") or "").strip().upper()
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            return

        if event_type == "TASK_UPDATED":
            self._apply_task_updated(payload)
            self._mark_last_update("event")
            return

        if event_type == "ACTION_FEEDBACK_UPDATED":
            self._apply_action_feedback_updated(payload)
            self._mark_last_update("event")
            return

        if event_type in {"ALERT_CREATED", "FALL_ALERT_CREATED"}:
            self._apply_alert_created(payload)
            self._mark_last_update("event")

    def apply_snapshot(self, snapshot):
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        tasks = [task for task in snapshot.get("tasks") or [] if isinstance(task, dict)]

        self._reset_task_list()
        first_task_id = None
        for task_payload in tasks:
            normalized_payload = self._normalize_snapshot_task(task_payload)
            task = self._merge_task_payload(normalized_payload)
            if task is None:
                continue
            if first_task_id is None:
                first_task_id = task["task_id"]
            self._upsert_task_row(task)

        if first_task_id is not None:
            self._select_task(first_task_id)
        else:
            self._render_detail({})

    def _reset_task_list(self):
        self.task_table.blockSignals(True)
        try:
            self.task_table.setRowCount(0)
            self._tasks.clear()
            self._row_by_task_id.clear()
            self._selected_task_id = None
            self.empty_state_label.setHidden(False)
        finally:
            self.task_table.blockSignals(False)

    @staticmethod
    def _normalize_snapshot_task(task_payload):
        normalized = dict(task_payload)

        latest_feedback = normalized.get("latest_feedback")
        if isinstance(latest_feedback, dict):
            normalized["feedback_summary"] = (
                latest_feedback.get("feedback_summary")
                or latest_feedback.get("summary")
                or normalized.get("feedback_summary")
            )
            if latest_feedback.get("pose") is not None:
                normalized["pose"] = latest_feedback.get("pose")

        latest_robot = normalized.get("latest_robot")
        if isinstance(latest_robot, dict):
            if not normalized.get("assigned_robot_id"):
                normalized["assigned_robot_id"] = latest_robot.get("robot_id")
            if latest_robot.get("pose") is not None and not normalized.get("pose"):
                normalized["pose"] = latest_robot.get("pose")

        latest_alert = normalized.get("latest_alert")
        if isinstance(latest_alert, dict):
            normalized["fall_alert"] = latest_alert

        return normalized

    def _apply_task_updated(self, payload):
        task = self._merge_task_payload(payload)
        if task is None:
            return
        self._upsert_task_row(task)
        self._select_task_if_needed(task["task_id"])

    def _apply_action_feedback_updated(self, payload):
        task = self._merge_task_payload(
            {
                "task_id": payload.get("task_id"),
                "feedback_summary": payload.get("feedback_summary"),
                "pose": payload.get("pose"),
            }
        )
        if task is None:
            return
        self._upsert_task_row(task)
        self._select_task_if_needed(task["task_id"])

    def _apply_alert_created(self, payload):
        task = self._merge_task_payload(
            {
                "task_id": payload.get("task_id"),
                "task_type": payload.get("task_type") or "PATROL",
                "task_status": payload.get("task_status"),
                "phase": payload.get("phase") or "WAIT_FALL_RESPONSE",
                "assigned_robot_id": payload.get("assigned_robot_id"),
            }
        )
        if task is None:
            return

        alert = dict(task.get("fall_alert") or {})
        alert.update(payload)
        task["fall_alert"] = alert
        self._upsert_task_row(task)
        self._select_task(task["task_id"])

    def _merge_task_payload(self, payload):
        task_id = _task_key(payload.get("task_id"))
        if task_id is None:
            return None

        task = self._tasks.setdefault("task_id:" + task_id, {"task_id": task_id})
        for key, value in payload.items():
            if value is not None:
                task[key] = value
        task["task_id"] = task_id
        return task

    def _upsert_task_row(self, task):
        task_id = task["task_id"]
        row = self._row_by_task_id.get(task_id)
        if row is None:
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)
            self._row_by_task_id[task_id] = row

        values = [
            task_id,
            _display(task.get("task_type")),
            _display(task.get("task_status")),
            _display(task.get("phase")),
            _display(task.get("assigned_robot_id")),
        ]
        for column, value in enumerate(values):
            item = self.task_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                self.task_table.setItem(row, column, item)
            item.setText(str(value))

        self.empty_state_label.setHidden(self.task_table.rowCount() > 0)

        if self._selected_task_id == task_id:
            self._render_detail(task)

    def _select_task_if_needed(self, task_id):
        if self._selected_task_id is None:
            self._select_task(task_id)
            return

        if self._selected_task_id == task_id:
            self._render_detail(self._tasks.get("task_id:" + task_id))

    def _select_task(self, task_id):
        task_id = _task_key(task_id)
        if task_id is None:
            return

        row = self._row_by_task_id.get(task_id)
        if row is not None:
            self.task_table.selectRow(row)

        self._selected_task_id = task_id
        self._render_detail(self._tasks.get("task_id:" + task_id))

    def _handle_table_selection_changed(self):
        selected_items = self.task_table.selectedItems()
        if not selected_items:
            return
        task_id_item = self.task_table.item(selected_items[0].row(), 0)
        if task_id_item is None:
            return
        self._selected_task_id = task_id_item.text()
        self._render_detail(self._tasks.get("task_id:" + self._selected_task_id))

    def _render_detail(self, task):
        task = task or {}
        self.detail_task_id_label.setText(_display(task.get("task_id")))
        self.detail_task_type_label.setText(_display(task.get("task_type")))
        self.detail_task_status_label.setText(_display(task.get("task_status")))
        self.detail_phase_label.setText(_display(task.get("phase")))
        self.detail_robot_label.setText(_display(task.get("assigned_robot_id")))
        self.detail_feedback_label.setText(_display(task.get("feedback_summary")))
        self.detail_pose_label.setText(_format_pose(task.get("pose")))
        self._render_result_info(task)
        self.cancel_status_label.setHidden(True)
        self._sync_cancel_action(task)
        self._render_fall_alert(task)

    def _render_result_info(self, task):
        self.result_info_panel.render(task)

    def _sync_cancel_action(self, task):
        task = task or {}
        task_id = task.get("task_id")
        task_type = str(task.get("task_type") or "").strip().upper()
        task_status = str(task.get("task_status") or "").strip().upper()
        cancellable = task.get("cancellable")
        default_text = "순찰 중단" if task_type == "PATROL" else "작업 취소"

        self.cancel_task_btn.setProperty("task_id", task_id)
        self.cancel_task_btn.setProperty("task_type", task_type)
        self.cancel_task_btn.setProperty("task_status", task_status)
        self.cancel_task_btn.setText(default_text)

        if task_status in CANCEL_IN_PROGRESS_STATUSES:
            self.cancel_task_btn.setText("취소 처리 중")
            self.cancel_task_btn.setEnabled(False)
            return

        if task_status in TERMINAL_TASK_STATUSES:
            self.cancel_task_btn.setText("취소 불가")
            self.cancel_task_btn.setEnabled(False)
            return

        if _task_key(task_id) is None:
            self.cancel_task_btn.setEnabled(False)
            return

        if cancellable is not None:
            self.cancel_task_btn.setEnabled(bool(cancellable))
            return

        self.cancel_task_btn.setEnabled(task_status in CANCELLABLE_TASK_STATUSES)

    def _request_task_cancel(self):
        task = self._current_task() or {}
        task_id = _task_key(task.get("task_id"))
        if task_id is None:
            self.cancel_status_label.setText("취소할 task_id가 없습니다.")
            self.cancel_status_label.setHidden(False)
            return

        current_user = SessionManager.current_user()
        caregiver_id = getattr(current_user, "user_id", None)
        if not str(caregiver_id or "").strip().isdigit():
            self.cancel_status_label.setText("취소 요청자 caregiver_id가 없습니다.")
            self.cancel_status_label.setHidden(False)
            return

        payload = {
            "task_id": task_id,
            "caregiver_id": int(caregiver_id),
            "reason": "operator_cancel",
        }
        self.cancel_task_btn.setEnabled(False)
        self.cancel_task_btn.setText("취소 요청 전송 중...")
        self.cancel_status_label.setText("취소 요청 전송 중...")
        self.cancel_status_label.setHidden(False)
        self._start_task_cancel(payload)

    def _start_task_cancel(self, payload):
        if self.task_cancel_thread is not None:
            return

        self.task_cancel_thread, self.task_cancel_worker = start_worker_thread(
            self,
            worker=TaskCancelWorker(payload=payload),
            finished_handler=self._handle_task_cancel_finished,
            clear_handler=self._clear_task_cancel_thread,
        )

    def _handle_task_cancel_finished(self, success, response):
        response = normalize_ui_response(
            response,
            success=success,
            default_fields={"cancel_requested": False},
        )

        if response.get("task_id"):
            self._apply_task_updated(response)
        else:
            self._render_detail(self._current_task())

        result_code = _display(response.get("result_code"))
        reason_code = _display(response.get("reason_code"))
        message = _display(response.get("result_message"))
        self.cancel_status_label.setText(f"{result_code} / {reason_code}: {message}")
        self.cancel_status_label.setHidden(False)
        self._mark_last_update("cancel")

    def _clear_task_cancel_thread(self):
        self.task_cancel_thread = None
        self.task_cancel_worker = None

    def _render_fall_alert(self, task):
        alert = task.get("fall_alert") or {}
        self.patrol_runtime_section.render(
            task,
            can_resume=self._can_resume_patrol(task),
            evidence_available=self._is_evidence_image_available(alert),
        )

    def _can_resume_patrol(self, task):
        task_type = str(task.get("task_type") or "").strip().upper()
        phase = str(task.get("phase") or "").strip().upper()
        return task_type == "PATROL" and phase in WAITING_FALL_RESPONSE_PHASES

    def open_fall_evidence_dialog(self):
        payload = self._build_fall_evidence_payload()
        if payload is None:
            self.evidence_status_label.setText("조회할 증거사진 정보가 없습니다.")
            self.evidence_status_label.setHidden(False)
            return

        self.evidence_image_btn.setEnabled(False)
        self.evidence_image_btn.setText("조회 중...")
        self.evidence_status_label.setText("증거사진 조회 중...")
        self.evidence_status_label.setHidden(False)
        self._start_fall_evidence_image_lookup(payload)

    def _build_fall_evidence_payload(self):
        task = self._current_task()
        if not task:
            return None

        alert = task.get("fall_alert") or {}
        evidence_image_id = str(alert.get("evidence_image_id") or "").strip()
        if not evidence_image_id:
            return None

        return {
            "consumer_id": self.consumer_id,
            "task_id": task.get("task_id"),
            "alert_id": alert.get("alert_id"),
            "evidence_image_id": evidence_image_id,
            "result_seq": alert.get("result_seq"),
        }

    def _start_fall_evidence_image_lookup(self, payload):
        if self.fall_evidence_thread is not None:
            return

        self.fall_evidence_thread, self.fall_evidence_worker = start_worker_thread(
            self,
            worker=FallEvidenceImageLookupWorker(payload=payload),
            finished_handler=self._handle_fall_evidence_finished,
            clear_handler=self._clear_fall_evidence_thread,
        )

    def _handle_fall_evidence_finished(self, success, response):
        response = normalize_ui_response(
            response,
            success=success,
            require_result_code=True,
        )

        self.evidence_image_btn.setText("증거사진 조회")
        self.evidence_image_btn.setEnabled(self._has_current_evidence_image())

        result_code = str(response.get("result_code") or "").upper()
        if success and result_code == "OK":
            self.evidence_status_label.setHidden(True)
            self._fall_evidence_dialog = self._create_fall_evidence_dialog(response)
            self._fall_evidence_dialog.open()
            return

        message = response.get("result_message") or result_code or "증거사진 조회 실패"
        self.evidence_status_label.setText(f"증거사진 조회 실패: {message}")
        self.evidence_status_label.setHidden(False)

    def _create_fall_evidence_dialog(self, response):
        return FallEvidenceImageDialog(response=response, parent=self)

    def _clear_fall_evidence_thread(self):
        self.fall_evidence_thread = None
        self.fall_evidence_worker = None

    def _current_task(self):
        if self._selected_task_id is None:
            return None
        return self._tasks.get("task_id:" + str(self._selected_task_id))

    def _has_current_evidence_image(self):
        task = self._current_task() or {}
        alert = task.get("fall_alert") or {}
        return self._is_evidence_image_available(alert)

    @staticmethod
    def _is_evidence_image_available(alert):
        if not isinstance(alert, dict):
            return False
        return bool(
            alert.get("evidence_image_id")
            and alert.get("evidence_image_available") is not False
        )

    def open_patrol_resume_dialog(self):
        if self._selected_task_id is None:
            return

        dialog = self._create_patrol_resume_dialog()
        self._resume_dialog = dialog
        dialog.accepted.connect(
            lambda dialog=dialog: self._handle_patrol_resume_dialog_accepted(dialog)
        )
        dialog.open()

    def _create_patrol_resume_dialog(self):
        return PatrolResumeDialog(task_id=self._selected_task_id, parent=self)

    def _handle_patrol_resume_dialog_accepted(self, dialog):
        current_user = SessionManager.current_user()
        caregiver_id = getattr(current_user, "user_id", None)

        try:
            payload = dialog.build_payload(caregiver_id=caregiver_id)
        except ValueError as exc:
            dialog.show_error(str(exc))
            return

        self.resume_patrol_btn.setEnabled(False)
        self.resume_patrol_btn.setText("재개 요청 전송 중...")
        self.resume_status_label.setText("순찰 재개 요청 전송 중...")
        self.resume_status_label.setHidden(False)
        self._start_patrol_resume_task(payload)

    def _start_patrol_resume_task(self, payload):
        if self.patrol_resume_thread is not None:
            return

        self.patrol_resume_thread, self.patrol_resume_worker = start_worker_thread(
            self,
            worker=PatrolResumeWorker(payload=payload),
            finished_handler=self._handle_patrol_resume_finished,
            clear_handler=self._clear_patrol_resume_thread,
        )

    def _handle_patrol_resume_finished(self, success, response):
        response = normalize_ui_response(response, success=success)

        self.resume_status_label.setText(_display(response.get("result_message")))
        self.resume_status_label.setHidden(False)

        if response.get("task_id"):
            self._apply_task_updated(response)
        else:
            self._render_detail(self._tasks.get("task_id:" + str(self._selected_task_id)))
        self._mark_last_update("patrol resume")

    def _clear_patrol_resume_thread(self):
        self.patrol_resume_thread = None
        self.patrol_resume_worker = None

    def refresh_snapshot(self):
        self._start_snapshot_load(status_text="수동 새로고침 중")

    def reconnect_task_event_stream(self):
        self.stream_status_label.setText("이벤트 스트림 재연결 중")
        self._stop_task_event_stream_thread()
        self._start_task_event_stream(last_seq=self._last_event_seq)

    def _start_snapshot_load(self, *, status_text="초기 상태 조회 중"):
        if self.snapshot_thread is not None:
            return False

        self.refresh_snapshot_btn.setEnabled(False)
        self.stream_status_label.setText(status_text)
        self.snapshot_thread, self.snapshot_worker = start_worker_thread(
            self,
            worker=TaskMonitorSnapshotLoadWorker(consumer_id=self.consumer_id),
            finished_handler=self._handle_snapshot_loaded,
            clear_handler=self._clear_snapshot_thread,
        )
        return True

    def _handle_snapshot_loaded(self, success, response):
        last_seq = 0
        if success and isinstance(response, dict):
            self.apply_snapshot(response)
            try:
                last_seq = int(response.get("last_event_seq") or 0)
            except (TypeError, ValueError):
                last_seq = 0
            self._last_event_seq = last_seq
            self.stream_status_label.setText("초기 상태 조회 완료")
            self._mark_last_update("snapshot")
        else:
            self.stream_status_label.setText(f"초기 상태 조회 실패: {response}")

        self.refresh_snapshot_btn.setEnabled(True)
        self._start_task_event_stream(last_seq=last_seq)

    def _clear_snapshot_thread(self):
        self.snapshot_thread = None
        self.snapshot_worker = None
        self.refresh_snapshot_btn.setEnabled(True)

    def _start_task_event_stream(self, *, last_seq=0):
        if self.task_event_thread is not None:
            return

        self.stream_status_label.setText("이벤트 스트림 연결 중")
        self.reconnect_stream_btn.setEnabled(True)
        self.task_event_thread, self.task_event_worker = start_worker_thread(
            self,
            worker=TaskEventStreamWorker(
                consumer_id=self.consumer_id,
                last_seq=last_seq,
            ),
            clear_handler=self._clear_task_event_stream_thread,
            worker_signal_connections={
                "batch_received": self._handle_task_event_batch,
                "failed": self._handle_task_event_stream_failed,
            },
        )

    def _handle_task_event_batch(self, batch):
        if not isinstance(batch, dict):
            return

        try:
            self._last_event_seq = int(batch.get("batch_end_seq") or self._last_event_seq)
        except (TypeError, ValueError):
            pass

        self.stream_status_label.setText(
            f"이벤트 스트림 수신 중 (seq {self._last_event_seq})"
        )
        for event in batch.get("events") or []:
            if isinstance(event, dict):
                self.apply_stream_event(event)
        self._mark_last_update("event")

    def _handle_task_event_stream_failed(self, error):
        logger.debug("task monitor event stream stopped: %s", error)
        self.stream_status_label.setText(f"이벤트 스트림 중단: {error}")
        self.reconnect_stream_btn.setEnabled(True)

    def _clear_task_event_stream_thread(self):
        self.task_event_thread = None
        self.task_event_worker = None

    def _mark_last_update(self, source):
        self.time_card.mark_updated(source)

    def _stop_task_event_stream_thread(self):
        worker = self.task_event_worker
        thread = self.task_event_thread
        if worker is not None:
            worker.stop()
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1000)
        self._clear_task_event_stream_thread()

    def _stop_snapshot_thread(self):
        if self.snapshot_thread is None:
            return
        if self.snapshot_thread.isRunning():
            self.snapshot_thread.quit()
            self.snapshot_thread.wait(1000)
        self._clear_snapshot_thread()

    def _stop_patrol_resume_thread(self):
        if self.patrol_resume_thread is None:
            return
        if self.patrol_resume_thread.isRunning():
            self.patrol_resume_thread.quit()
            self.patrol_resume_thread.wait(1000)
        self._clear_patrol_resume_thread()

    def _stop_fall_evidence_thread(self):
        if self.fall_evidence_thread is None:
            return
        if self.fall_evidence_thread.isRunning():
            self.fall_evidence_thread.quit()
            self.fall_evidence_thread.wait(1000)
        self._clear_fall_evidence_thread()

    def _stop_task_cancel_thread(self):
        if self.task_cancel_thread is None:
            return
        if self.task_cancel_thread.isRunning():
            self.task_cancel_thread.quit()
            self.task_cancel_thread.wait(1000)
        self._clear_task_cancel_thread()

    def reset_page(self):
        if self.task_table.rowCount() > 0:
            self._render_detail(self._tasks.get("task_id:" + str(self._selected_task_id)))

    def shutdown(self):
        self._stop_snapshot_thread()
        self._stop_task_event_stream_thread()
        self._stop_patrol_resume_thread()
        self._stop_fall_evidence_thread()
        self._stop_task_cancel_thread()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


__all__ = [
    "FallEvidenceImageDialog",
    "FallEvidenceImageLookupWorker",
    "PatrolResumeDialog",
    "TaskCancelWorker",
    "TaskMonitorPage",
    "TaskMonitorSnapshotLoadWorker",
]
