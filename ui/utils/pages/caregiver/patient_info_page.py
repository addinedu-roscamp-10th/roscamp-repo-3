from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QTextEdit, QListWidget, QListWidgetItem
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.service_clients import PatientRemoteService
from ui.utils.widgets.admin_common import (
    display_text as _display,
    operator_datetime_text as _datetime,
)
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard
from ui.utils.widgets.common import InlineStatusMixin


class PatientCandidateLookupWorker(QObject):
    finished = pyqtSignal(int, object, object)

    def __init__(self, request_id: int, name: str, room_no: str, limit: int = 10):
        super().__init__()
        self.request_id = request_id
        self.name = name
        self.room_no = room_no
        self.limit = limit

    def run(self):
        service = PatientRemoteService()
        try:
            result = service.search_patient_candidates(
                self.name,
                self.room_no,
                limit=self.limit,
            )
            self.finished.emit(self.request_id, True, result)
        except Exception as exc:
            self.finished.emit(self.request_id, False, str(exc))


class PatientLookupWorker(QObject):
    finished = pyqtSignal(int, object, object)

    def __init__(self, request_id: int, name: str = "", room_no: str = "", member_id=None):
        super().__init__()
        self.request_id = request_id
        self.name = name
        self.room_no = room_no
        self.member_id = member_id

    def run(self):
        service = PatientRemoteService()
        try:
            if self.member_id is not None:
                result = service.get_patient_info(self.member_id)
            else:
                result = service.search_patient_info(self.name, self.room_no)
            self.finished.emit(self.request_id, True, result)
        except Exception as exc:
            self.finished.emit(self.request_id, False, str(exc))


class PatientInfoPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.lookup_thread = None
        self.lookup_worker = None
        self.candidate_thread = None
        self.candidate_worker = None
        self.lookup_request_id = 0
        self.candidate_request_id = 0
        self.selected_candidate = None
        self._candidate_debounce_ms = 250
        self._updating_inputs_from_candidate = False
        self.candidate_timer = QTimer(self)
        self.candidate_timer.setSingleShot(True)
        self.candidate_timer.timeout.connect(self.load_patient_candidates)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        search_card = QFrame()
        search_card.setObjectName("formCard")
        sc = QVBoxLayout(search_card)
        sc.setContentsMargins(20, 20, 20, 20)
        sc.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("어르신 이름 입력")
        self.name_input.textChanged.connect(self._schedule_candidate_lookup)

        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("호실 입력")
        self.room_input.textChanged.connect(self._schedule_candidate_lookup)

        self.search_btn = QPushButton("조회")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.load_patient_info)

        self.init_inline_status()

        sc.addWidget(QLabel("어르신 이름"))
        sc.addWidget(self.name_input)
        sc.addWidget(QLabel("호실"))
        sc.addWidget(self.room_input)
        sc.addWidget(self.search_btn)
        sc.addWidget(self._build_candidate_list())
        sc.addWidget(self.status_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        self.member_box, self.member_value = self._make_info_box("어르신 ID", "-")
        self.dislike_box, self.dislike_value = self._make_info_box("비선호", "-")
        self.preference_box, self.preference_value = self._make_info_box("선호", "-")

        info_row.addWidget(self.member_box)
        info_row.addWidget(self.dislike_box)
        info_row.addWidget(self.preference_box)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        history_card = QFrame()
        history_card.setObjectName("formCard")
        hc = QVBoxLayout(history_card)
        hc.setContentsMargins(20, 20, 20, 20)
        hc.setSpacing(12)

        history_title = QLabel("최근 이벤트 시간 / 설명")
        history_title.setObjectName("sectionTitle")

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlainText("어르신 조회 후 이벤트 시간이 표시됩니다.")

        hc.addWidget(history_title)
        hc.addWidget(self.result_box)

        prescription_card = QFrame()
        prescription_card.setObjectName("formCard")
        pc = QVBoxLayout(prescription_card)
        pc.setContentsMargins(20, 20, 20, 20)
        pc.setSpacing(12)

        prescription_title = QLabel("처방전 이미지 경로")
        prescription_title.setObjectName("sectionTitle")

        self.prescription_box = QTextEdit()
        self.prescription_box.setReadOnly(True)
        self.prescription_box.setPlainText("조회 후 처방전 이미지 경로가 표시됩니다.")

        pc.addWidget(prescription_title)
        pc.addWidget(self.prescription_box)

        content_row.addWidget(history_card, 2)
        content_row.addWidget(prescription_card, 1)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            PageHeader(
                "어르신 정보 조회",
                "이름이나 호실 일부로 후보를 찾고 최근 이벤트와 선호 정보를 확인합니다.",
            ),
            1,
        )
        self.time_card = PageTimeCard(show_last_update=False)
        header_row.addWidget(self.time_card)

        root.addLayout(header_row)
        root.addWidget(search_card)
        root.addLayout(info_row)
        root.addLayout(content_row, 1)

    def _build_candidate_list(self):
        self.candidate_list = QListWidget()
        self.candidate_list.setObjectName("patientCandidateList")
        self.candidate_list.setMaximumHeight(132)
        self.candidate_list.itemClicked.connect(self._handle_candidate_clicked)
        self.candidate_empty_label = QLabel("이름이나 호실 일부를 입력하면 후보가 표시됩니다.")
        self.candidate_empty_label.setObjectName("mutedText")
        self.candidate_empty_label.setWordWrap(True)

        box = QFrame()
        box.setObjectName("patientCandidateBox")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.candidate_empty_label)
        layout.addWidget(self.candidate_list)
        self.candidate_list.hide()
        return box

    def _make_info_box(self, title_text, value_text):
        box = QFrame()
        box.setObjectName("infoBox")
        b = QVBoxLayout(box)
        b.setContentsMargins(18, 16, 18, 16)

        title = QLabel(title_text)
        title.setObjectName("mutedText")
        value = QLabel(value_text)
        value.setObjectName("bigValue")
        value.setWordWrap(True)

        b.addWidget(title)
        b.addWidget(value)
        return box, value

    def _set_loading_state(self, loading: bool):
        self.search_btn.setDisabled(loading)
        self.search_btn.setText("조회 중..." if loading else "조회")

    def _schedule_candidate_lookup(self):
        if self._updating_inputs_from_candidate:
            return
        self.selected_candidate = None
        self.candidate_timer.start(self._candidate_debounce_ms)

    def load_patient_candidates(self):
        name = self.name_input.text().strip()
        room_no = self.room_input.text().strip()

        self.candidate_request_id += 1
        if not name and not room_no:
            self._apply_candidate_rows([])
            self.candidate_empty_label.setText("이름이나 호실 일부를 입력하면 후보가 표시됩니다.")
            return

        self.candidate_empty_label.setText("후보를 검색하고 있습니다.")
        self.candidate_list.hide()
        self.candidate_thread, self.candidate_worker = start_worker_thread(
            self,
            worker=PatientCandidateLookupWorker(
                self.candidate_request_id,
                name,
                room_no,
            ),
            finished_handler=self._handle_candidate_result,
            clear_handler=self._clear_candidate_thread,
        )

    def _handle_candidate_result(self, request_id, ok, payload):
        if request_id != self.candidate_request_id:
            return
        if not ok:
            self._apply_candidate_rows([])
            self.candidate_empty_label.setText(str(payload))
            return
        candidates = payload or []
        self._apply_candidate_rows(candidates)
        if candidates:
            self.candidate_empty_label.setText("후보를 선택하면 상세 정보를 조회합니다.")
        else:
            self.candidate_empty_label.setText("검색 후보가 없습니다.")

    def _apply_candidate_rows(self, candidates):
        self.candidate_list.clear()
        for candidate in candidates or []:
            member_id = candidate.get("member_id")
            name = _display(candidate.get("name"))
            room_no = _display(candidate.get("room_no"))
            item = QListWidgetItem(f"{name} · {room_no}호 · #{_display(member_id)}")
            item.setData(Qt.ItemDataRole.UserRole, dict(candidate))
            self.candidate_list.addItem(item)
        self.candidate_list.setVisible(self.candidate_list.count() > 0)

    def _handle_candidate_clicked(self, item):
        candidate = item.data(Qt.ItemDataRole.UserRole) or {}
        self.selected_candidate = candidate
        self._updating_inputs_from_candidate = True
        self.name_input.setText(_display(candidate.get("name"), ""))
        self.room_input.setText(_display(candidate.get("room_no"), ""))
        self._updating_inputs_from_candidate = False
        self.load_patient_info_for_candidate(candidate)

    def load_patient_info(self):
        name = self.name_input.text().strip()
        room_no = self.room_input.text().strip()

        self.lookup_request_id += 1
        if self.selected_candidate:
            self._start_patient_lookup(member_id=self.selected_candidate.get("member_id"))
            return

        if not name and not room_no:
            self._clear_result()
            self.show_inline_status("이름이나 호실 일부를 입력해 후보를 선택해 주세요.", "warning")
            return

        self.load_patient_candidates()
        self.show_inline_status("검색 후보를 선택해 주세요.", "info")

    def load_patient_info_for_candidate(self, candidate):
        self.lookup_request_id += 1
        self._start_patient_lookup(member_id=candidate.get("member_id"))

    def _start_patient_lookup(self, *, member_id=None, name="", room_no=""):
        self._set_loading_state(True)
        self.show_inline_status("어르신 정보를 조회하고 있습니다.", "info")

        self.lookup_thread, self.lookup_worker = start_worker_thread(
            self,
            worker=PatientLookupWorker(
                self.lookup_request_id,
                name,
                room_no,
                member_id=member_id,
            ),
            finished_handler=self._handle_lookup_result,
            clear_handler=self._clear_lookup_thread,
        )

    def _handle_lookup_result(self, request_id, ok, payload):
        if request_id != self.lookup_request_id:
            return

        self._set_loading_state(False)

        if not ok:
            self._clear_result()
            self.show_inline_status(str(payload), "error")
            return

        if not payload:
            self._clear_result()
            self.show_inline_status("일치하는 어르신 정보를 찾지 못했습니다.", "warning")
            return

        self.member_value.setText(_display(payload.get("member_id")))
        self.dislike_value.setText(_display(payload.get("dislike")))
        self.preference_value.setText(_display(payload.get("preference")))

        self.result_box.setPlainText(self._build_event_text(payload))
        self.prescription_box.setPlainText(self._build_prescription_text(payload))

        self.show_inline_status("어르신 정보를 불러왔습니다.", "success")

    def _build_event_text(self, payload):
        lines = [
            f"어르신명: {_display(payload.get('name'))}",
            f"호실: {_display(payload.get('room_no'))}",
            f"어르신 ID: {_display(payload.get('member_id'))}",
            f"입소일: {_datetime(payload.get('admission_date'))}",
            f"선호 메모: {_display(payload.get('comment'))}",
            "",
            "[최근 이벤트]",
        ]

        events = payload.get("events") or []
        if not events:
            lines.append("최근 이벤트가 없습니다.")
            return "\n".join(lines)

        for row in events:
            event_time = _datetime(row.get("event_at"))
            description = _display(row.get("description"))
            lines.append(f"{event_time} | {description}")

        return "\n".join(lines)

    def _build_prescription_text(self, payload):
        paths = payload.get("prescription_paths") or []
        if not paths:
            return "등록된 처방전 이미지 경로가 없습니다."
        return "\n".join(_display(path) for path in paths)

    def _clear_result(self):
        self.member_value.setText("-")
        self.dislike_value.setText("-")
        self.preference_value.setText("-")
        self.result_box.setPlainText("어르신 조회 후 이벤트 시간이 표시됩니다.")
        self.prescription_box.setPlainText("조회 후 처방전 이미지 경로가 표시됩니다.")

    def _clear_lookup_thread(self):
        self.lookup_thread = None
        self.lookup_worker = None

    def _clear_candidate_thread(self):
        self.candidate_thread = None
        self.candidate_worker = None

    def reset_page(self):
        self.lookup_request_id += 1
        self.candidate_request_id += 1
        self.candidate_timer.stop()
        self.selected_candidate = None
        self.name_input.clear()
        self.room_input.clear()
        self._apply_candidate_rows([])
        self.candidate_empty_label.setText("이름이나 호실 일부를 입력하면 후보가 표시됩니다.")
        self._set_loading_state(False)
        self._clear_result()
        self.hide_inline_status()

    def shutdown(self):
        self.candidate_timer.stop()
        stop_worker_thread(
            self.candidate_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_candidate_thread,
        )
        stop_worker_thread(
            self.lookup_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_lookup_thread,
        )
