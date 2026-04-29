from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class NotReadyScenarioForm(QWidget):
    def __init__(self, scenario_name: str, field_labels: list[str], note: str):
        super().__init__()
        self.submit_btn = None
        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel(f"{scenario_name} 요청 구조")
        title.setObjectName("sectionTitle")
        description = QLabel(note)
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        self.not_ready_label = QLabel(
            f"{scenario_name} 요청은 현재 서버 workflow 연동 전입니다. "
            "현재 제출 가능한 시나리오는 물품 운반입니다."
        )
        self.not_ready_label.setObjectName("noticeText")
        self.not_ready_label.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(self.not_ready_label)

        for label in field_labels:
            value = QLabel("준비 중")
            value.setObjectName("mutedText")
            root.addWidget(QLabel(label))
            root.addWidget(value)

        root.addStretch()

        self.submit_btn = QPushButton(f"{scenario_name} 요청 준비 중")
        self.submit_btn.setObjectName("secondaryButton")
        self.submit_btn.setEnabled(False)
        root.addWidget(self.submit_btn)

    def reset_form(self):
        return


class GuideRequestForm(NotReadyScenarioForm):
    def __init__(self):
        super().__init__(
            "안내",
            ["member_id", "visitor_id", "start_location_id", "destination_id"],
            "방문자 키오스크와 안내 workflow가 연결되면 이 입력 구조를 실제 폼으로 전환합니다.",
        )


class FollowRequestForm(NotReadyScenarioForm):
    def __init__(self):
        super().__init__(
            "추종",
            ["target_caregiver_id", "follow_mode", "start_location_id", "priority"],
            "추종 시나리오의 phase 1 포함 여부가 확정되면 실제 요청 API와 연결합니다.",
        )


__all__ = [
    "FollowRequestForm",
    "GuideRequestForm",
    "NotReadyScenarioForm",
]
