from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


PRIORITY_CODE_TO_LABEL = {
    "NORMAL": "일반",
    "URGENT": "긴급",
    "HIGHEST": "최우선",
}


def _display(value):
    if value is None or value == "":
        return "-"
    return str(value)


def _priority_label(priority_code):
    priority_code = _display(priority_code)
    return PRIORITY_CODE_TO_LABEL.get(priority_code, priority_code)


def _metric_row(label_text, value_text="-", value_object_name="sideMetricValue"):
    row = QFrame()
    row.setObjectName("sideMetricRow")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(12, 10, 12, 10)
    row_layout.setSpacing(10)

    label = QLabel(label_text)
    label.setObjectName("sideMetricLabel")
    value = QLabel(value_text)
    value.setObjectName(value_object_name)
    value.setWordWrap(True)
    value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    row_layout.addWidget(label)
    row_layout.addStretch(1)
    row_layout.addWidget(value)
    return row, label, value


class RequestPreviewCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("requestPreviewCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        title = QLabel("요청 미리보기")
        title.setObjectName("sectionTitle")

        (
            caregiver_row,
            self.preview_caregiver_label,
            self.preview_caregiver_id,
        ) = _metric_row("요청자")
        item_row, self.preview_item_label, self.preview_item = _metric_row("물품")
        (
            quantity_row,
            self.preview_quantity_label,
            self.preview_quantity,
        ) = _metric_row("수량", "1개")
        (
            destination_row,
            self.preview_destination_label,
            self.preview_destination,
        ) = _metric_row("목적지")
        priority_row, self.preview_priority_label, self.preview_priority = _metric_row(
            "우선순위",
            "일반",
            "priorityChip",
        )

        layout.addWidget(title)
        layout.addWidget(caregiver_row)
        layout.addWidget(item_row)
        layout.addWidget(quantity_row)
        layout.addWidget(destination_row)
        layout.addWidget(priority_row)

    def set_delivery_context(self):
        self.preview_item_label.setText("물품")
        self.preview_quantity_label.setText("수량")
        self.preview_destination_label.setText("목적지")

    def set_patrol_context(self):
        self.preview_item_label.setText("순찰 구역")
        self.preview_quantity_label.setText("구역 ID")
        self.preview_destination_label.setText("배정 후보")

    def update_delivery(self, preview):
        item_id = _display(preview.get("item_id"))
        item_name = _display(preview.get("item_name"))
        item_text = "-"
        if item_id != "-" or item_name != "-":
            item_text = f"{item_name} (item_id: {item_id})"

        self.preview_caregiver_id.setText(_display(preview.get("caregiver_id")))
        self.preview_item.setText(item_text)
        self.preview_quantity.setText(f"{_display(preview.get('quantity'))}개")
        self.preview_destination.setText(_display(preview.get("destination_id")))
        self.preview_priority.setText(_priority_label(preview.get("priority")))

    def update_patrol(self, preview):
        self.preview_caregiver_id.setText(_display(preview.get("caregiver_id")))
        self.preview_item.setText(_display(preview.get("patrol_area_name")))
        self.preview_quantity.setText(_display(preview.get("patrol_area_id")))
        self.preview_destination.setText(
            _display(preview.get("assigned_robot_id") or "pinky3")
        )
        self.preview_priority.setText(_priority_label(preview.get("priority")))


class RobotStatusCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("robotStatusCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        title = QLabel("실시간 로봇 상태")
        title.setObjectName("sectionTitle")

        robot_id_row, self.robot_id_text_label, self.robot_id_label = _metric_row(
            "로봇",
            "pinky2",
        )
        (
            robot_state_row,
            self.robot_state_text_label,
            self.robot_state_label,
        ) = _metric_row(
            "상태",
            "feedback 수신 전",
            "robotStateChip",
        )
        robot_pose_row, self.robot_pose_text_label, self.robot_pose_label = _metric_row(
            "위치",
            "미수신",
        )
        (
            robot_destination_row,
            self.robot_destination_text_label,
            self.robot_destination_label,
        ) = _metric_row("목적지")

        self.robot_map_placeholder = QFrame()
        self.robot_map_placeholder.setObjectName("robotMapPlaceholder")
        map_layout = QVBoxLayout(self.robot_map_placeholder)
        map_layout.setContentsMargins(16, 16, 16, 16)
        self.robot_map_label = QLabel("지도 / 위치 placeholder")
        self.robot_map_label.setObjectName("mutedText")
        self.robot_map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_layout.addWidget(self.robot_map_label)

        layout.addWidget(title)
        layout.addWidget(robot_id_row)
        layout.addWidget(robot_state_row)
        layout.addWidget(robot_pose_row)
        layout.addWidget(robot_destination_row)
        layout.addWidget(self.robot_map_placeholder)

    def set_delivery_context(self):
        self.robot_id_text_label.setText("로봇")
        self.robot_state_text_label.setText("상태")
        self.robot_pose_text_label.setText("위치")
        self.robot_destination_text_label.setText("목적지")
        self.robot_map_label.setText("지도 / 위치 placeholder")
        if self.robot_id_label.text() == "pinky3":
            self.robot_id_label.setText("pinky2")

    def set_patrol_context(self):
        self.robot_id_text_label.setText("로봇")
        self.robot_state_text_label.setText("상태")
        self.robot_pose_text_label.setText("위치")
        self.robot_destination_text_label.setText("waypoint")
        self.robot_map_label.setText("순찰 경로 / waypoint placeholder")

    def update_delivery_destination(self, destination_id):
        self.robot_destination_label.setText(_display(destination_id))

    def update_patrol(self, assigned_robot_id):
        self.robot_id_label.setText(_display(assigned_robot_id))
        self.robot_state_label.setText("feedback 수신 전")
        self.robot_pose_label.setText("미수신")
        self.robot_destination_label.setText("미수신")


class RequestResultCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("resultPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        title = QLabel("최근 요청 결과")
        title.setObjectName("sectionTitle")

        self.result_message_label = QLabel("아직 요청 결과가 없습니다.")
        self.result_message_label.setObjectName("resultMessage")
        self.result_message_label.setWordWrap(True)

        result_code_row, self.result_code_text_label, self.result_code_label = (
            _metric_row("결과")
        )
        reason_row, self.reason_code_text_label, self.reason_code_label = _metric_row(
            "사유"
        )
        task_id_row, self.task_id_text_label, self.task_id_label = _metric_row(
            "task_id"
        )
        task_status_row, self.task_status_text_label, self.task_status_label = (
            _metric_row("상태")
        )
        (
            assigned_robot_row,
            self.assigned_robot_text_label,
            self.assigned_robot_id_label,
        ) = _metric_row("배정 로봇")

        layout.addWidget(title)
        layout.addWidget(self.result_message_label)
        layout.addWidget(result_code_row)
        layout.addWidget(reason_row)
        layout.addWidget(task_id_row)
        layout.addWidget(task_status_row)
        layout.addWidget(assigned_robot_row)

    def show_delivery_result(self, response):
        response = response or {}
        self.result_code_label.setText(_display(response.get("result_code")))
        self.result_message_label.setText(_display(response.get("result_message")))
        self.reason_code_label.setText(_display(response.get("reason_code")))
        self.task_id_label.setText(_display(response.get("task_id")))
        self.task_status_label.setText(_display(response.get("task_status")))
        self.assigned_robot_id_label.setText(
            _display(response.get("assigned_robot_id"))
        )


class NoticeCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("noticeCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("주의사항")
        title.setObjectName("noticeTitle")
        text = QLabel(
            "로봇 경로에 장애물이 없는지 확인하세요. 중량이 큰 물품이나 "
            "응급 상황은 운영 절차에 따라 별도 처리해야 합니다."
        )
        text.setObjectName("noticeText")
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(text)


class TaskRequestSidePanel(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self.preview_card = RequestPreviewCard()
        self.robot_status_card = RobotStatusCard()
        self.result_card = RequestResultCard()
        self.notice_card = NoticeCard()

        root.addWidget(self.preview_card)
        root.addWidget(self.robot_status_card)
        root.addWidget(self.result_card)
        root.addWidget(self.notice_card)
        root.addStretch()

        self._bind_legacy_aliases()

    def _bind_legacy_aliases(self):
        self.preview_caregiver_label = self.preview_card.preview_caregiver_label
        self.preview_caregiver_id = self.preview_card.preview_caregiver_id
        self.preview_item_label = self.preview_card.preview_item_label
        self.preview_item = self.preview_card.preview_item
        self.preview_quantity_label = self.preview_card.preview_quantity_label
        self.preview_quantity = self.preview_card.preview_quantity
        self.preview_destination_label = self.preview_card.preview_destination_label
        self.preview_destination = self.preview_card.preview_destination
        self.preview_priority_label = self.preview_card.preview_priority_label
        self.preview_priority = self.preview_card.preview_priority

        self.robot_id_text_label = self.robot_status_card.robot_id_text_label
        self.robot_id_label = self.robot_status_card.robot_id_label
        self.robot_state_text_label = self.robot_status_card.robot_state_text_label
        self.robot_state_label = self.robot_status_card.robot_state_label
        self.robot_pose_text_label = self.robot_status_card.robot_pose_text_label
        self.robot_pose_label = self.robot_status_card.robot_pose_label
        self.robot_destination_text_label = (
            self.robot_status_card.robot_destination_text_label
        )
        self.robot_destination_label = self.robot_status_card.robot_destination_label
        self.robot_map_placeholder = self.robot_status_card.robot_map_placeholder
        self.robot_map_label = self.robot_status_card.robot_map_label

        self.result_message_label = self.result_card.result_message_label
        self.result_code_text_label = self.result_card.result_code_text_label
        self.result_code_label = self.result_card.result_code_label
        self.reason_code_text_label = self.result_card.reason_code_text_label
        self.reason_code_label = self.result_card.reason_code_label
        self.task_id_text_label = self.result_card.task_id_text_label
        self.task_id_label = self.result_card.task_id_label
        self.task_status_text_label = self.result_card.task_status_text_label
        self.task_status_label = self.result_card.task_status_label
        self.assigned_robot_text_label = self.result_card.assigned_robot_text_label
        self.assigned_robot_id_label = self.result_card.assigned_robot_id_label

    def update_preview(self, preview):
        preview = preview or {}
        if preview.get("task_type") == "PATROL":
            self.update_patrol_preview(preview)
            return

        self.set_delivery_context()
        self.preview_card.update_delivery(preview)
        self.robot_status_card.update_delivery_destination(
            preview.get("destination_id")
        )

    def update_patrol_preview(self, preview):
        preview = preview or {}
        self.set_patrol_context()
        self.preview_card.update_patrol(preview)
        self.robot_status_card.update_patrol(
            preview.get("assigned_robot_id") or "pinky3"
        )

    def set_delivery_context(self):
        self.preview_card.set_delivery_context()
        self.robot_status_card.set_delivery_context()

    def set_patrol_context(self):
        self.preview_card.set_patrol_context()
        self.robot_status_card.set_patrol_context()

    def show_delivery_result(self, response):
        response = response or {}
        self.result_card.show_delivery_result(response)
        self.robot_id_label.setText(
            _display(response.get("assigned_robot_id") or "pinky2")
        )
