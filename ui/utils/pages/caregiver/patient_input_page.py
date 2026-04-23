from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, QPushButton
from ui.utils.widgets.common import InlineStatusMixin, page_title

class PatientInputPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(page_title("어르신 정보 입력", "어르신 신규 정보 또는 수정 정보를 입력합니다."))

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.room_input = QLineEdit()
        self.meal_combo = QComboBox()
        self.meal_combo.addItems(["아침 완료", "점심 완료", "저녁 완료", "일부 섭취", "미섭취"])
        self.med_combo = QComboBox()
        self.med_combo.addItems(["오전 복용 완료", "점심 복용 완료", "저녁 복용 완료", "복용 전"])
        self.fall_input = QLineEdit()
        self.visit_combo = QComboBox()
        self.visit_combo.addItems(["가능", "확인 필요", "불가"])
        self.note_input = QTextEdit()
        self.init_inline_status()

        form.addRow("어르신 이름", self.name_input)
        form.addRow("병실", self.room_input)
        form.addRow("식사 상태", self.meal_combo)
        form.addRow("복약 상태", self.med_combo)
        form.addRow("낙상 이력", self.fall_input)
        form.addRow("면회 상태", self.visit_combo)
        form.addRow("특이사항", self.note_input)
        root.addLayout(form)
        root.addWidget(self.status_label)

        save_btn = QPushButton("저장")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.save)
        root.addWidget(save_btn)

    def save(self):
        self.show_inline_status("어르신 정보가 저장되었습니다.", "success")
