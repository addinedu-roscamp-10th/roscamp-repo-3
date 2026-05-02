from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.utils.widgets.map_overlay import PatrolMapOverlay


RESULT_ATTENTION_STATUSES = {
    "CANCEL_REQUESTED",
    "CANCELLED",
    "FAILED",
    "REJECTED",
}
RESULT_ATTENTION_CODES = {
    "CANCEL_REQUESTED",
    "CANCELLED",
    "CLIENT_ERROR",
    "FAILED",
    "NOT_ALLOWED",
    "NOT_FOUND",
    "REJECTED",
}


def _display(value):
    if value is None or value == "":
        return "-"
    return str(value)


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
    return row, label, value


def _format_pose(pose):
    if not isinstance(pose, dict):
        return _display(pose)

    try:
        x = float(pose.get("x"))
        y = float(pose.get("y"))
        yaw = float(pose.get("yaw", 0.0))
    except (TypeError, ValueError):
        return _display(pose)

    return f"x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"


class TaskResultInfoPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("taskResultPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("결과 정보")
        title.setObjectName("sectionTitle")
        (
            result_code_row,
            _result_code_text,
            self.result_code_label,
        ) = _metric_row("결과")
        (
            reason_code_row,
            _reason_code_text,
            self.reason_code_label,
        ) = _metric_row("사유")
        (
            result_message_row,
            _result_message_text,
            self.result_message_label,
        ) = _metric_row("메시지")

        layout.addWidget(title)
        layout.addWidget(result_code_row)
        layout.addWidget(reason_code_row)
        layout.addWidget(result_message_row)

    def render(self, task):
        task = task or {}
        result_code = task.get("result_code") or task.get("task_outcome")
        reason_code = task.get("reason_code") or task.get("latest_reason_code")
        result_message = task.get("result_message") or task.get("message")

        self.result_code_label.setText(_display(result_code))
        self.reason_code_label.setText(_display(reason_code))
        self.result_message_label.setText(_display(result_message))

        task_status = str(task.get("task_status") or "").strip().upper()
        normalized_result_code = str(result_code or "").strip().upper()
        if (
            task_status in RESULT_ATTENTION_STATUSES
            or normalized_result_code in RESULT_ATTENTION_CODES
        ):
            self.setObjectName("taskResultPanelWarning")
        else:
            self.setObjectName("taskResultPanel")
        self.style().unpolish(self)
        self.style().polish(self)


class PatrolRuntimePanel(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.patrol_map_placeholder = QFrame()
        self.patrol_map_placeholder.setObjectName("patrolMapPlaceholder")
        map_layout = QVBoxLayout(self.patrol_map_placeholder)
        map_layout.setContentsMargins(16, 16, 16, 16)
        map_layout.setSpacing(8)
        self.patrol_map_overlay = PatrolMapOverlay()
        self.fall_marker_label = QLabel("낙상 지점 미수신")
        self.fall_marker_label.setObjectName("fallAlertMarker")
        self.fall_marker_label.setWordWrap(True)
        self.fall_marker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(self.patrol_map_overlay)
        map_layout.addWidget(self.fall_marker_label)

        self.alert_panel = QFrame()
        self.alert_panel.setObjectName("fallAlertPanel")
        alert_layout = QVBoxLayout(self.alert_panel)
        alert_layout.setContentsMargins(14, 14, 14, 14)
        alert_layout.setSpacing(8)

        alert_title = QLabel("낙상 감지")
        alert_title.setObjectName("sectionTitle")
        (
            alert_task_row,
            _alert_task_text,
            self.fall_alert_task_label,
        ) = _metric_row("task_id")
        (
            evidence_row,
            _evidence_text,
            self.evidence_image_id_label,
        ) = _metric_row("증거사진")
        frame_row, _frame_text, self.fall_frame_id_label = _metric_row("frame_id")
        streak_row, _streak_text, self.fall_streak_label = _metric_row("누적 감지")

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.evidence_image_btn = QPushButton("증거사진 조회")
        self.evidence_image_btn.setObjectName("secondaryButton")
        self.evidence_image_btn.setEnabled(False)
        self.resume_patrol_btn = QPushButton("현장 조치 후 순찰 재개")
        self.resume_patrol_btn.setObjectName("patrolResumeButton")
        self.resume_patrol_btn.setEnabled(False)
        action_row.addWidget(self.evidence_image_btn)
        action_row.addWidget(self.resume_patrol_btn)

        self.evidence_status_label = QLabel("")
        self.evidence_status_label.setObjectName("mutedText")
        self.evidence_status_label.setWordWrap(True)
        self.evidence_status_label.setHidden(True)

        self.resume_status_label = QLabel("")
        self.resume_status_label.setObjectName("mutedText")
        self.resume_status_label.setWordWrap(True)
        self.resume_status_label.setHidden(True)

        alert_layout.addWidget(alert_title)
        alert_layout.addWidget(alert_task_row)
        alert_layout.addWidget(evidence_row)
        alert_layout.addWidget(frame_row)
        alert_layout.addWidget(streak_row)
        alert_layout.addLayout(action_row)
        alert_layout.addWidget(self.evidence_status_label)
        alert_layout.addWidget(self.resume_status_label)
        self.alert_panel.setHidden(True)

        root.addWidget(self.patrol_map_placeholder)
        root.addWidget(self.alert_panel)

    def render(self, task, *, can_resume, evidence_available):
        task = task or {}
        alert = task.get("fall_alert") or {}
        has_alert = bool(alert)
        should_show = has_alert or bool(can_resume)
        self.patrol_map_overlay.render(task)
        self.alert_panel.setHidden(not should_show)
        self.evidence_status_label.setHidden(True)
        self.resume_status_label.setHidden(True)

        if not should_show:
            self.fall_marker_label.setText("낙상 지점 미수신")
            self.evidence_image_btn.setEnabled(False)
            self.resume_patrol_btn.setEnabled(False)
            return

        task_id = task.get("task_id")
        evidence_id = alert.get("evidence_image_id")
        frame_id = alert.get("frame_id")
        fall_streak_ms = alert.get("fall_streak_ms")
        zone_text = alert.get("zone_name") or alert.get("zone_id") or "구역 미수신"
        pose_text = _format_pose(alert.get("alert_pose") or alert.get("pose"))

        self.fall_alert_task_label.setText(_display(task_id))
        self.evidence_image_id_label.setText(_display(evidence_id))
        self.fall_frame_id_label.setText(_display(frame_id))
        self.fall_streak_label.setText(
            f"{fall_streak_ms}ms" if fall_streak_ms not in (None, "") else "-"
        )
        self.fall_marker_label.setText(f"{zone_text}\n{pose_text}")
        self.evidence_image_btn.setEnabled(bool(evidence_available))
        self.resume_patrol_btn.setEnabled(bool(can_resume))
        self.resume_patrol_btn.setText("현장 조치 후 순찰 재개")


__all__ = [
    "PatrolRuntimePanel",
    "TaskResultInfoPanel",
    "_display",
    "_format_pose",
    "_metric_row",
]
