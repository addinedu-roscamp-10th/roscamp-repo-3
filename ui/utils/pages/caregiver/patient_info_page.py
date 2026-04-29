from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QTextEdit
)

from ui.utils.network.service_clients import PatientRemoteService
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.common import InlineStatusMixin


class PatientLookupWorker(QObject):
    finished = pyqtSignal(int, object, object)

    def __init__(self, request_id: int, name: str, room_no: str):
        super().__init__()
        self.request_id = request_id
        self.name = name
        self.room_no = room_no

    def run(self):
        service = PatientRemoteService()
        try:
            result = service.search_patient_info(self.name, self.room_no)
            self.finished.emit(self.request_id, True, result)
        except Exception as exc:
            self.finished.emit(self.request_id, False, str(exc))


class PatientInfoPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        self.lookup_thread = None
        self.lookup_worker = None
        self.lookup_request_id = 0
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

        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("호실 입력")

        self.search_btn = QPushButton("조회")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.load_patient_info)

        self.init_inline_status()

        sc.addWidget(QLabel("어르신 이름"))
        sc.addWidget(self.name_input)
        sc.addWidget(QLabel("호실"))
        sc.addWidget(self.room_input)
        sc.addWidget(self.search_btn)
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

        root.addWidget(
            PageHeader(
                "어르신 정보 조회",
                "이름과 호실로 어르신 정보를 조회하고 최근 이벤트와 선호 정보를 확인합니다.",
            )
        )
        root.addWidget(search_card)
        root.addLayout(info_row)
        root.addLayout(content_row, 1)

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

    def load_patient_info(self):
        name = self.name_input.text().strip()
        room_no = self.room_input.text().strip()

        self.lookup_request_id += 1
        self._set_loading_state(True)
        self.show_inline_status("어르신 정보를 조회하고 있습니다.", "info")

        self.lookup_thread = QThread(self)
        self.lookup_worker = PatientLookupWorker(self.lookup_request_id, name, room_no)
        self.lookup_worker.moveToThread(self.lookup_thread)
        self.lookup_thread.started.connect(self.lookup_worker.run)
        self.lookup_worker.finished.connect(self._handle_lookup_result)
        self.lookup_worker.finished.connect(self.lookup_thread.quit)
        self.lookup_worker.finished.connect(self.lookup_worker.deleteLater)
        self.lookup_thread.finished.connect(self.lookup_thread.deleteLater)
        self.lookup_thread.start()

    def _handle_lookup_result(self, request_id, ok, payload):
        if request_id != self.lookup_request_id:
            return

        self._set_loading_state(False)
        self.lookup_thread = None
        self.lookup_worker = None

        if not ok:
            self._clear_result()
            self.show_inline_status(str(payload), "error")
            return

        if not payload:
            self._clear_result()
            self.show_inline_status("일치하는 어르신 정보를 찾지 못했습니다.", "warning")
            return

        self.member_value.setText(payload.get("member_id") or "-")
        self.dislike_value.setText(payload.get("dislike") or "-")
        self.preference_value.setText(payload.get("preference") or "-")

        self.result_box.setPlainText(self._build_event_text(payload))
        self.prescription_box.setPlainText(self._build_prescription_text(payload))

        self.show_inline_status("어르신 정보를 불러왔습니다.", "success")

    def _build_event_text(self, payload):
        lines = [
            f"어르신명: {payload.get('name') or '-'}",
            f"호실: {payload.get('room_no') or '-'}",
            f"어르신 ID: {payload.get('member_id') or '-'}",
            f"입소일: {payload.get('admission_date') or '-'}",
            f"선호 메모: {payload.get('comment') or '-'}",
            "",
            "[최근 이벤트]",
        ]

        events = payload.get("events") or []
        if not events:
            lines.append("최근 이벤트가 없습니다.")
            return "\n".join(lines)

        for row in events:
            event_at = row.get("event_at")
            if hasattr(event_at, "strftime"):
                event_time = event_at.strftime("%Y-%m-%d %H:%M")
            else:
                event_time = str(event_at or "-")
            description = row.get("description") or "-"
            lines.append(f"{event_time} | {description}")

        return "\n".join(lines)

    def _build_prescription_text(self, payload):
        paths = payload.get("prescription_paths") or []
        if not paths:
            return "등록된 처방전 이미지 경로가 없습니다."
        return "\n".join(paths)

    def _clear_result(self):
        self.member_value.setText("-")
        self.dislike_value.setText("-")
        self.preference_value.setText("-")
        self.result_box.setPlainText("어르신 조회 후 이벤트 시간이 표시됩니다.")
        self.prescription_box.setPlainText("조회 후 처방전 이미지 경로가 표시됩니다.")

    def reset_page(self):
        self.lookup_request_id += 1
        self.name_input.clear()
        self.room_input.clear()
        self._set_loading_state(False)
        self._clear_result()
        self.hide_inline_status()
