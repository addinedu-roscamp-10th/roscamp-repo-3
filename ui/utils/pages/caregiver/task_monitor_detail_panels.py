import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.utils.widgets.admin_common import make_key_value_row
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
    return make_key_value_row(
        label_text,
        value_text,
        row_object_name="sideMetricRow",
        key_object_name="sideMetricLabel",
        value_object_name=value_object_name,
    )


def _format_pose(pose):
    pose = _normalize_pose(pose)
    if not isinstance(pose, dict):
        return _display(pose)

    try:
        x = float(pose.get("x"))
        y = float(pose.get("y"))
        yaw = float(pose.get("yaw", 0.0))
    except (TypeError, ValueError):
        return _display(pose)

    return f"x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"


def _normalize_pose(pose):
    if not isinstance(pose, dict):
        return pose
    if "x" in pose and "y" in pose:
        return pose

    stamped_pose = pose.get("pose")
    if not isinstance(stamped_pose, dict):
        return pose
    position = stamped_pose.get("position")
    if not isinstance(position, dict):
        return pose

    normalized = {
        "x": position.get("x"),
        "y": position.get("y"),
    }
    orientation = stamped_pose.get("orientation")
    if isinstance(orientation, dict):
        normalized["yaw"] = _yaw_from_quaternion(orientation)
    header = pose.get("header")
    if isinstance(header, dict) and header.get("frame_id") not in (None, ""):
        normalized["frame_id"] = header.get("frame_id")
    return normalized


def _yaw_from_quaternion(orientation):
    try:
        x = float(orientation.get("x", 0.0))
        y = float(orientation.get("y", 0.0))
        z = float(orientation.get("z", 0.0))
        w = float(orientation.get("w", 1.0))
    except (TypeError, ValueError):
        return 0.0
    siny_cosp = 2.0 * ((w * z) + (x * y))
    cosy_cosp = 1.0 - (2.0 * ((y * y) + (z * z)))
    return math.atan2(siny_cosp, cosy_cosp)


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


class GuideRuntimePanel(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.guide_info_panel = QFrame()
        self.guide_info_panel.setObjectName("guideRuntimePanel")
        panel_layout = QVBoxLayout(self.guide_info_panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(8)

        title = QLabel("안내 진행")
        title.setObjectName("sectionTitle")
        (
            guide_phase_row,
            _guide_phase_text,
            self.guide_phase_label,
        ) = _metric_row("안내 단계")
        (
            target_track_row,
            _target_track_text,
            self.target_track_id_label,
        ) = _metric_row("추적 ID")
        visitor_row, _visitor_text, self.visitor_label = _metric_row("방문자")
        resident_row, _resident_text, self.resident_label = _metric_row("어르신")
        destination_row, _destination_text, self.destination_label = _metric_row(
            "목적지"
        )

        panel_layout.addWidget(title)
        panel_layout.addWidget(guide_phase_row)
        panel_layout.addWidget(target_track_row)
        panel_layout.addWidget(visitor_row)
        panel_layout.addWidget(resident_row)
        panel_layout.addWidget(destination_row)
        root.addWidget(self.guide_info_panel)
        self.setHidden(True)

    def render(self, task):
        task = task if isinstance(task, dict) else {}
        task_type = str(task.get("task_type") or "").strip().upper()
        if task_type != "GUIDE":
            self.setHidden(True)
            self._reset_inactive_state()
            return

        detail = task.get("guide_detail")
        detail = detail if isinstance(detail, dict) else {}
        self.setHidden(False)
        self.guide_phase_label.setText(
            _display(
                detail.get("guide_phase")
                or task.get("guide_phase")
                or task.get("phase")
            )
        )
        self.target_track_id_label.setText(
            _display(detail.get("target_track_id") or task.get("target_track_id"))
        )
        self.visitor_label.setText(self._format_visitor(detail, task))
        self.resident_label.setText(self._format_resident(detail, task))
        self.destination_label.setText(self._format_destination(detail, task))

    def _reset_inactive_state(self):
        self.guide_phase_label.setText("-")
        self.target_track_id_label.setText("-")
        self.visitor_label.setText("-")
        self.resident_label.setText("-")
        self.destination_label.setText("-")

    @classmethod
    def _format_visitor(cls, detail, task):
        visitor_name = detail.get("visitor_name") or task.get("visitor_name")
        visitor_id = detail.get("visitor_id") or task.get("visitor_id")
        relation_name = detail.get("relation_name") or task.get("relation_name")
        return cls._join_display_parts(
            visitor_name,
            f"visitor_id={visitor_id}" if visitor_id not in (None, "") else None,
            relation_name,
        )

    @classmethod
    def _format_resident(cls, detail, task):
        resident_name = (
            detail.get("resident_name")
            or detail.get("member_name")
            or task.get("resident_name")
            or task.get("member_name")
        )
        member_id = detail.get("member_id") or task.get("member_id")
        room_no = detail.get("room_no") or task.get("room_no")
        room_text = cls._format_room_no(room_no)
        return cls._join_display_parts(
            resident_name,
            f"member_id={member_id}" if member_id not in (None, "") else None,
            room_text,
        )

    @classmethod
    def _format_destination(cls, detail, task):
        destination_id = (
            detail.get("destination_id")
            or detail.get("destination_goal_pose_id")
            or task.get("destination_id")
            or task.get("destination_goal_pose_id")
        )
        zone_name = detail.get("destination_zone_name") or task.get(
            "destination_zone_name"
        )
        zone_id = detail.get("destination_zone_id") or task.get("destination_zone_id")
        return cls._join_display_parts(destination_id, zone_name, zone_id)

    @staticmethod
    def _join_display_parts(*parts):
        values = [str(part).strip() for part in parts if part not in (None, "")]
        return " / ".join(values) if values else "-"

    @staticmethod
    def _format_room_no(room_no):
        if room_no in (None, ""):
            return None
        text = str(room_no).strip()
        if not text:
            return None
        return text if text.endswith("호") else f"{text}호"


class PatrolRuntimePanel(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("patrolRuntimeInfoPanel")
        progress_layout = QVBoxLayout(self.progress_panel)
        progress_layout.setContentsMargins(14, 14, 14, 14)
        progress_layout.setSpacing(8)

        progress_title = QLabel("순찰 진행")
        progress_title.setObjectName("sectionTitle")
        area_row, _area_text, self.patrol_area_label = _metric_row("구역")
        robot_row, _robot_text, self.patrol_robot_label = _metric_row("로봇")
        status_row, _status_text, self.patrol_status_label = _metric_row("상태")
        waypoint_row, _waypoint_text, self.patrol_waypoint_label = _metric_row(
            "waypoint"
        )
        distance_row, _distance_text, self.patrol_distance_label = _metric_row(
            "남은 거리"
        )
        location_row, _location_text, self.patrol_location_label = _metric_row("위치")

        progress_layout.addWidget(progress_title)
        progress_layout.addWidget(area_row)
        progress_layout.addWidget(robot_row)
        progress_layout.addWidget(status_row)
        progress_layout.addWidget(waypoint_row)
        progress_layout.addWidget(distance_row)
        progress_layout.addWidget(location_row)

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

        root.addWidget(self.progress_panel)
        root.addWidget(self.patrol_map_placeholder)
        root.addWidget(self.alert_panel)

    def render(self, task, *, can_resume, evidence_available):
        task = task if isinstance(task, dict) else {}
        task_type = str(task.get("task_type") or "").strip().upper()
        if task_type != "PATROL":
            self.setHidden(True)
            self._reset_inactive_state()
            self.patrol_map_overlay.render({})
            return

        self.setHidden(False)
        alert = task.get("fall_alert") or {}
        has_alert = bool(alert)
        should_show = has_alert or bool(can_resume)
        self._render_progress(task)
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

    def _render_progress(self, task):
        self.patrol_area_label.setText(self._format_patrol_area(task))
        self.patrol_robot_label.setText(_display(task.get("assigned_robot_id")))
        self.patrol_status_label.setText(self._format_patrol_status(task))
        self.patrol_waypoint_label.setText(self._format_waypoint(task))
        self.patrol_distance_label.setText(self._format_distance(task))
        self.patrol_location_label.setText(self._format_location(task))

    def _reset_inactive_state(self):
        self.patrol_area_label.setText("-")
        self.patrol_robot_label.setText("-")
        self.patrol_status_label.setText("feedback 수신 전")
        self.patrol_waypoint_label.setText("미수신")
        self.patrol_distance_label.setText("미수신")
        self.patrol_location_label.setText("미수신")
        self.alert_panel.setHidden(True)
        self.evidence_status_label.setHidden(True)
        self.resume_status_label.setHidden(True)
        self.fall_marker_label.setText("낙상 지점 미수신")
        self.evidence_image_btn.setEnabled(False)
        self.evidence_image_btn.setText("증거사진 조회")
        self.resume_patrol_btn.setEnabled(False)
        self.resume_patrol_btn.setText("현장 조치 후 순찰 재개")

    @classmethod
    def _format_patrol_area(cls, task):
        parts = [
            task.get("patrol_area_name"),
            task.get("patrol_area_id"),
        ]
        revision = task.get("patrol_area_revision")
        if revision not in (None, ""):
            parts.append(f"rev {revision}")
        values = [str(part).strip() for part in parts if part not in (None, "")]
        return " / ".join(values) if values else "-"

    @classmethod
    def _format_patrol_status(cls, task):
        return _display(
            cls._first_present(
                task.get("patrol_status"),
                cls._latest_feedback(task).get("patrol_status"),
            )
            or "feedback 수신 전"
        )

    @classmethod
    def _format_waypoint(cls, task):
        current_index = cls._optional_int(
            cls._first_present(
                task.get("current_waypoint_index"),
                cls._latest_feedback(task).get("current_waypoint_index"),
                cls._patrol_path(task).get("current_waypoint_index"),
            )
        )
        total = cls._optional_int(
            cls._first_present(
                task.get("total_waypoints"),
                task.get("waypoint_count"),
                cls._latest_feedback(task).get("total_waypoints"),
                cls._patrol_path(task).get("waypoint_count"),
            )
        )
        if current_index is None or total is None or total <= 0:
            return "미수신"
        return f"{current_index + 1} / {total}"

    @classmethod
    def _format_distance(cls, task):
        distance = cls._optional_float(
            cls._first_present(
                task.get("distance_remaining_m"),
                cls._latest_feedback(task).get("distance_remaining_m"),
            )
        )
        if distance is None or distance < 0:
            return "미수신"
        return f"{distance:.2f}m"

    @classmethod
    def _format_location(cls, task):
        pose = cls._first_present(
            task.get("current_pose"),
            task.get("pose"),
            cls._latest_feedback(task).get("current_pose"),
            cls._latest_feedback(task).get("pose"),
            cls._latest_robot(task).get("pose"),
        )
        if pose in (None, ""):
            return "미수신"
        return _format_pose(pose)

    @staticmethod
    def _latest_feedback(task):
        feedback = task.get("latest_feedback")
        return feedback if isinstance(feedback, dict) else {}

    @staticmethod
    def _latest_robot(task):
        robot = task.get("latest_robot")
        return robot if isinstance(robot, dict) else {}

    @staticmethod
    def _patrol_path(task):
        path = task.get("patrol_path")
        return path if isinstance(path, dict) else {}

    @staticmethod
    def _first_present(*values):
        for value in values:
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "GuideRuntimePanel",
    "PatrolRuntimePanel",
    "TaskResultInfoPanel",
    "_display",
    "_format_pose",
    "_metric_row",
]
