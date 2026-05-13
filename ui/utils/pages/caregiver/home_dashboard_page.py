from __future__ import annotations

import base64
import binascii
import math
from collections.abc import Iterable

from PyQt6.QtCore import QObject, QPointF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from server.ropi_main_service.transport.tcp_protocol import MESSAGE_CODE_HEARTBEAT
from ui.utils.core.responses import normalize_ui_response
from ui.utils.core.stream_refresh import VisibleDeferredRefresh
from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.tcp_client import send_request
from ui.utils.network.service_clients import (
    CaregiverRemoteService,
    CoordinateConfigRemoteService,
    TaskMonitorRemoteService,
)
from ui.utils.pages.caregiver.robot_stream_pose import (
    normalize_stream_pose,
    robot_id_from_action_name,
)
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_common import (
    StatusChip,
    battery_text as _battery_text,
    display_text as _display,
    operator_datetime_text as _datetime,
)
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard
from ui.utils.widgets.map_canvas import MapCanvasWidget


CANCELABLE_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
    "IN_PROGRESS",
}

CANCELING_TASK_STATUSES = {"CANCEL_REQUESTED", "CANCELLING", "PREEMPTING"}

FLOW_COLUMNS = (
    ("WAITING", "대기", {"WAITING", "WAITING_DISPATCH", "READY"}),
    ("ASSIGNED", "배정", {"ASSIGNED"}),
    ("IN_PROGRESS", "진행 중", {"RUNNING", "IN_PROGRESS"}),
    ("CANCELING", "취소 중", CANCELING_TASK_STATUSES),
    ("DONE", "완료/실패", set()),
)

HOME_FLOW_RENDER_ORDER = ("CANCELING", "IN_PROGRESS", "ASSIGNED", "WAITING", "DONE")

TASK_TYPE_LABELS = {
    "DELIVERY": "운반",
    "PATROL": "순찰",
    "GUIDE": "안내",
    "FOLLOW": "추종",
}

TASK_STATUS_LABELS = {
    "WAITING": "대기",
    "WAITING_DISPATCH": "배차 대기",
    "READY": "준비",
    "ASSIGNED": "배정",
    "RUNNING": "진행 중",
    "IN_PROGRESS": "진행 중",
    "CANCEL_REQUESTED": "취소 요청",
    "CANCELLING": "취소 중",
    "PREEMPTING": "선점 처리",
    "COMPLETED": "완료",
    "FAILED": "실패",
    "CANCELLED": "취소됨",
    "REJECTED": "거절",
}

TASK_PHASE_LABELS = {
    "REQUESTED": "요청 접수",
    "WAITING_DISPATCH": "배차 대기",
    "READY": "준비",
    "MOVE_TO_PICKUP": "픽업 지점 이동",
    "DELIVERY_PICKUP": "픽업 수행",
    "MOVE_TO_DESTINATION": "목적지 이동",
    "DELIVERY_DESTINATION": "목적지 도착",
    "RUNNING": "진행 중",
    "WAIT_GUIDE_START_CONFIRM": "안내 시작 확인 대기",
    "WAIT_TARGET_TRACKING": "안내 대상 확인",
    "READY_TO_START_GUIDANCE": "안내 시작 준비",
    "GUIDANCE_RUNNING": "안내 주행 중",
    "WAIT_REIDENTIFY": "안내 대상 재확인",
    "GUIDANCE_FINISHED": "안내 완료",
    "GUIDANCE_CANCELLED": "안내 취소",
    "GUIDANCE_FAILED": "안내 실패",
    "WAIT_FALL_RESPONSE": "낙상 대응 대기",
    "COMPLETED": "완료",
    "FAILED": "실패",
    "CANCEL_REQUESTED": "취소 요청",
    "CANCELLED": "취소됨",
}

REASON_LABELS = {
    "ROS_SERVICE_UNAVAILABLE": "ROS 브릿지 미연결",
    "CLIENT_EXCEPTION": "클라이언트 오류",
    "CLIENT_ERROR": "클라이언트 오류",
    "ACTION_REJECTED": "명령 거절",
    "ROS_ACTION_FAILED": "ROS 명령 실패",
    "GUIDE_STATE_MISMATCH": "안내 상태 불일치",
    "GUIDE_COMMAND_REJECTED": "안내 명령 거절",
    "GUIDE_COMMAND_TRANSPORT_ERROR": "안내 명령 통신 실패",
    "GUIDE_RUNTIME_NOT_READY": "안내 런타임 미준비",
    "GUIDE_DESTINATION_NOT_CONFIGURED": "안내 목적지 미설정",
    "GUIDE_DESTINATION_POSE_INVALID": "안내 목적지 좌표 오류",
}

ROS_ERROR_MARKERS = (
    "ROS service command failed",
    "No such file or directory",
    "Connection refused",
    "ROPI_ROS_SERVICE_SOCKET",
)

HOME_SYSTEM_STATUS_POLL_INTERVAL_MS = 2000
HOME_MAP_FLOW_PANEL_MIN_WIDTH = 420
HOME_MAP_FLOW_PANEL_HEIGHT = 396
HOME_MAP_CANVAS_MAX_HEIGHT = 320
HOME_FLOW_SCROLL_MAX_HEIGHT = 320


def _is_ok_response(response):
    return isinstance(response, dict) and response.get("result_code", "OK") == "OK"


def _format_response_error(response, default_message):
    response = response if isinstance(response, dict) else {}
    return str(
        response.get("result_message") or response.get("reason_code") or default_message
    )


def _decode_base64_asset(value):
    try:
        return base64.b64decode(str(value or "").encode("ascii"), validate=True)
    except (binascii.Error, ValueError):
        return b""


def _optional_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _selected_home_map_id(*, preferred_map_id, map_profiles, robots):
    map_ids = [
        str(profile.get("map_id") or "").strip()
        for profile in map_profiles or []
        if isinstance(profile, dict) and str(profile.get("map_id") or "").strip()
    ]
    preferred_map_id = str(preferred_map_id or "").strip()
    if preferred_map_id and preferred_map_id in map_ids:
        return preferred_map_id

    robot_map_counts = {}
    for robot in robots or []:
        pose = robot.get("current_pose") if isinstance(robot, dict) else None
        if not isinstance(pose, dict):
            continue
        map_id = str(pose.get("map_id") or "").strip()
        if map_id and map_id in map_ids:
            robot_map_counts[map_id] = robot_map_counts.get(map_id, 0) + 1
    if robot_map_counts:
        return sorted(robot_map_counts.items(), key=lambda item: (-item[1], item[0]))[
            0
        ][0]

    for profile in map_profiles or []:
        if not isinstance(profile, dict):
            continue
        if bool(profile.get("is_active")):
            return str(profile.get("map_id") or "").strip()
    return map_ids[0] if map_ids else None


def _status_of(task: dict) -> str:
    return _display(task.get("task_status"), "UNKNOWN").upper()


def _effective_task_status(task: dict) -> str:
    status = _status_of(task)
    task_type = str(task.get("task_type") or task.get("scenario") or "").upper()
    result_code = str(task.get("result_code") or "").upper()
    if status == "FAILED" or result_code == "FAILED":
        return "FAILED"
    if task_type == "GUIDE" and result_code == "REJECTED":
        return "FAILED"
    return status


def _task_id_value(task: dict):
    task_id = task.get("task_id")
    if isinstance(task_id, int):
        return task_id
    text = str(task_id or "").strip()
    if text.isdigit():
        return int(text)
    return text or None


def _capabilities_text(capabilities) -> str:
    if isinstance(capabilities, (list, tuple)):
        values = [str(item).strip() for item in capabilities if str(item).strip()]
        return ", ".join(values) if values else "-"
    return _display(capabilities)


def _label_from(mapping, value, default="-"):
    text = _display(value, default)
    if text == default:
        return text
    normalized = text.upper()
    return mapping.get(normalized, text)


def _task_status_label(value):
    if isinstance(value, dict):
        value = _effective_task_status(value)
    return _label_from(TASK_STATUS_LABELS, value)


def _task_status_chip_type(value):
    if isinstance(value, dict):
        value = _effective_task_status(value)
    status = str(value or "").upper()
    if status in {"FAILED", "CANCELLED"}:
        return "red"
    if status in CANCELING_TASK_STATUSES:
        return "yellow"
    if status in {"RUNNING", "IN_PROGRESS"}:
        return "green"
    return "blue"


def _summary_and_detail(message):
    text = _display(message, "")
    if not text:
        return "", ""
    if any(marker in text for marker in ROS_ERROR_MARKERS):
        return "ROS 브릿지에 연결할 수 없습니다.", text
    return text, ""


def _reason_label(value):
    return _label_from(REASON_LABELS, value, "")


def _set_style_property(widget, name: str, value: str):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class DashboardLoadWorker(QObject):
    finished = pyqtSignal(object, object, object, object, object, object, object)

    def __init__(
        self,
        *,
        selected_map_id=None,
        cached_map_assets_by_map_id=None,
    ):
        super().__init__()
        self.selected_map_id = str(selected_map_id or "").strip() or None
        self.cached_map_assets_by_map_id = (
            cached_map_assets_by_map_id
            if isinstance(cached_map_assets_by_map_id, dict)
            else {}
        )

    def run(self):
        system_statuses = self._load_system_statuses()
        try:
            bundle = CaregiverRemoteService().get_dashboard_bundle() or {}
            summary = bundle.get("summary", {})
            robots = bundle.get("robots", [])
            flow_data = bundle.get("flow_data", {})
            timeline_rows = bundle.get("timeline_rows", [])
            map_data = self._load_home_map_data(robots)
            self.finished.emit(
                True,
                summary,
                robots,
                flow_data,
                timeline_rows,
                system_statuses,
                map_data,
            )
        except Exception as exc:
            self.finished.emit(False, str(exc), [], {}, [], system_statuses, {})

    def _load_home_map_data(self, robots):
        map_data = {}
        try:
            service = CoordinateConfigRemoteService()
            profiles_response = service.list_map_profiles()
            if not _is_ok_response(profiles_response):
                map_data["map_asset_error"] = _format_response_error(
                    profiles_response,
                    "맵 목록을 불러오지 못했습니다.",
                )
                return map_data

            profiles = [
                profile
                for profile in profiles_response.get("map_profiles") or []
                if isinstance(profile, dict)
            ]
            map_data["map_profiles"] = profiles
            selected_map_id = _selected_home_map_id(
                preferred_map_id=self.selected_map_id,
                map_profiles=profiles,
                robots=robots or [],
            )
            map_data["selected_map_id"] = selected_map_id
            if not selected_map_id:
                return map_data

            cached_assets = self.cached_map_assets_by_map_id.get(selected_map_id)
            if isinstance(cached_assets, dict):
                map_data["map_assets"] = dict(cached_assets)
                return map_data

            yaml_asset = service.get_map_asset(
                asset_type="YAML",
                map_id=selected_map_id,
                encoding="TEXT",
            )
            if not _is_ok_response(yaml_asset):
                map_data["map_asset_error"] = _format_response_error(
                    yaml_asset,
                    "맵 YAML을 불러오지 못했습니다.",
                )
                return map_data

            pgm_asset = service.get_map_asset(
                asset_type="PGM",
                map_id=selected_map_id,
                encoding="BASE64",
            )
            if not _is_ok_response(pgm_asset):
                map_data["map_asset_error"] = _format_response_error(
                    pgm_asset,
                    "맵 PGM을 불러오지 못했습니다.",
                )
                return map_data

            map_data["map_assets"] = {
                "map_id": selected_map_id,
                "yaml_text": str(yaml_asset.get("content_text") or ""),
                "pgm_bytes": _decode_base64_asset(pgm_asset.get("content_base64")),
                "yaml_sha256": yaml_asset.get("sha256"),
                "pgm_sha256": pgm_asset.get("sha256"),
            }
        except Exception as exc:
            map_data["map_asset_error"] = str(exc)
        return map_data

    @classmethod
    def _load_system_statuses(cls):
        try:
            response = send_request(
                MESSAGE_CODE_HEARTBEAT,
                {"check_db": True, "check_ros": True, "check_ai": True},
            )
        except Exception:
            return {
                "관제 서버": "offline",
                "데이터베이스": "unknown",
                "ROS2": "unknown",
                "AI 서버": "unknown",
            }

        if not response.get("ok"):
            return {
                "관제 서버": "offline",
                "데이터베이스": "unknown",
                "ROS2": "unknown",
                "AI 서버": "unknown",
            }

        payload = response.get("payload") or {}
        return {
            "관제 서버": "online",
            "데이터베이스": cls._component_status(payload.get("db")),
            "ROS2": cls._component_status(payload.get("ros")),
            "AI 서버": cls._component_status(payload.get("ai")),
        }

    @staticmethod
    def _component_status(component):
        if not isinstance(component, dict):
            return "unknown"
        if component.get("disabled"):
            return "disabled"
        return "online" if component.get("ok") else "offline"


class HomeSystemStatusWorker(QObject):
    finished = pyqtSignal(object)

    def run(self):
        self.finished.emit(DashboardLoadWorker._load_system_statuses())


class DashboardTaskCancelWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload if isinstance(payload, dict) else {}

    def run(self):
        try:
            response = TaskMonitorRemoteService().cancel_task(**self.payload) or {}
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


class HomeOperationMapCanvas(MapCanvasWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeOperationMapCanvas")
        self.background_color = QColor("#FFFFFF")
        self.setMinimumHeight(260)
        self.setMaximumHeight(HOME_MAP_CANVAS_MAX_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.visible_robot_ids = []
        self.robot_markers = []
        self._syncing_canvas_height = False

    def load_map_from_assets(self, *, yaml_text, pgm_bytes, cache_key=None):
        super().load_map_from_assets(
            yaml_text=yaml_text,
            pgm_bytes=pgm_bytes,
            cache_key=cache_key,
        )
        self._sync_canvas_height_to_map_ratio()

    def clear_map(self, status_text="맵 미수신"):
        super().clear_map(status_text)
        self.setMinimumHeight(260)
        self.setMaximumHeight(HOME_MAP_CANVAS_MAX_HEIGHT)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_canvas_height_to_map_ratio()

    def _sync_canvas_height_to_map_ratio(self):
        if self._syncing_canvas_height or not self.map_loaded or not self.map_image_size:
            return
        image_width, image_height = self.map_image_size
        if image_width <= 0 or image_height <= 0 or self.width() <= 0:
            return
        target_height = max(220, int(round(self.width() * image_height / image_width)))
        target_height = min(HOME_MAP_CANVAS_MAX_HEIGHT, target_height)
        if abs(self.height() - target_height) <= 1:
            return
        self._syncing_canvas_height = True
        try:
            self.setFixedHeight(target_height)
        finally:
            self._syncing_canvas_height = False

    def show_robots(self, robots, *, selected_map_id):
        self.visible_robot_ids = []
        self.robot_markers = []
        selected_map_id = str(selected_map_id or "").strip()
        if not self.map_loaded or not selected_map_id:
            self.update()
            return

        for robot in robots or []:
            if not isinstance(robot, dict):
                continue
            pose = robot.get("current_pose")
            if not isinstance(pose, dict):
                continue
            if str(pose.get("map_id") or "").strip() != selected_map_id:
                continue
            point = self.world_to_pixel(
                {
                    "x": pose.get("x"),
                    "y": pose.get("y"),
                }
            )
            if point is None:
                continue
            robot_id = _display(robot.get("robot_id") or robot.get("robot_name"))
            self.visible_robot_ids.append(robot_id)
            self.robot_markers.append(
                {
                    "robot_id": robot_id,
                    "pixel": point,
                    "yaw": _optional_float(pose.get("yaw"), default=0.0),
                    "connection_status": str(
                        robot.get("connection_status") or robot.get("status") or ""
                    ).upper(),
                }
            )
        self.update()

    def draw_overlay(self, painter, target):
        for marker in self.robot_markers:
            point = self.to_view_point(marker.get("pixel"), target)
            if point is None:
                continue

            status = marker.get("connection_status")
            fill = QColor("#16A34A" if status == "ONLINE" else "#F59E0B")
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.setBrush(fill)
            painter.drawEllipse(point, 9, 9)

            yaw = marker.get("yaw")
            if yaw is not None:
                heading = QPointF(
                    point.x() + math.cos(float(yaw)) * 20.0,
                    point.y() - math.sin(float(yaw)) * 20.0,
                )
                painter.setPen(QPen(fill.darker(120), 2))
                painter.drawLine(point, heading)

            painter.setPen(QPen(QColor("#111827"), 1))
            painter.drawText(point + QPointF(11, -11), marker.get("robot_id") or "-")


class KpiCard(QFrame):
    def __init__(self, title: str, hint: str):
        super().__init__()
        self.setObjectName("homeKpiCard")
        self.setProperty("tone", "neutral")

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self.accent = QFrame()
        self.accent.setObjectName("homeKpiAccent")
        self.accent.setProperty("tone", "neutral")
        self.accent.setFixedWidth(6)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("homeKpiTitle")

        self.value_label = QLabel("0")
        self.value_label.setObjectName("homeKpiValue")

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("homeKpiHint")
        self.hint_label.setWordWrap(True)

        content.addWidget(title_label)
        content.addWidget(self.value_label)
        content.addWidget(self.hint_label)

        root.addWidget(self.accent)
        root.addLayout(content, 1)

    def set_tone(self, tone: str):
        _set_style_property(self, "tone", tone)
        _set_style_property(self.accent, "tone", tone)


class RobotBoardCard(QFrame):
    def __init__(self, robot: dict):
        super().__init__()
        self.setObjectName("homeRobotCard")

        robot_id = _display(robot.get("robot_id") or robot.get("robot_name"))
        robot_type = _display(robot.get("robot_type") or robot.get("robot_type_name"))
        capabilities = _capabilities_text(robot.get("capabilities"))
        status = _display(robot.get("connection_status") or robot.get("status"))
        status_key = status.lower()
        self.setProperty("connection_status", status_key)
        location = _display(
            robot.get("current_location") or robot.get("zone"),
            "위치 미수신",
        )
        battery = robot.get("battery_percent", robot.get("battery"))
        current_task = _display(
            robot.get("current_task_id") or robot.get("current_task")
        )
        last_seen = _datetime(robot.get("last_seen_at"))
        chip_type = _display(robot.get("chip_type"), "blue")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        name = QLabel(robot_id)
        name.setObjectName("homeRobotTitle")
        chip = StatusChip(status, chip_type)

        top.addWidget(name)
        top.addStretch()
        top.addWidget(chip)

        rows = (
            ("구분", robot_type),
            ("지원 기능", capabilities),
            ("현재 작업", current_task),
            ("위치", location),
            ("배터리", _battery_text(battery)),
            ("마지막 수신", last_seen),
        )
        for row in rows:
            self._add_field_row(root, *row)

        root.insertLayout(0, top)

    @staticmethod
    def _add_field_row(layout, key: str, value: str):
        row = QHBoxLayout()
        row.setSpacing(8)

        key_label = QLabel(key)
        key_label.setObjectName("homeRobotFieldKey")
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setObjectName("homeRobotFieldValue")
        value_label.setWordWrap(True)

        row.addWidget(key_label, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(value_label, 1)
        layout.addLayout(row)


class FlowColumn(QFrame):
    cancel_requested = pyqtSignal(object)

    def __init__(
        self, column_key: str, title: str, tasks: list, *, canceling_task_id=None
    ):
        super().__init__()
        self.column_key = column_key
        self.setObjectName("card")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        self.task_count_label = QLabel(f"{len(tasks)}건")
        self.task_count_label.setObjectName("mutedText")

        root.addWidget(title_label)
        root.addWidget(self.task_count_label)

        if tasks:
            for task in tasks:
                task_card = self._build_task_card(
                    task, canceling_task_id=canceling_task_id
                )
                root.addWidget(task_card)
        else:
            empty = QLabel("현재 비어 있음")
            empty.setObjectName("mutedText")
            root.addWidget(empty)

        root.addStretch()

    def _build_task_card(self, task, *, canceling_task_id=None):
        task_card = QFrame()
        task_card.setObjectName("infoBox")
        tc = QVBoxLayout(task_card)
        tc.setContentsMargins(12, 12, 12, 12)
        tc.setSpacing(8)

        header = QHBoxLayout()
        title_label = QLabel(self._format_task_title(task))
        title_label.setObjectName("homeTaskTitle")
        status_chip = StatusChip(
            _task_status_label(task),
            _task_status_chip_type(task),
        )
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(status_chip)
        tc.addLayout(header)

        for key, value, kind in self._format_task_rows(task):
            row = QHBoxLayout()
            row.setSpacing(8)

            key_label = QLabel(key)
            key_label.setObjectName("homeTaskFieldKey")
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            value_label = QLabel(value)
            value_label.setObjectName(
                "homeTaskFieldDetail" if kind == "detail" else "homeTaskFieldValue"
            )
            value_label.setWordWrap(True)

            row.addWidget(key_label, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(value_label, 1)
            tc.addLayout(row)

        cancel_button = self._build_cancel_button(
            task, canceling_task_id=canceling_task_id
        )
        if cancel_button is not None:
            tc.addWidget(cancel_button)

        return task_card

    def _build_cancel_button(self, task, *, canceling_task_id=None):
        task_id = _task_id_value(task)
        if task_id is None:
            return None

        status = _effective_task_status(task)
        cancellable = task.get("cancellable")
        if cancellable is None:
            cancellable = status in CANCELABLE_TASK_STATUSES
        if not cancellable or status in CANCELING_TASK_STATUSES:
            return None

        button = QPushButton("작업 취소")
        button.setObjectName("dangerButton")
        button.setProperty("dashboard_cancel_task_id", task_id)

        if task_id == canceling_task_id:
            button.setText("취소 요청 중...")
            button.setEnabled(False)

        button.clicked.connect(
            lambda _checked=False, selected_task=dict(task): self.cancel_requested.emit(
                selected_task
            )
        )
        return button

    @staticmethod
    def _format_task_title(task):
        if not isinstance(task, dict):
            return "작업 -"

        task_id = _display(task.get("task_id"))
        task_type = _label_from(
            TASK_TYPE_LABELS,
            task.get("task_type") or task.get("scenario"),
        )
        return f"작업 #{task_id} · {task_type}"

    @staticmethod
    def _format_task_rows(task):
        if not isinstance(task, dict):
            return [("작업", str(task), "value")]

        robot_id = _display(
            task.get("assigned_robot_id") or task.get("robot_id"),
            "미배정",
        )
        status = _effective_task_status(task)
        phase = ""
        if status not in {"FAILED", "CANCELLED"}:
            phase = _label_from(TASK_PHASE_LABELS, task.get("phase"))
        destination = _display(task.get("destination_label"), "")
        feedback_summary = _display(task.get("feedback_summary"), "")
        reason_code = _reason_label(
            task.get("reason_code") or task.get("latest_reason_code"),
        )
        description, detail = _summary_and_detail(task.get("description"))

        rows = [("로봇", robot_id, "value")]
        if phase and phase != "-":
            rows.append(("단계", phase, "value"))
        if destination:
            rows.append(("목적지", destination, "value"))
        if feedback_summary:
            rows.append(("피드백", feedback_summary, "value"))
        if reason_code:
            rows.append(("사유", reason_code, "value"))
        if description:
            rows.append(("최근", description, "value"))
        if detail:
            rows.append(("상세", detail, "detail"))
        return rows


class CaregiverHomePage(QWidget):
    def __init__(
        self,
        *,
        autoload: bool = True,
        auto_system_status_poll: bool | None = None,
        system_status_poll_interval_ms: int = HOME_SYSTEM_STATUS_POLL_INTERVAL_MS,
    ):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.kpi_cards = {}
        self.robot_row = None
        self.timeline_table = None
        self.flow_list = None
        self.flow_count_label = None
        self.home_map_canvas = None
        self.home_map_status_label = None
        self.dashboard_thread = None
        self.dashboard_worker = None
        self.system_status_thread = None
        self.system_status_worker = None
        self.cancel_thread = None
        self.cancel_worker = None
        self._last_summary = {}
        self._last_robots = []
        self._last_flow_data = {}
        self._last_home_map_data = {}
        self._last_timeline_rows = []
        self._timeline_event_keys = set()
        self.home_map_profiles = []
        self.home_selected_map_id = None
        self._home_map_asset_cache = {}
        self._has_summary_snapshot = False
        self._canceling_task_id = None
        self.stream_refresh_scheduler = VisibleDeferredRefresh(
            owner=self,
            interval_ms=200,
            callback=lambda: self.load_dashboard_data(),
            is_busy=lambda: self.dashboard_thread is not None,
            single_shot=lambda delay, _callback: QTimer.singleShot(
                delay,
                self._run_stream_refresh,
            ),
        )
        self._auto_system_status_poll = (
            bool(autoload)
            if auto_system_status_poll is None
            else bool(auto_system_status_poll)
        )
        try:
            system_status_interval = int(system_status_poll_interval_ms)
        except (TypeError, ValueError):
            system_status_interval = HOME_SYSTEM_STATUS_POLL_INTERVAL_MS
        self.system_status_timer = QTimer(self)
        self.system_status_timer.setInterval(max(500, system_status_interval))
        self.system_status_timer.timeout.connect(self._poll_system_statuses)

        self._build_ui()
        if autoload:
            QTimer.singleShot(0, self.load_dashboard_data)
        if self._auto_system_status_poll:
            self.system_status_timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        top = QHBoxLayout()
        top.setSpacing(16)

        self.time_card = PageTimeCard(
            object_name="homeTimeCard",
            refresh_text="새로고침",
            refresh_property=("dashboard_action", "refresh"),
            on_refresh=self.load_dashboard_data,
        )
        self.refresh_button = self.time_card.refresh_button
        self.clock_label = self.time_card.clock_label
        self.date_label = self.time_card.date_label
        self.last_update_label = self.time_card.last_update_label
        self.load_status_label = self.time_card.status_label

        self.status_banner = QFrame()
        self.status_banner.setObjectName("dashboardStatusBanner")
        self.status_banner.setMaximumHeight(124)
        self.status_banner.setHidden(True)
        banner_layout = QVBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(12, 12, 12, 12)
        banner_layout.setSpacing(4)

        self.status_banner_title_label = QLabel("")
        self.status_banner_title_label.setObjectName("homeStatusBannerTitle")
        self.status_banner_summary_label = QLabel("")
        self.status_banner_summary_label.setObjectName("mutedText")
        self.status_banner_summary_label.setWordWrap(True)
        self.status_banner_detail_label = QLabel("")
        self.status_banner_detail_label.setObjectName("mutedText")
        self.status_banner_detail_label.setWordWrap(True)
        self.status_banner_detail_label.setHidden(True)

        banner_layout.addWidget(self.status_banner_title_label)
        banner_layout.addWidget(self.status_banner_summary_label)
        banner_layout.addWidget(self.status_banner_detail_label)

        self.header = PageHeader(
            "운영 대시보드",
            "현재 로봇 상태와 작업 흐름을 한눈에 확인합니다.",
            show_status=True,
        )

        top.addWidget(self.header, 1)
        top.addWidget(self.time_card)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)

        self._add_kpi_card(
            summary_row,
            "available_robots",
            "사용가능 로봇",
            "대기/준비 상태 로봇",
        )
        self._add_kpi_card(
            summary_row,
            "waiting_tasks",
            "대기 작업",
            "대기/준비 상태 작업",
        )
        self._add_kpi_card(
            summary_row,
            "running_tasks",
            "진행 중 작업",
            "배정/이동/수행 중 작업",
        )
        self._add_kpi_card(
            summary_row,
            "warning_errors",
            "경고/오류",
            "최근 24시간 운영 이벤트",
        )

        robot_board_wrap = QFrame()
        robot_board_wrap.setObjectName("card")
        rbw = QVBoxLayout(robot_board_wrap)
        rbw.setContentsMargins(20, 20, 20, 20)
        rbw.setSpacing(14)

        robot_title = QLabel("로봇 보드")
        robot_title.setObjectName("sectionTitle")

        self.robot_row = QHBoxLayout()
        self.robot_row.setSpacing(16)

        rbw.addWidget(robot_title)
        rbw.addLayout(self.robot_row)

        map_flow_row = QFrame()
        map_flow_row.setObjectName("homeMapFlowRow")
        map_flow_layout = QHBoxLayout(map_flow_row)
        map_flow_layout.setContentsMargins(0, 0, 0, 0)
        map_flow_layout.setSpacing(16)

        map_panel = QFrame()
        map_panel.setObjectName("homeOperationMapPanel")
        map_panel.setMinimumWidth(HOME_MAP_FLOW_PANEL_MIN_WIDTH)
        map_panel.setFixedHeight(HOME_MAP_FLOW_PANEL_HEIGHT)
        map_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mp = QVBoxLayout(map_panel)
        mp.setContentsMargins(20, 20, 20, 20)
        mp.setSpacing(12)

        map_title = QLabel("운영 맵")
        map_title.setObjectName("sectionTitle")

        self.home_map_canvas = HomeOperationMapCanvas()
        self.home_map_status_label = QLabel("맵을 불러오지 않았습니다.")
        self.home_map_status_label.setObjectName("mutedText")
        self.home_map_status_label.setWordWrap(True)

        mp.addWidget(map_title)
        mp.addWidget(self.home_map_canvas, 1)
        mp.addWidget(self.home_map_status_label)

        flow_wrap = QFrame()
        flow_wrap.setObjectName("homeTaskFlowPanel")
        flow_wrap.setMinimumWidth(HOME_MAP_FLOW_PANEL_MIN_WIDTH)
        flow_wrap.setFixedHeight(HOME_MAP_FLOW_PANEL_HEIGHT)
        flow_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fw = QVBoxLayout(flow_wrap)
        fw.setContentsMargins(20, 20, 20, 20)
        fw.setSpacing(14)

        flow_header = QHBoxLayout()
        flow_header.setSpacing(8)
        flow_title = QLabel("작업 흐름 보드")
        flow_title.setObjectName("sectionTitle")
        self.flow_count_label = QLabel("0건")
        self.flow_count_label.setObjectName("mutedText")
        flow_header.addWidget(flow_title)
        flow_header.addStretch()
        flow_header.addWidget(self.flow_count_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.flow_scroll = QScrollArea()
        self.flow_scroll.setObjectName("flowBoardScroll")
        self.flow_scroll.setWidgetResizable(True)
        self.flow_scroll.setMinimumHeight(260)
        self.flow_scroll.setMaximumHeight(HOME_FLOW_SCROLL_MAX_HEIGHT)

        flow_content = QWidget()
        flow_content.setObjectName("flowBoardContent")

        self.flow_list = QVBoxLayout(flow_content)
        self.flow_list.setContentsMargins(0, 0, 0, 0)
        self.flow_list.setSpacing(12)
        self.flow_scroll.setWidget(flow_content)

        fw.addLayout(flow_header)
        fw.addWidget(self.flow_scroll, 1)

        map_flow_layout.addWidget(map_panel, 1, Qt.AlignmentFlag.AlignTop)
        map_flow_layout.addWidget(flow_wrap, 1, Qt.AlignmentFlag.AlignTop)

        timeline_wrap = QFrame()
        timeline_wrap.setObjectName("card")
        tw = QVBoxLayout(timeline_wrap)
        tw.setContentsMargins(20, 20, 20, 20)
        tw.setSpacing(12)

        timeline_title = QLabel("최근 이벤트")
        timeline_title.setObjectName("sectionTitle")

        self.timeline_table = QTableWidget(0, 4)
        self.timeline_table.setHorizontalHeaderLabels(
            ["시간", "작업 ID", "이벤트", "상세"]
        )
        self.timeline_table.horizontalHeader().setStretchLastSection(True)

        tw.addWidget(timeline_title)
        tw.addWidget(self.timeline_table)

        root.addLayout(top)
        root.addWidget(self.status_banner)
        root.addLayout(summary_row)
        root.addWidget(map_flow_row)
        root.addWidget(robot_board_wrap)
        root.addWidget(timeline_wrap, 1)

    def _add_kpi_card(self, layout, key: str, title: str, hint: str):
        card = KpiCard(title, hint)
        self.kpi_cards[key] = card
        layout.addWidget(card)

    def load_dashboard_data(self):
        if self.dashboard_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self.load_status_label.setText("대시보드 데이터를 불러오는 중입니다.")
        self.load_status_label.setHidden(False)

        self.dashboard_thread, self.dashboard_worker = start_worker_thread(
            self,
            worker=DashboardLoadWorker(
                selected_map_id=self.home_selected_map_id,
                cached_map_assets_by_map_id=self._home_map_asset_cache,
            ),
            finished_handler=self._handle_dashboard_loaded,
            clear_handler=self._clear_dashboard_thread,
        )

    def _handle_dashboard_loaded(
        self,
        ok,
        summary,
        robots,
        flow_data,
        timeline_rows,
        system_statuses=None,
        map_data=None,
    ):
        self._set_system_statuses(system_statuses)
        if not ok:
            self.load_status_label.setText(f"대시보드 데이터 로드 실패: {summary}")
            self.load_status_label.setHidden(False)
            return

        self.apply_summary_data(summary, robots=robots)
        self.apply_robot_board_data(robots)
        self.apply_home_map_data(map_data, robots=robots)
        self.apply_flow_board_data(flow_data)
        self.apply_timeline_data(timeline_rows)
        self._mark_last_update()
        self.load_status_label.setHidden(True)

    def _set_system_statuses(self, statuses):
        status_strip = getattr(self.header, "status_strip", None)
        if status_strip is not None and statuses:
            status_strip.set_statuses(statuses)

    def _poll_system_statuses(self):
        if not self.isVisible():
            return
        self._refresh_system_statuses()

    def _refresh_system_statuses(self):
        if self.system_status_thread is not None:
            return

        self.system_status_thread, self.system_status_worker = start_worker_thread(
            self,
            worker=HomeSystemStatusWorker(),
            finished_handler=self._handle_system_status_loaded,
            clear_handler=self._clear_system_status_thread,
        )

    def _handle_system_status_loaded(self, statuses):
        self._set_system_statuses(statuses)

    def _clear_system_status_thread(self):
        self.system_status_thread = None
        self.system_status_worker = None

    def _clear_dashboard_thread(self):
        self.dashboard_thread = None
        self.dashboard_worker = None
        self.refresh_button.setEnabled(True)

    def apply_stream_event(self, event):
        event = event or {}
        event_type = str(event.get("event_type") or "").strip().upper()
        if event_type in {"PINKY_UPDATED", "ARM_UPDATED", "ACTION_FEEDBACK_UPDATED"}:
            payload = event.get("payload") if isinstance(event, dict) else {}
            if self.isVisible() and self._apply_robot_stream_event(
                event_type,
                payload if isinstance(payload, dict) else {},
            ):
                return
            self._schedule_stream_refresh()
            return

        if event_type == "TASK_UPDATED":
            payload = event.get("payload") if isinstance(event, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            if self.isVisible():
                self._apply_fall_alert_from_task_payload(payload)
                if self._apply_task_stream_event(payload):
                    return
            self._schedule_stream_refresh()
            return

        if event_type in {"ALERT_CREATED", "FALL_ALERT_CREATED"}:
            payload = event.get("payload") if isinstance(event, dict) else {}
            if self.isVisible() and self._apply_alert_stream_event(
                event_type,
                payload if isinstance(payload, dict) else {},
            ):
                return
            self._schedule_stream_refresh()

    def _apply_robot_stream_event(self, event_type: str, payload: dict) -> bool:
        patch = self._robot_patch_from_stream_event(event_type, payload)
        robot_id = str(patch.get("robot_id") or "").strip()
        if not robot_id or not self._last_robots:
            return False

        next_robots = []
        patched = False
        for robot in self._last_robots:
            robot_data = dict(robot) if isinstance(robot, dict) else {}
            current_id = str(
                robot_data.get("robot_id") or robot_data.get("robot_name") or ""
            ).strip()
            if current_id == robot_id:
                robot_data.update(patch)
                patched = True
            next_robots.append(robot_data)

        if not patched:
            return False

        self.apply_robot_board_data(next_robots)
        if self._last_home_map_data:
            self.apply_home_map_data(self._last_home_map_data, robots=next_robots)
        self._mark_last_update()
        return True

    def _robot_patch_from_stream_event(self, event_type: str, payload: dict) -> dict:
        if event_type == "PINKY_UPDATED":
            robot_id = payload.get("robot_id") or payload.get("pinky_id")
            robot_type = "MOBILE"
            state = payload.get("pinky_state") or payload.get("runtime_state")
        elif event_type == "ARM_UPDATED":
            robot_id = payload.get("robot_id") or payload.get("arm_id")
            robot_type = "ARM"
            state = payload.get("arm_state") or payload.get("runtime_state")
        else:
            robot_id = payload.get("robot_id") or robot_id_from_action_name(
                payload.get("action_name")
            )
            robot_type = "MOBILE"
            state = payload.get("patrol_status") or payload.get("runtime_state")

        patch = {
            "robot_id": robot_id,
            "robot_type": robot_type,
        }

        connection_status = str(payload.get("connection_status") or "").strip().upper()
        if connection_status:
            patch["connection_status"] = connection_status
            patch["chip_type"] = self._robot_chip_type(connection_status)
        elif state is not None:
            patch["status"] = str(state or "").upper()

        if state is not None:
            patch["runtime_state"] = str(state or "").upper()

        if "battery_percent" in payload:
            patch["battery_percent"] = payload.get("battery_percent")

        if "active_task_id" in payload:
            patch["current_task_id"] = payload.get("active_task_id")
        elif "current_task_id" in payload:
            patch["current_task_id"] = payload.get("current_task_id")
        elif "task_id" in payload:
            patch["current_task_id"] = payload.get("task_id")

        location = self._robot_location_from_stream_payload(payload)
        if location is not None:
            patch["current_location"] = location

        pose = self._robot_pose_from_stream_payload(payload)
        if pose is not None:
            patch["current_pose"] = pose

        last_seen_at = payload.get("last_seen_at")
        if last_seen_at is None and event_type == "ACTION_FEEDBACK_UPDATED":
            last_seen_at = payload.get("received_at")
        if last_seen_at is not None:
            patch["last_seen_at"] = last_seen_at

        if payload.get("fault_code") is not None:
            patch["fault_code"] = payload.get("fault_code")

        return patch

    @staticmethod
    def _robot_chip_type(connection_status: str) -> str:
        status = str(connection_status or "").strip().upper()
        if status == "ONLINE":
            return "green"
        if status in {"DEGRADED", "STALE", "UNKNOWN"}:
            return "amber"
        if status in {"OFFLINE", "ERROR", "FAULT"}:
            return "red"
        return "blue"

    @classmethod
    def _robot_location_from_stream_payload(cls, payload: dict) -> str | None:
        for key in ("current_location", "zone_name", "zone_id"):
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)

        if "current_pose" in payload or "pose" in payload:
            pose = payload.get("current_pose") or payload.get("pose")
            return cls._robot_location_from_pose(pose) or "위치 미수신"

        return None

    @staticmethod
    def _robot_location_from_pose(pose) -> str | None:
        if not isinstance(pose, dict):
            return None

        position = pose.get("position")
        if isinstance(position, dict):
            x_value = position.get("x")
            y_value = position.get("y")
        else:
            x_value = pose.get("x")
            y_value = pose.get("y")

        try:
            x = float(x_value)
            y = float(y_value)
        except (TypeError, ValueError):
            return None
        return f"좌표 x={x:.2f}, y={y:.2f}"

    def _robot_pose_from_stream_payload(self, payload: dict) -> dict | None:
        if "current_pose" not in payload and "pose" not in payload:
            return None
        return normalize_stream_pose(
            payload.get("current_pose") or payload.get("pose"),
            fallback_map_id=payload.get("map_id") or self.home_selected_map_id,
            updated_at=payload.get("received_at") or payload.get("last_seen_at"),
        )

    def _apply_task_stream_event(self, payload: dict) -> bool:
        patch = self._task_patch_from_stream_payload(payload)
        task_id = _task_id_value(patch)
        if task_id is None or not self._last_flow_data:
            return False

        normalized = self._normalize_flow_data(self._last_flow_data)
        next_tasks = []
        patched = False
        for task in self._iter_flow_tasks(normalized):
            task_data = dict(task) if isinstance(task, dict) else {}
            if _task_id_value(task_data) == task_id:
                task_data.update(patch)
                patched = True
            next_tasks.append(task_data)

        if not patched:
            if not self._task_patch_is_renderable(patch):
                return False
            next_tasks.append(dict(patch))

        next_flow_data = self._normalize_flow_data(next_tasks)
        self.apply_flow_board_data(next_flow_data)
        self._apply_task_flow_kpi_counts(next_flow_data)
        self._mark_last_update()
        return True

    @staticmethod
    def _task_patch_is_renderable(task: dict) -> bool:
        return _task_id_value(task) is not None and task.get("task_status") not in (
            None,
            "",
        )

    @staticmethod
    def _task_patch_from_stream_payload(payload: dict) -> dict:
        patch = {"task_id": payload.get("task_id")}

        for source_key, target_key in (
            ("task_type", "task_type"),
            ("task_status", "task_status"),
            ("phase", "phase"),
            ("assigned_robot_id", "assigned_robot_id"),
            ("robot_id", "robot_id"),
            ("latest_reason_code", "latest_reason_code"),
            ("reason_code", "latest_reason_code"),
            ("cancel_requested", "cancel_requested"),
            ("cancellable", "cancellable"),
            ("destination_label", "destination_label"),
            ("feedback_summary", "feedback_summary"),
        ):
            if source_key in payload:
                patch[target_key] = payload.get(source_key)

        description = payload.get("result_message")
        if description is None and "description" in payload:
            description = payload.get("description")
        if description not in (None, ""):
            patch["description"] = description

        if patch.get("task_status") is not None:
            patch["task_status"] = str(patch["task_status"] or "").upper()
        if patch.get("phase") is not None:
            patch["phase"] = str(patch["phase"] or "").upper()
        if patch.get("task_type") is not None:
            patch["task_type"] = str(patch["task_type"] or "").upper()

        return patch

    def _apply_task_flow_kpi_counts(self, flow_data):
        normalized = self._normalize_flow_data(flow_data)
        summary = dict(self._last_summary)
        summary["waiting_job_count"] = len(normalized["WAITING"])
        summary["running_job_count"] = len(normalized["ASSIGNED"]) + len(
            normalized["IN_PROGRESS"]
        )
        self.apply_summary_data(summary, robots=self._last_robots)

    def _apply_fall_alert_from_task_payload(self, payload: dict) -> bool:
        fall_alert = payload.get("fall_alert")
        if not isinstance(fall_alert, dict):
            return False

        alert_payload = dict(fall_alert)
        for source_key, target_key in (
            ("task_id", "task_id"),
            ("assigned_robot_id", "pinky_id"),
            ("robot_id", "pinky_id"),
            ("result_message", "message"),
            ("occurred_at", "occurred_at"),
        ):
            if alert_payload.get(target_key) in (None, "") and payload.get(
                source_key
            ) not in (None, ""):
                alert_payload[target_key] = payload.get(source_key)

        return self._apply_alert_stream_event("FALL_ALERT_CREATED", alert_payload)

    def _apply_alert_stream_event(self, event_type: str, payload: dict) -> bool:
        if not self._has_summary_snapshot:
            return False

        row = self._timeline_row_from_alert_event(event_type, payload)
        if row is None:
            return False

        event_key = self._timeline_event_key(row)
        if event_key in self._timeline_event_keys:
            return True

        self._increment_warning_error_count()
        self.apply_timeline_data([row, *self._last_timeline_rows])
        self._mark_last_update()
        return True

    @staticmethod
    def _timeline_row_from_alert_event(event_type: str, payload: dict) -> dict | None:
        task_id = payload.get("task_id")
        alert_id = payload.get("alert_id") or payload.get("event_id")
        if task_id in (None, "") and alert_id in (None, ""):
            return None

        message = (
            payload.get("message")
            or payload.get("result_message")
            or payload.get("detail")
            or payload.get("zone_name")
            or "낙상 알림 생성"
        )
        return {
            "event_id": alert_id,
            "alert_id": alert_id,
            "occurred_at": (
                payload.get("occurred_at")
                or payload.get("created_at")
                or payload.get("frame_ts")
                or payload.get("timestamp")
            ),
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
            "result_seq": payload.get("result_seq"),
            "frame_id": payload.get("frame_id"),
        }

    def _increment_warning_error_count(self):
        summary = dict(self._last_summary)
        try:
            current_count = int(summary.get("warning_error_count") or 0)
        except (TypeError, ValueError):
            current_count = 0
        summary["warning_error_count"] = current_count + 1
        self.apply_summary_data(summary, robots=self._last_robots)

    def _schedule_stream_refresh(self):
        self.stream_refresh_scheduler.schedule()

    def _run_stream_refresh(self):
        self.stream_refresh_scheduler.run()

    def showEvent(self, event):
        super().showEvent(event)
        self.stream_refresh_scheduler.handle_show()

    @property
    def _stream_refresh_pending(self):
        return self.stream_refresh_scheduler.pending

    @_stream_refresh_pending.setter
    def _stream_refresh_pending(self, value):
        self.stream_refresh_scheduler.pending = bool(value)

    @property
    def _deferred_stream_refresh(self):
        return self.stream_refresh_scheduler.deferred

    @_deferred_stream_refresh.setter
    def _deferred_stream_refresh(self, value):
        self.stream_refresh_scheduler.deferred = bool(value)

    def apply_summary_data(self, summary, *, robots=None):
        summary = summary or {}
        robots = robots or []
        self._last_summary = dict(summary) if isinstance(summary, dict) else {}
        self._has_summary_snapshot = True
        available_robot_count = int(summary.get("available_robot_count") or 0)
        total_robot_count = summary.get("total_robot_count")
        if total_robot_count is None:
            total_robot_count = len(robots)

        values = {
            "available_robots": f"{available_robot_count}/{int(total_robot_count or 0)}대",
            "waiting_tasks": f"{int(summary.get('waiting_job_count') or 0)}건",
            "running_tasks": f"{int(summary.get('running_job_count') or 0)}건",
            "warning_errors": f"{int(summary.get('warning_error_count') or 0)}건",
        }

        for key, value in values.items():
            self.kpi_cards[key].value_label.setText(value)

        self._apply_kpi_states(
            available_robot_count=available_robot_count,
            waiting_job_count=int(summary.get("waiting_job_count") or 0),
            running_job_count=int(summary.get("running_job_count") or 0),
            warning_error_count=int(summary.get("warning_error_count") or 0),
        )

    def _apply_kpi_states(
        self,
        *,
        available_robot_count,
        waiting_job_count,
        running_job_count,
        warning_error_count,
    ):
        states = {
            "available_robots": (
                "teal" if available_robot_count > 0 else "red",
                "운영 가능 로봇"
                if available_robot_count > 0
                else "운영 가능 로봇 없음",
            ),
            "waiting_tasks": (
                "amber" if waiting_job_count > 0 else "neutral",
                "배차 대기 필요" if waiting_job_count > 0 else "대기 중 작업 없음",
            ),
            "running_tasks": (
                "green" if running_job_count > 0 else "neutral",
                "로봇 수행 중" if running_job_count > 0 else "진행 중 작업 없음",
            ),
            "warning_errors": (
                "red" if warning_error_count > 0 else "neutral",
                "운영 확인 필요" if warning_error_count > 0 else "최근 오류 없음",
            ),
        }

        for key, (tone, hint) in states.items():
            card = self.kpi_cards[key]
            card.set_tone(tone)
            card.hint_label.setText(hint)

    def apply_robot_board_data(self, robots):
        robot_rows = [
            dict(robot) if isinstance(robot, dict) else {}
            for robot in (robots or [])
        ]
        self._last_robots = robot_rows
        self.clear_layout(self.robot_row)

        if not robot_rows:
            empty = QLabel("표시할 로봇 상태가 없습니다.")
            empty.setObjectName("mutedText")
            self.robot_row.addWidget(empty)
            return

        for robot in robot_rows:
            card = RobotBoardCard(robot)
            self.robot_row.addWidget(card)

    def apply_home_map_data(self, map_data, *, robots=None):
        map_data = map_data if isinstance(map_data, dict) else {}
        robots = [
            dict(robot) if isinstance(robot, dict) else {}
            for robot in (robots if robots is not None else self._last_robots)
        ]
        self._last_home_map_data = dict(map_data)

        if "map_profiles" in map_data:
            self.home_map_profiles = [
                profile
                for profile in map_data.get("map_profiles") or []
                if isinstance(profile, dict)
            ]

        selected_map_id = (
            str(map_data.get("selected_map_id") or "").strip()
            or self.home_selected_map_id
            or _selected_home_map_id(
                preferred_map_id=None,
                map_profiles=self.home_map_profiles,
                robots=robots,
            )
        )
        self.home_selected_map_id = selected_map_id or None
        self._remember_home_map_assets(map_data)

        assets = map_data.get("map_assets")
        assets = assets if isinstance(assets, dict) else {}
        if (
            not assets
            and selected_map_id
            and selected_map_id in self._home_map_asset_cache
        ):
            assets = dict(self._home_map_asset_cache[selected_map_id])

        asset_map_id = str(assets.get("map_id") or "").strip()
        if asset_map_id and asset_map_id == selected_map_id:
            self.home_map_canvas.load_map_from_assets(
                yaml_text=str(assets.get("yaml_text") or ""),
                pgm_bytes=assets.get("pgm_bytes") or b"",
                cache_key=(
                    asset_map_id,
                    assets.get("yaml_sha256"),
                    assets.get("pgm_sha256"),
                ),
            )
        else:
            self.home_map_canvas.clear_map("맵 asset 미수신")

        self.home_map_canvas.show_robots(robots, selected_map_id=selected_map_id)
        visible_count = len(self.home_map_canvas.visible_robot_ids)
        total_count = len(robots)
        error = str(map_data.get("map_asset_error") or "").strip()
        if error:
            self.home_map_status_label.setText(error)
        elif selected_map_id:
            self.home_map_status_label.setText(
                f"선택 맵 {selected_map_id} · 표시 {visible_count}대 / "
                f"전체 {total_count}대"
            )
        else:
            self.home_map_status_label.setText("선택 가능한 맵이 없습니다.")

    def _remember_home_map_assets(self, map_data):
        assets = map_data.get("map_assets") if isinstance(map_data, dict) else None
        if not isinstance(assets, dict):
            return
        map_id = str(assets.get("map_id") or "").strip()
        if map_id:
            self._home_map_asset_cache[map_id] = dict(assets)

    def apply_flow_board_data(self, flow_data):
        normalized = self._normalize_flow_data(flow_data)
        self._last_flow_data = {
            column_key: [dict(task) for task in tasks]
            for column_key, tasks in normalized.items()
        }
        compact_tasks = self._compact_flow_tasks(normalized)
        self.clear_layout(self.flow_list)
        self.flow_count_label.setText(f"{len(compact_tasks)}건")

        if not compact_tasks:
            empty = QLabel("표시할 작업이 없습니다.")
            empty.setObjectName("mutedText")
            self.flow_list.addWidget(empty)
            self.flow_list.addStretch()
            return

        for task in compact_tasks:
            self.flow_list.addWidget(self._build_compact_task_card(task))
        self.flow_list.addStretch()

    @staticmethod
    def _compact_flow_tasks(normalized):
        tasks = []
        for column_key in HOME_FLOW_RENDER_ORDER:
            tasks.extend(
                dict(task) if isinstance(task, dict) else {}
                for task in normalized.get(column_key, [])
            )
        return tasks

    def _build_compact_task_card(self, task):
        task_card = QFrame()
        task_card.setObjectName("infoBox")
        tc = QVBoxLayout(task_card)
        tc.setContentsMargins(12, 12, 12, 12)
        tc.setSpacing(8)

        header = QHBoxLayout()
        title_label = QLabel(FlowColumn._format_task_title(task))
        title_label.setObjectName("homeTaskTitle")
        title_label.setWordWrap(True)
        status_chip = StatusChip(
            _task_status_label(task),
            _task_status_chip_type(task),
        )
        header.addWidget(title_label, 1)
        header.addWidget(status_chip, 0, Qt.AlignmentFlag.AlignTop)
        tc.addLayout(header)

        for key, value, kind in FlowColumn._format_task_rows(task):
            row = QHBoxLayout()
            row.setSpacing(8)

            key_label = QLabel(key)
            key_label.setObjectName("homeTaskFieldKey")
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            value_label = QLabel(value)
            value_label.setObjectName(
                "homeTaskFieldDetail" if kind == "detail" else "homeTaskFieldValue"
            )
            value_label.setWordWrap(True)

            row.addWidget(key_label, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(value_label, 1)
            tc.addLayout(row)

        cancel_button = self._build_compact_cancel_button(task)
        if cancel_button is not None:
            tc.addWidget(cancel_button)

        return task_card

    def _build_compact_cancel_button(self, task):
        task_id = _task_id_value(task)
        if task_id is None:
            return None

        status = _effective_task_status(task)
        cancellable = task.get("cancellable")
        if cancellable is None:
            cancellable = status in CANCELABLE_TASK_STATUSES
        if not cancellable or status in CANCELING_TASK_STATUSES:
            return None

        button = QPushButton("작업 취소")
        button.setObjectName("dangerButton")
        button.setProperty("dashboard_cancel_task_id", task_id)

        if task_id == self._canceling_task_id:
            button.setText("취소 요청 중...")
            button.setEnabled(False)

        button.clicked.connect(
            lambda _checked=False, selected_task=dict(task): self._request_task_cancel(
                selected_task
            )
        )
        return button

    def apply_timeline_data(self, rows):
        rows = list(rows or [])[:20]
        self._last_timeline_rows = rows
        self._timeline_event_keys = {
            event_key
            for event_key in (self._timeline_event_key(row) for row in rows)
            if event_key is not None
        }
        self.timeline_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            values = self._timeline_values(row)
            for c, value in enumerate(values):
                self.timeline_table.setItem(r, c, QTableWidgetItem(str(value)))

    def _request_task_cancel(self, task):
        task = task if isinstance(task, dict) else {}
        task_id = _task_id_value(task)
        if task_id is None:
            self._show_status("취소할 작업 번호가 없습니다.")
            return
        if self.cancel_thread is not None:
            self._show_status("이전 취소 요청을 처리하는 중입니다.")
            return

        current_user = SessionManager.current_user()
        caregiver_id = getattr(current_user, "user_id", None)
        if not str(caregiver_id or "").strip().isdigit():
            self._show_status("취소 요청자 정보를 확인할 수 없습니다.")
            return

        self._canceling_task_id = task_id
        self.apply_flow_board_data(self._last_flow_data)
        self._show_status("취소 요청 전송 중...")

        payload = {
            "task_id": task_id,
            "caregiver_id": int(caregiver_id),
            "reason": "operator_cancel",
        }
        self.cancel_thread, self.cancel_worker = start_worker_thread(
            self,
            worker=DashboardTaskCancelWorker(payload),
            finished_handler=self._handle_task_cancel_finished,
            clear_handler=self._clear_cancel_thread,
        )

    def _handle_task_cancel_finished(self, success, response):
        response = normalize_ui_response(
            response,
            success=success,
            default_fields={"cancel_requested": False},
        )
        result_code = _display(response.get("result_code"))
        reason_code = _display(response.get("reason_code"))
        message = _display(response.get("result_message"))
        title, summary, detail = self._format_cancel_result(
            success=success,
            result_code=result_code,
            reason_code=reason_code,
            message=message,
        )

        self._canceling_task_id = None
        self._show_status_banner(title, summary, detail)
        self.apply_flow_board_data(self._last_flow_data)

        if success:
            self.load_dashboard_data()

    def _clear_cancel_thread(self):
        self.cancel_thread = None
        self.cancel_worker = None

    def _show_status(self, message: str):
        self.status_banner.setHidden(True)
        self.load_status_label.setText(message)
        self.load_status_label.setHidden(False)

    def _show_status_banner(self, title: str, summary: str, detail: str = ""):
        self.load_status_label.setHidden(True)
        self.status_banner_title_label.setText(title)
        self.status_banner_summary_label.setText(summary)
        self.status_banner_detail_label.setText(f"상세: {detail}" if detail else "")
        self.status_banner_detail_label.setHidden(not bool(detail))
        self.status_banner.setHidden(False)

    @staticmethod
    def _format_cancel_result(*, success, result_code, reason_code, message):
        summary, detail = _summary_and_detail(message)
        if success:
            title = "취소 요청 접수"
            if not summary:
                summary = "작업 취소 요청이 접수되었습니다."
            return title, summary, detail

        reason = _reason_label(reason_code) or _reason_label(result_code)
        if not summary:
            summary = reason or "작업 취소 요청을 처리하지 못했습니다."
        return "작업 취소 실패", summary, detail

    def _mark_last_update(self):
        self.time_card.mark_updated()

    def shutdown(self):
        self.system_status_timer.stop()
        stop_worker_thread(
            self.dashboard_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_dashboard_thread,
        )
        stop_worker_thread(
            self.system_status_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_system_status_thread,
        )
        stop_worker_thread(
            self.cancel_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_cancel_thread,
        )

    @classmethod
    def _normalize_flow_data(cls, flow_data):
        normalized = {column_key: [] for column_key, _title, _statuses in FLOW_COLUMNS}
        seen = set()

        for task in cls._iter_flow_tasks(flow_data):
            task_id = _task_id_value(task)
            seen_key = (
                task_id,
                _status_of(task),
                task.get("event_id"),
            )
            if task_id is not None and seen_key in seen:
                continue
            if task_id is not None:
                seen.add(seen_key)

            normalized[cls._flow_column_key_for(task)].append(task)

        return normalized

    @staticmethod
    def _iter_flow_tasks(flow_data) -> Iterable[dict]:
        if isinstance(flow_data, dict):
            sources = flow_data.values()
        elif isinstance(flow_data, list):
            sources = [flow_data]
        else:
            sources = []

        for tasks in sources:
            if not isinstance(tasks, list):
                continue
            for task in tasks:
                if isinstance(task, dict):
                    yield task

    @staticmethod
    def _flow_column_key_for(task):
        status = _effective_task_status(task)
        for column_key, _title, statuses in FLOW_COLUMNS:
            if status in statuses:
                return column_key
        return "DONE"

    @staticmethod
    def _timeline_values(row):
        if isinstance(row, dict):
            return [
                _datetime(row.get("occurred_at") or row.get("timeline_time")),
                _display(row.get("task_id") or row.get("work_id")),
                _display(row.get("event_type") or row.get("event_name")),
                _display(row.get("message") or row.get("detail")),
            ]

        values = list(row or [])
        return (values + ["", "", "", ""])[:4]

    @staticmethod
    def _timeline_event_key(row):
        if isinstance(row, dict):
            event_id = row.get("event_id") or row.get("alert_id")
            if event_id not in (None, ""):
                return ("id", str(event_id))
            return (
                "row",
                str(row.get("event_type") or row.get("event_name") or ""),
                str(row.get("task_id") or row.get("work_id") or ""),
                str(row.get("result_seq") or ""),
                str(row.get("frame_id") or ""),
                str(row.get("occurred_at") or row.get("timeline_time") or ""),
                str(row.get("message") or row.get("detail") or ""),
            )

        values = list(row or [])
        if not values:
            return None
        return ("list", *tuple(str(value) for value in values[:4]))

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                CaregiverHomePage.clear_layout(child_layout)


__all__ = [
    "CaregiverHomePage",
    "DashboardLoadWorker",
    "DashboardTaskCancelWorker",
    "FlowColumn",
    "HomeOperationMapCanvas",
    "HomeSystemStatusWorker",
    "RobotBoardCard",
    "StatusChip",
]
