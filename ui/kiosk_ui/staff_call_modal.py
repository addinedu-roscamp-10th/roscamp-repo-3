from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class KioskStaffCallModal(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("kioskStaffCallModalOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(48, 48, 48, 48)
        overlay_layout.setSpacing(0)
        overlay_layout.addStretch()

        self.card = QFrame()
        self.card.setObjectName("kioskStaffCallModalCard")
        self.card.setMinimumWidth(620)
        self.card.setMaximumWidth(720)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(44, 42, 44, 42)
        card_layout.setSpacing(20)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("✓")
        self.icon_label.setObjectName("kioskStaffCallModalIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(92, 92)

        self.title_label = QLabel("직원 호출이 접수되었습니다.")
        self.title_label.setObjectName("kioskStaffCallModalTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)

        self.message_label = QLabel("잠시만 기다려 주세요.")
        self.message_label.setObjectName("kioskStaffCallModalMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)

        self.close_button = QPushButton("확인")
        self.close_button.setObjectName("kioskStaffCallModalCloseButton")
        self.close_button.setMinimumHeight(72)
        self.close_button.clicked.connect(self.hide)

        card_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.message_label)
        card_layout.addWidget(self.close_button)

        overlay_layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()

    def show_result(self, *, success, message):
        state = "success" if success else "error"
        self.setProperty("state", state)
        self.card.setProperty("state", state)
        self.icon_label.setProperty("state", state)
        self.title_label.setText(
            "직원 호출이 접수되었습니다."
            if success
            else "직원 호출 접수에 실패했습니다."
        )
        self.icon_label.setText("✓" if success else "!")
        self.message_label.setText(
            str(message or "").strip()
            or ("잠시만 기다려 주세요." if success else "데스크에 문의해 주세요.")
        )
        for widget in [self, self.card, self.icon_label, self.title_label, self.message_label]:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.show()
        self.raise_()
        self.close_button.setFocus()


__all__ = ["KioskStaffCallModal"]
