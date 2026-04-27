from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QTextEdit
)

from ui.utils.network.service_clients import VisitorInfoRemoteService


class VisitorInfoPage(QWidget):
    def __init__(self):
        super().__init__()
        self.service = VisitorInfoRemoteService()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("면회 정보 조회")
        title.setObjectName("pageTitle")
        subtitle = QLabel("어르신 이름이나 병실로 면회 가능 여부와 기본 정보를 확인합니다.")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        chip = QLabel("Visitor Info")
        chip.setObjectName("chipBlue")

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(chip)

        search_card = QFrame()
        search_card.setObjectName("formCard")
        sc = QVBoxLayout(search_card)
        sc.setContentsMargins(20, 20, 20, 20)
        sc.setSpacing(12)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("어르신 이름 또는 병실 입력")
        self.keyword_input.returnPressed.connect(self.load_visitor_info)

        self.search_btn = QPushButton("조회")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.load_visitor_info)

        self.status_label = QLabel("조회 대기 중")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)

        sc.addWidget(QLabel("검색어"))
        sc.addWidget(self.keyword_input)
        sc.addWidget(self.search_btn)
        sc.addWidget(self.status_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        self.meal_box, self.meal_value = self._make_info_box("식사 상태", "-")
        self.med_box, self.med_value = self._make_info_box("복약 상태", "-")
        self.fall_box, self.fall_value = self._make_info_box("안전 상태", "-")
        self.visit_box, self.visit_value = self._make_info_box("면회 가능 여부", "-")

        info_row.addWidget(self.meal_box)
        info_row.addWidget(self.med_box)
        info_row.addWidget(self.fall_box)
        info_row.addWidget(self.visit_box)

        history_card = QFrame()
        history_card.setObjectName("formCard")
        hc = QVBoxLayout(history_card)
        hc.setContentsMargins(20, 20, 20, 20)
        hc.setSpacing(12)

        history_title = QLabel("상세 안내")
        history_title.setObjectName("sectionTitle")

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlainText("어르신 조회 후 면회 안내 정보가 표시됩니다.")

        hc.addWidget(history_title)
        hc.addWidget(self.result_box)

        root.addLayout(header)
        root.addWidget(search_card)
        root.addLayout(info_row)
        root.addWidget(history_card, 1)

    def _make_info_box(self, title_text, value_text):
        box = QFrame()
        box.setObjectName("infoBox")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 16, 18, 16)

        title = QLabel(title_text)
        title.setObjectName("mutedText")
        value = QLabel(value_text)
        value.setObjectName("bigValue")

        layout.addWidget(title)
        layout.addWidget(value)
        return box, value

    def load_visitor_info(self):
        ok, message, patient = self.service.get_patient_visit_info(self.keyword_input.text())
        self.status_label.setText(message)

        if not ok:
            self.meal_value.setText("-")
            self.med_value.setText("-")
            self.fall_value.setText("-")
            self.visit_value.setText("-")
            self.result_box.setPlainText("조회 결과가 없습니다.")
            return

        self.meal_value.setText(patient.get("meal_status", "-"))
        self.med_value.setText(patient.get("medication_status", "-"))
        self.fall_value.setText(patient.get("fall_risk", "-"))
        self.visit_value.setText(patient.get("visit_status", "-"))

        self.result_box.setPlainText(
            f"어르신명: {patient.get('name', '-') }\n"
            f"병실: {patient.get('room', '-') }\n"
            f"면회 가능 여부: {patient.get('visit_status', '-') }\n"
            f"식사 상태: {patient.get('meal_status', '-') }\n"
            f"복약 상태: {patient.get('medication_status', '-') }\n"
            f"안전 상태: {patient.get('fall_risk', '-') }\n\n"
            f"안내 메모\n{patient.get('notes', '등록된 메모가 없습니다.') }"
        )
