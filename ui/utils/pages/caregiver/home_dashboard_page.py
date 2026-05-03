from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from server.ropi_main_service.transport.tcp_protocol import MESSAGE_CODE_HEARTBEAT
from ui.utils.core.responses import normalize_ui_response
from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.tcp_client import send_request
from ui.utils.network.service_clients import (
    CaregiverRemoteService,
    TaskMonitorRemoteService,
)
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_common import (
    StatusChip,
    display_text as _display,
    operator_datetime_text as _datetime,
)
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard


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
}

ROS_ERROR_MARKERS = (
    "ROS service command failed",
    "No such file or directory",
    "Connection refused",
    "ROPI_ROS_SERVICE_SOCKET",
)

def _status_of(task: dict) -> str:
    return _display(task.get("task_status"), "UNKNOWN").upper()


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
    return _label_from(TASK_STATUS_LABELS, value)


def _task_status_chip_type(value):
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
    finished = pyqtSignal(object, object, object, object, object, object)

    def run(self):
        system_statuses = self._load_system_statuses()
        try:
            bundle = CaregiverRemoteService().get_dashboard_bundle() or {}
            summary = bundle.get("summary", {})
            robots = bundle.get("robots", [])
            flow_data = bundle.get("flow_data", {})
            timeline_rows = bundle.get("timeline_rows", [])
            self.finished.emit(
                True,
                summary,
                robots,
                flow_data,
                timeline_rows,
                system_statuses,
            )
        except Exception as exc:
            self.finished.emit(False, str(exc), [], {}, [], system_statuses)

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
        display_name = _display(robot.get("display_name"), robot_id)
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
        name = QLabel(f"{display_name} · {robot_id}")
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
            ("배터리", _display(battery, "배터리 미수신")),
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

    def __init__(self, column_key: str, title: str, tasks: list, *, canceling_task_id=None):
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
                task_card = self._build_task_card(task, canceling_task_id=canceling_task_id)
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
            _task_status_label(task.get("task_status")),
            _task_status_chip_type(task.get("task_status")),
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

        cancel_button = self._build_cancel_button(task, canceling_task_id=canceling_task_id)
        if cancel_button is not None:
            tc.addWidget(cancel_button)

        return task_card

    def _build_cancel_button(self, task, *, canceling_task_id=None):
        task_id = _task_id_value(task)
        if task_id is None:
            return None

        status = _status_of(task)
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
        phase = _label_from(TASK_PHASE_LABELS, task.get("phase"))
        destination = _display(task.get("destination_label"), "")
        feedback_summary = _display(task.get("feedback_summary"), "")
        reason_code = _reason_label(
            task.get("reason_code") or task.get("latest_reason_code"),
        )
        description, detail = _summary_and_detail(task.get("description"))

        rows = [("로봇", robot_id, "value")]
        if phase != "-":
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
    def __init__(self, *, autoload: bool = True):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.kpi_cards = {}
        self.robot_row = None
        self.timeline_table = None
        self.flow_grid = None
        self.dashboard_thread = None
        self.dashboard_worker = None
        self.cancel_thread = None
        self.cancel_worker = None
        self._last_flow_data = {}
        self._canceling_task_id = None

        self._build_ui()
        if autoload:
            QTimer.singleShot(0, self.load_dashboard_data)

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

        flow_wrap = QFrame()
        flow_wrap.setObjectName("card")
        fw = QVBoxLayout(flow_wrap)
        fw.setContentsMargins(20, 20, 20, 20)
        fw.setSpacing(14)

        flow_title = QLabel("작업 흐름 보드")
        flow_title.setObjectName("sectionTitle")

        flow_sub = QLabel("현재 요청된 작업을 상태별로 분류해 보여줍니다.")
        flow_sub.setObjectName("mutedText")

        self.flow_scroll = QScrollArea()
        self.flow_scroll.setObjectName("flowBoardScroll")
        self.flow_scroll.setWidgetResizable(True)
        self.flow_scroll.setMinimumHeight(260)
        self.flow_scroll.setMaximumHeight(420)

        flow_content = QWidget()
        flow_content.setObjectName("flowBoardContent")

        self.flow_grid = QGridLayout(flow_content)
        self.flow_grid.setHorizontalSpacing(16)
        self.flow_grid.setVerticalSpacing(16)
        self.flow_scroll.setWidget(flow_content)

        fw.addWidget(flow_title)
        fw.addWidget(flow_sub)
        fw.addWidget(self.flow_scroll)

        timeline_wrap = QFrame()
        timeline_wrap.setObjectName("card")
        tw = QVBoxLayout(timeline_wrap)
        tw.setContentsMargins(20, 20, 20, 20)
        tw.setSpacing(12)

        timeline_title = QLabel("최근 이벤트")
        timeline_title.setObjectName("sectionTitle")

        self.timeline_table = QTableWidget(0, 4)
        self.timeline_table.setHorizontalHeaderLabels(["시간", "작업 ID", "이벤트", "상세"])
        self.timeline_table.horizontalHeader().setStretchLastSection(True)

        tw.addWidget(timeline_title)
        tw.addWidget(self.timeline_table)

        root.addLayout(top)
        root.addWidget(self.status_banner)
        root.addLayout(summary_row)
        root.addWidget(robot_board_wrap)
        root.addWidget(flow_wrap)
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
            worker=DashboardLoadWorker(),
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
    ):
        self._set_system_statuses(system_statuses)
        if not ok:
            self.load_status_label.setText(f"대시보드 데이터 로드 실패: {summary}")
            self.load_status_label.setHidden(False)
            return

        self.apply_summary_data(summary, robots=robots)
        self.apply_robot_board_data(robots)
        self.apply_flow_board_data(flow_data)
        self.apply_timeline_data(timeline_rows)
        self._mark_last_update()
        self.load_status_label.setHidden(True)

    def _set_system_statuses(self, statuses):
        status_strip = getattr(self.header, "status_strip", None)
        if status_strip is not None and statuses:
            status_strip.set_statuses(statuses)

    def _clear_dashboard_thread(self):
        self.dashboard_thread = None
        self.dashboard_worker = None
        self.refresh_button.setEnabled(True)

    def apply_summary_data(self, summary, *, robots=None):
        summary = summary or {}
        robots = robots or []
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
                "운영 가능 로봇" if available_robot_count > 0 else "운영 가능 로봇 없음",
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
        self.clear_layout(self.robot_row)

        if not robots:
            empty = QLabel("표시할 로봇 상태가 없습니다.")
            empty.setObjectName("mutedText")
            self.robot_row.addWidget(empty)
            return

        for robot in robots:
            card = RobotBoardCard(robot if isinstance(robot, dict) else {})
            self.robot_row.addWidget(card)

    def apply_flow_board_data(self, flow_data):
        self._last_flow_data = flow_data or {}
        normalized = self._normalize_flow_data(flow_data)
        self.clear_layout(self.flow_grid)

        for index, (column_key, title, _statuses) in enumerate(FLOW_COLUMNS):
            column = FlowColumn(
                column_key,
                title,
                normalized[column_key],
                canceling_task_id=self._canceling_task_id,
            )
            column.cancel_requested.connect(self._request_task_cancel)
            self.flow_grid.addWidget(column, 0, index)

    def apply_timeline_data(self, rows):
        rows = list(rows or [])[:20]
        self.timeline_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            values = self._timeline_values(row)
            for c, value in enumerate(values):
                self.timeline_table.setItem(r, c, QTableWidgetItem(str(value)))

    def _request_task_cancel(self, task):
        task = task if isinstance(task, dict) else {}
        task_id = _task_id_value(task)
        if task_id is None:
            self._show_status("취소할 task_id가 없습니다.")
            return
        if self.cancel_thread is not None:
            self._show_status("이전 취소 요청을 처리하는 중입니다.")
            return

        current_user = SessionManager.current_user()
        caregiver_id = getattr(current_user, "user_id", None)
        if not str(caregiver_id or "").strip().isdigit():
            self._show_status("취소 요청자 caregiver_id가 없습니다.")
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
        stop_worker_thread(
            self.dashboard_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_dashboard_thread,
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
        status = _status_of(task)
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
    "RobotBoardCard",
    "StatusChip",
]
