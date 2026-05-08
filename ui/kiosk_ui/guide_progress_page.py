from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.kiosk_ui.guide_progress_state import (
    POST_START_GUIDE_PHASES,
    build_guide_progress_view_state,
    guide_warning_message_for_reason,
)
from ui.utils.network.service_clients import VisitGuideRemoteService


class KioskProgressStage(QFrame):
    def __init__(self, *, title_text, active=False, completed=False):
        super().__init__()
        self.setObjectName("kioskProgressStage")
        self._state = "pending"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.badge = QLabel()
        self.badge.setObjectName("kioskProgressStageBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(72, 72)

        self.title = QLabel(title_text)
        self.title.setObjectName("kioskProgressStageTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)

        layout.addWidget(self.badge)
        layout.addWidget(self.title)
        if active:
            self.set_state("active")
        elif completed:
            self.set_state("done")
        else:
            self.set_state("pending")

    def set_state(self, state):
        normalized = str(state or "pending").strip() or "pending"
        if normalized not in {"pending", "active", "done"}:
            normalized = "pending"
        self._state = normalized
        self.setProperty("state", normalized)
        self.badge.setProperty("state", normalized)
        self.title.setProperty("state", normalized)
        self.badge.setText("●" if normalized in {"active", "done"} else "○")
        for widget in (self, self.badge, self.title):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class KioskRobotGuidanceProgressPage(QWidget):
    def __init__(self, *, go_home_page=None, go_call_staff_page=None):
        super().__init__()
        self.setObjectName("kioskProgressPage")
        self.go_home_page = go_home_page
        self.go_call_staff_page = go_call_staff_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None
        self.current_session = None
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(3000)
        self.status_timer.timeout.connect(self.refresh_progress_status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("kioskProgressTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(56, 24, 56, 24)
        top_layout.setSpacing(16)

        brand = QLabel("ROPI 안내 로봇")
        brand.setObjectName("kioskProgressBrand")

        self.help_button = QPushButton("도움")
        self.help_button.setObjectName("kioskRoundIconButton")
        self.help_button.setMinimumSize(72, 72)

        self.info_button = QPushButton("안내")
        self.info_button.setObjectName("kioskRoundIconButton")
        self.info_button.setMinimumSize(72, 72)

        top_layout.addWidget(brand)
        top_layout.addStretch()
        top_layout.addWidget(self.help_button)
        top_layout.addWidget(self.info_button)

        content = QVBoxLayout()
        content.setContentsMargins(56, 44, 56, 0)
        content.setSpacing(28)

        header_wrap = QVBoxLayout()
        header_wrap.setSpacing(10)
        header_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_title_label = QLabel("안내를 준비하고 있습니다")
        self.progress_title_label.setObjectName("kioskProgressTitle")
        self.progress_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_subtitle_label = QLabel("로봇과 안내 대상을 확인하는 중입니다.")
        self.progress_subtitle_label.setObjectName("kioskProgressSubtitle")
        self.progress_subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_wrap.addWidget(self.progress_title_label)
        header_wrap.addWidget(self.progress_subtitle_label)

        progress_card = QFrame()
        progress_card.setObjectName("kioskProgressCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(28, 28, 28, 28)
        progress_layout.setSpacing(18)

        line_wrap = QFrame()
        line_wrap.setObjectName("kioskProgressLineWrap")
        line_layout = QHBoxLayout(line_wrap)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_layout.setSpacing(8)

        self.progress_stages = [
            KioskProgressStage(title_text="요청 접수", completed=True),
            KioskProgressStage(title_text="로봇 이동", completed=True),
            KioskProgressStage(title_text="안내자 확인", active=True),
            KioskProgressStage(title_text="안내 시작"),
            KioskProgressStage(title_text="인계 완료", completed=False),
        ]
        for stage in self.progress_stages:
            line_layout.addWidget(stage, 1)

        progress_layout.addWidget(line_wrap)

        robot_card = QFrame()
        robot_card.setObjectName("kioskRobotInfoCard")
        robot_layout = QHBoxLayout(robot_card)
        robot_layout.setContentsMargins(28, 28, 28, 28)
        robot_layout.setSpacing(22)

        robot_icon = QLabel("R")
        robot_icon.setObjectName("kioskRobotInfoIcon")
        robot_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        robot_icon.setFixedSize(124, 124)

        robot_text_wrap = QVBoxLayout()
        robot_text_wrap.setSpacing(14)

        top_text_row = QHBoxLayout()
        top_text_row.setSpacing(14)

        self.robot_name_label = QLabel("ROPI-01")
        self.robot_name_label.setObjectName("kioskRobotInfoTitle")

        self.robot_state_chip = QLabel("이동 중")
        self.robot_state_chip.setObjectName("kioskRobotStateChip")

        top_text_row.addWidget(self.robot_name_label)
        top_text_row.addWidget(self.robot_state_chip)
        top_text_row.addStretch()

        self.progress_bar_track = QFrame()
        self.progress_bar_track.setObjectName("kioskRobotProgressTrack")
        progress_bar_layout = QVBoxLayout(self.progress_bar_track)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        self.progress_bar_fill = QFrame()
        self.progress_bar_fill.setObjectName("kioskRobotProgressFill")
        self.progress_bar_fill.setFixedWidth(420)
        self.progress_bar_fill.setMinimumHeight(14)
        self.progress_bar_fill.setMaximumHeight(14)

        progress_bar_layout.addWidget(self.progress_bar_fill)

        self.distance_label = QLabel("안내 상태를 확인하고 있습니다.")
        self.distance_label.setObjectName("kioskRobotDistanceText")

        robot_text_wrap.addLayout(top_text_row)
        robot_text_wrap.addWidget(self.progress_bar_track)
        robot_text_wrap.addWidget(self.distance_label)

        robot_layout.addWidget(robot_icon)
        robot_layout.addLayout(robot_text_wrap, 1)

        safety_notice = QFrame()
        safety_notice.setObjectName("kioskSafetyNotice")
        safety_layout = QHBoxLayout(safety_notice)
        safety_layout.setContentsMargins(24, 24, 24, 24)
        safety_layout.setSpacing(18)

        safety_icon = QLabel("↔")
        safety_icon.setObjectName("kioskSafetyNoticeIcon")
        safety_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        safety_icon.setFixedWidth(50)

        safety_text = QLabel("로봇과 적정한 거리를 유지하며 따라와 주세요.")
        safety_text.setObjectName("kioskSafetyNoticeText")
        safety_text.setWordWrap(True)

        safety_layout.addWidget(safety_icon)
        safety_layout.addWidget(safety_text, 1)

        self.request_id_label = QLabel("요청번호: -")
        self.request_id_label.setObjectName("kioskProgressRequestId")
        self.request_id_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        content.addLayout(header_wrap)
        content.addWidget(progress_card)
        content.addWidget(robot_card)
        content.addWidget(safety_notice)
        content.addWidget(self.request_id_label)
        content.addStretch()

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskConfirmationBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(56, 20, 56, 20)
        bottom_layout.setSpacing(24)

        self.call_staff_button = QPushButton("직원 호출")
        self.call_staff_button.setObjectName("kioskProgressPrimaryButton")
        self.call_staff_button.setMinimumHeight(72)

        self.start_driving_button = QPushButton("안내 주행 시작")
        self.start_driving_button.setObjectName("kioskProgressPrimaryButton")
        self.start_driving_button.setMinimumHeight(72)
        self.start_driving_button.setEnabled(False)
        self.start_driving_button.clicked.connect(self.start_guidance_driving)

        self.cancel_button = QPushButton("안내 취소")
        self.cancel_button.setObjectName("kioskProgressSecondaryButton")
        self.cancel_button.setMinimumHeight(72)
        self.cancel_button.clicked.connect(self.finish_guidance)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.call_staff_button, 1)
        bottom_layout.addWidget(self.start_driving_button, 1)
        bottom_layout.addWidget(self.cancel_button, 1)
        bottom_layout.addStretch()

        root.addWidget(top_bar)
        root.addLayout(content, 1)
        root.addWidget(bottom_bar)

    def set_patient(self, patient, session=None):
        self.selected_patient = patient or None
        self.current_session = session or None
        self.detected_target_track_id = self._normalize_target_track_id(
            self._session_target_track_id()
        )
        self.start_driving_button.setEnabled(False)
        task_id = str((self.current_session or {}).get("task_id", "-")).strip() or "-"
        if self.selected_patient:
            name = str(self.selected_patient.get("name", "-")).strip() or "-"
            room = str(self.selected_patient.get("room", "-")).strip() or "-"
            self.request_id_label.setText(
                f"안내 대상: {name} 어르신 / 목적지: {room} / task_id: {task_id}"
            )
        else:
            self.request_id_label.setText("안내 대상: -")

        self._apply_session_status()
        self.refresh_progress_status()
        self._set_status_polling_enabled(bool(task_id and task_id != "-"))

    def refresh_progress_status(self):
        task_applied = self.refresh_task_status()
        if not self.current_session:
            return task_applied
        if self._is_terminal_task_status((self.current_session or {}).get("task_status")):
            return task_applied
        self.refresh_runtime_status()
        return task_applied

    def refresh_task_status(self):
        task_id = str((self.current_session or {}).get("task_id", "")).strip()
        if not task_id:
            return False

        get_task_status = getattr(self.service, "get_task_status", None)
        if get_task_status is None:
            return False

        try:
            status = get_task_status(task_id=task_id)
        except Exception:
            return False

        return self._apply_task_status_payload(status or {})

    def _apply_task_status_payload(self, payload):
        result_code = str((payload or {}).get("result_code") or "").strip().upper()
        if result_code and result_code != "ACCEPTED":
            message = str((payload or {}).get("result_message") or "").strip()
            if message:
                self.distance_label.setText(message)
            return False

        phase = str((payload or {}).get("phase") or "").strip()
        task_status = str((payload or {}).get("task_status") or "").strip()
        if not phase and not task_status:
            return False

        self.current_session = {
            **(self.current_session or {}),
            "task_status": task_status or (self.current_session or {}).get("task_status"),
            "phase": phase or (self.current_session or {}).get("phase"),
            "task_outcome": (payload or {}).get("task_outcome"),
            "reason_code": (payload or {}).get("reason_code"),
            "latest_reason_code": (payload or {}).get("latest_reason_code"),
            "result_message": (payload or {}).get("result_message"),
            "assigned_robot_id": (
                (payload or {}).get("assigned_robot_id")
                or (self.current_session or {}).get("assigned_robot_id")
            ),
        }
        self._update_guide_progress_display(phase, task_status)
        self._apply_latest_result_warning()
        if self._is_post_start_guide_phase(phase):
            self._complete_guide_handoff(
                message="안내를 시작했습니다. 로봇을 따라 이동해주세요.",
                phase=phase,
                task_status=task_status,
            )
            return True
        if self._is_terminal_task_status(task_status):
            self._set_status_polling_enabled(False)
        return True

    def refresh_runtime_status(self):
        pinky_id = str((self.current_session or {}).get("pinky_id", "pinky1")).strip() or "pinky1"
        try:
            ok, message, status = self.service.get_guide_runtime_status(pinky_id=pinky_id)
        except Exception:
            return

        guide_runtime = (status or {}).get("guide_runtime") or {}
        last_update = guide_runtime.get("last_update") or {}
        self._apply_guide_runtime_payload(ok, last_update)

    def _apply_guide_runtime_payload(self, ok, payload):
        if (payload or {}).get("guide_phase"):
            return self._apply_guide_phase_payload(ok, payload)
        return False

    def _apply_guide_phase_payload(self, ok, payload):
        guide_phase = str((payload or {}).get("guide_phase") or "").strip().upper()
        if not ok and not guide_phase:
            return False

        target_track_id = self._normalize_target_track_id(
            (payload or {}).get("target_track_id")
        )
        phase = guide_phase or self._current_session_phase()
        task_status = str(
            (payload or {}).get("task_status")
            or (self.current_session or {}).get("task_status")
            or "RUNNING"
        ).strip().upper()

        self.current_session = {
            **(self.current_session or {}),
            "phase": phase,
            "guide_phase": phase,
            "task_status": task_status,
        }
        if target_track_id is not None:
            self.current_session["target_track_id"] = target_track_id
            self.detected_target_track_id = target_track_id

        self._update_guide_progress_display(phase, task_status)
        if self._is_post_start_guide_phase(phase):
            self._complete_guide_handoff(
                message="안내를 시작했습니다. 로봇을 따라 이동해주세요.",
                phase=phase,
                task_status=task_status,
            )
            return bool(guide_phase)
        if phase == "READY_TO_START_GUIDANCE" and target_track_id is not None:
            self.start_driving_button.setEnabled(True)
        elif phase in {
            "WAIT_TARGET_TRACKING",
            "GUIDANCE_RUNNING",
            "WAIT_REIDENTIFY",
            "GUIDANCE_FINISHED",
            "GUIDANCE_CANCELLED",
            "GUIDANCE_FAILED",
        }:
            self.start_driving_button.setEnabled(False)

        seq = (payload or {}).get("seq")
        if seq is not None and self.selected_patient:
            self.request_id_label.setText(
                f"안내 대상: {self.selected_patient.get('name', '-')} / phase 순번: {seq}"
            )
        warning_message = self._latest_result_warning_message()
        if warning_message:
            self.distance_label.setText(warning_message)
        return bool(guide_phase)

    def start_guidance_driving(self):
        task_id = str((self.current_session or {}).get("task_id", "")).strip()
        if not task_id:
            self.distance_label.setText("안내 주행 시작에 필요한 task_id가 없습니다.")
            return

        target_track_id = self._normalize_target_track_id(
            self.detected_target_track_id
            if self.detected_target_track_id is not None
            else self._session_target_track_id()
        )
        if target_track_id is None:
            self.distance_label.setText("안내 대상 확인 후 주행을 시작할 수 있습니다.")
            self.start_driving_button.setEnabled(False)
            return

        pinky_id = str((self.current_session or {}).get("pinky_id", "pinky1")).strip() or "pinky1"
        try:
            success, message, response = self.service.start_guide_driving(
                task_id=task_id,
                pinky_id=pinky_id,
                target_track_id=target_track_id,
            )
        except Exception as exc:
            self.distance_label.setText(f"안내 주행 시작 중 오류가 발생했습니다: {exc}")
            return

        if not success:
            failure_response = response or {}
            self.current_session = {
                **(self.current_session or {}),
                "command_response": failure_response,
                "task_outcome": failure_response.get("result_code") or "REJECTED",
                "reason_code": failure_response.get("reason_code"),
                "latest_reason_code": failure_response.get("reason_code"),
                "result_message": failure_response.get("result_message") or message,
            }
            self.distance_label.setText(message or "안내 주행 시작이 거부되었습니다.")
            return

        self.current_session = {
            **(self.current_session or {}),
            "target_track_id": target_track_id,
            "command_response": response or {},
            "task_outcome": None,
            "reason_code": None,
            "latest_reason_code": None,
            "result_message": None,
        }
        self.start_driving_button.setEnabled(False)
        self._complete_guide_handoff(
            message=message or "안내 주행을 시작했습니다.",
            phase=str((response or {}).get("phase") or "GUIDANCE_RUNNING").strip(),
            task_status=str((response or {}).get("task_status") or "RUNNING").strip(),
        )

    def _apply_session_status(self):
        session = self.current_session or {}
        command_response = session.get("command_response") or {}
        phase = str(
            command_response.get("phase")
            or command_response.get("guide_phase")
            or session.get("phase")
            or session.get("guide_phase")
            or ""
        ).strip()
        task_status = str(
            command_response.get("task_status")
            or session.get("task_status")
            or ""
        ).strip()
        if not phase and not task_status:
            return

        self._update_guide_progress_display(phase, task_status)
        self._apply_command_warning()
        self._apply_latest_result_warning()

        if self.selected_patient:
            name = str(self.selected_patient.get("name", "-")).strip() or "-"
            room = str(self.selected_patient.get("room", "-")).strip() or "-"
            task_id = str(session.get("task_id", "-")).strip() or "-"
            phase_label = self._guide_phase_label(phase, task_status)
            self.request_id_label.setText(
                f"안내 대상: {name} 어르신 / 목적지: {room} / task_id: {task_id} / 상태: {phase_label}"
            )

    def _apply_command_warning(self):
        session = self.current_session or {}
        if session.get("command_result_code") != "COMMAND_FAILED":
            return

        message = str(session.get("command_message") or "").strip()
        self.distance_label.setText(
            message or "로봇 호출 명령을 보낼 수 없습니다. 직원에게 문의해 주세요."
        )
        self.start_driving_button.setEnabled(False)

    def _apply_latest_result_warning(self):
        message = self._latest_result_warning_message()
        if not message:
            return False
        self.distance_label.setText(message)
        return True

    def _latest_result_warning_message(self):
        session = self.current_session or {}
        command_response = session.get("command_response") or {}
        phase = self._current_session_phase()
        task_status = str(session.get("task_status") or "").strip().upper()
        if self._is_terminal_task_status(task_status) or phase == "GUIDANCE_RUNNING":
            return ""
        if phase and phase not in {
            "WAIT_GUIDE_START_CONFIRM",
            "WAIT_TARGET_TRACKING",
            "READY_TO_START_GUIDANCE",
            "WAIT_REIDENTIFY",
        }:
            return ""

        outcome = str(
            session.get("task_outcome")
            or command_response.get("result_code")
            or ""
        ).strip().upper()
        reason_code = str(
            session.get("latest_reason_code")
            or session.get("reason_code")
            or command_response.get("reason_code")
            or ""
        ).strip().upper()
        if outcome not in {"REJECTED", "FAILED", "INVALID_REQUEST", "ERROR"} and not reason_code:
            return ""

        message = str(
            session.get("result_message")
            or command_response.get("result_message")
            or ""
        ).strip()
        if message:
            return message

        return self._guide_warning_message_for_reason(reason_code)

    @staticmethod
    def _guide_warning_message_for_reason(reason_code):
        return guide_warning_message_for_reason(reason_code)

    def _update_guide_progress_display(self, phase, task_status):
        state = build_guide_progress_view_state(
            phase=phase,
            task_status=task_status,
        )
        self.robot_state_chip.setText(state.robot_state_label)
        self.distance_label.setText(state.status_message)
        self.progress_title_label.setText(state.header_title)
        self.progress_subtitle_label.setText(state.header_subtitle)
        self._apply_progress_stage_states(state.active_stage_index)
        self.progress_bar_fill.setFixedWidth(state.progress_fill_width)
        if state.start_driving_enabled is not None:
            self.start_driving_button.setEnabled(
                state.start_driving_enabled
                and self.detected_target_track_id is not None
            )
        if state.cancel_enabled is not None:
            self.cancel_button.setEnabled(state.cancel_enabled)

    def _apply_progress_stage_states(self, active_index):
        for index, stage in enumerate(self.progress_stages):
            if index < active_index:
                stage.set_state("done")
            elif index == active_index:
                stage.set_state("active")
            else:
                stage.set_state("pending")

    @staticmethod
    def _is_terminal_task_status(task_status):
        return str(task_status or "").strip().upper() in {
            "COMPLETED",
            "CANCELLED",
            "FAILED",
        }

    @staticmethod
    def _is_post_start_guide_phase(phase):
        return str(phase or "").strip().upper() in POST_START_GUIDE_PHASES

    @staticmethod
    def _guide_phase_label(phase, task_status):
        normalized_phase = str(phase or "").strip().upper()
        normalized_status = str(task_status or "").strip().upper()
        labels = {
            "WAIT_TARGET_TRACKING": "대상 확인 대기",
            "READY_TO_START_GUIDANCE": "안내 시작 가능",
            "GUIDANCE_RUNNING": "인계 완료",
            "WAIT_REIDENTIFY": "인계 완료",
            "GUIDANCE_CANCELLED": "인계 완료",
            "GUIDANCE_FINISHED": "인계 완료",
            "GUIDANCE_FAILED": "인계 완료",
            "WAIT_GUIDE_START_CONFIRM": "안내 시작 대기",
        }
        if normalized_phase in labels:
            return labels[normalized_phase]
        if normalized_status == "CANCELLED":
            return "안내 취소"
        if normalized_status == "COMPLETED":
            return "안내 완료"
        return normalized_phase or normalized_status or "-"

    def _session_target_track_id(self):
        session = self.current_session or {}
        command_response = session.get("command_response") or {}
        return command_response.get("target_track_id", session.get("target_track_id"))

    @staticmethod
    def _normalize_target_track_id(value):
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        if normalized < 0:
            return None
        return normalized

    def _current_session_phase(self):
        session = self.current_session or {}
        command_response = session.get("command_response") or {}
        return str(
            command_response.get("phase")
            or command_response.get("guide_phase")
            or session.get("phase")
            or session.get("guide_phase")
            or ""
        ).strip().upper()

    def _complete_guide_handoff(self, *, message, phase, task_status):
        self._update_guide_progress_display(
            phase or "GUIDANCE_RUNNING",
            task_status or "RUNNING",
        )
        self.distance_label.setText(
            message or "안내를 시작했습니다. 로봇을 따라 이동해주세요."
        )
        self.start_driving_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self._set_status_polling_enabled(False)
        self._clear_guide_screen_session()
        self._go_home()

    def _clear_guide_screen_session(self):
        self.selected_patient = None
        self.current_session = None
        self.detected_target_track_id = None

    def finish_guidance(self):
        task_id = str((self.current_session or {}).get("task_id", "")).strip()
        if not task_id:
            self.distance_label.setText("안내 종료에 필요한 task_id가 없습니다.")
            return

        pinky_id = str((self.current_session or {}).get("pinky_id", "pinky1")).strip() or "pinky1"
        try:
            success, message, _response = self.service.finish_guide_session(
                task_id=task_id,
                pinky_id=pinky_id,
                finish_reason="USER_CANCELLED",
            )
        except Exception as exc:
            self.distance_label.setText(f"안내 종료 중 오류가 발생했습니다: {exc}")
            return

        if success:
            self.distance_label.setText("안내 종료 요청이 접수되었습니다.")
            self._set_status_polling_enabled(False)
            self._go_home()
            return

        self.distance_label.setText(f"안내 종료 실패: {message}")

    def _go_home(self):
        self._set_status_polling_enabled(False)
        if self.go_home_page:
            self.go_home_page()

    def _set_status_polling_enabled(self, enabled):
        if enabled and not self.status_timer.isActive():
            self.status_timer.start()
        elif not enabled and self.status_timer.isActive():
            self.status_timer.stop()


__all__ = ["KioskProgressStage", "KioskRobotGuidanceProgressPage"]
