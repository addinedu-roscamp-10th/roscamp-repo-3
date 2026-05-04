import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
ALERT_LOG_PAGE = (
    REPO_ROOT / "ui" / "utils" / "pages" / "caregiver" / "alert_log_page.py"
)


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _bundle():
    return {
        "summary": {
            "total_event_count": 2,
            "warning_count": 1,
            "error_count": 1,
            "critical_count": 0,
        },
        "events": [
            {
                "event_id": 11,
                "occurred_at": "2026-05-03T12:00:00",
                "severity": "ERROR",
                "source_component": "Control Service",
                "task_id": 1001,
                "robot_id": "pinky2",
                "event_type": "TASK_FAILED",
                "result_code": "FAILED",
                "reason_code": "ROS_ACTION_FAILED",
                "message": "navigation failed",
                "payload": {"phase": "DELIVERY_DESTINATION"},
            },
            {
                "event_id": 12,
                "occurred_at": "2026-05-03T12:01:00",
                "severity": "WARNING",
                "source_component": "AI Server",
                "task_id": 1002,
                "robot_id": "pinky3",
                "event_type": "FALL_ALERT_CREATED",
                "result_code": "ACCEPTED",
                "reason_code": None,
                "message": "fall alert candidate accepted",
                "payload": {"evidence_image_available": True},
            },
        ],
    }


def test_alert_log_page_matches_phase1_layout_contract():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)

    try:
        labels = _label_texts(page)
        refresh_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("alert_log_action") == "refresh"
        ]

        assert "알림/로그" in labels
        assert "기간" in labels
        assert "심각도" in labels
        assert "출처" in labels
        assert "작업 ID" in labels
        assert "로봇 ID" in labels
        assert "이벤트 종류" in labels
        assert "이벤트 상세" in labels
        assert "관련 작업/로봇" in labels
        assert page.findChild(QFrame, "pageTimeCard") is not None
        assert "새로고침" in [button.text() for button in refresh_buttons]
        assert [
            page.table.horizontalHeaderItem(index).text()
            for index in range(page.table.columnCount())
        ] == [
            "이벤트 ID",
            "발생 시각",
            "심각도",
            "출처",
            "작업 ID",
            "로봇 ID",
            "이벤트 종류",
            "메시지",
        ]
    finally:
        page.close()


def test_alert_log_page_applies_server_bundle_to_summary_table_and_detail():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)

    try:
        page.apply_alert_log_bundle(_bundle())

        labels = _label_texts(page)
        assert "2건" in labels
        assert "1건" in labels
        assert page.table.rowCount() == 2
        assert page.table.item(0, 0).text() == "11"
        assert page.table.item(0, 1).text() == "2026.05.03 12:00"
        assert page.table.item(0, 2).text() == "ERROR"
        assert page.table.item(0, 5).text() == "pinky2"
        assert "T12:00:00" not in page.table.item(0, 1).text()

        page.table.selectRow(0)
        page._handle_table_selection()

        labels = _label_texts(page)
        assert "이벤트 ID" in labels
        assert "11" in labels
        assert "발생 시각" in labels
        assert "2026.05.03 12:00" in labels
        assert "사유 코드" in labels
        assert "ROS_ACTION_FAILED" in labels
        assert "작업 ID" in labels
        assert "1001" in labels
        assert "로봇 ID" in labels
        assert "pinky2" in labels
        assert page.findChildren(QFrame, "keyValueRow")
        assert "event_id" not in labels
        assert "occurred_at" not in labels
        assert "task_id" not in labels
        assert "robot_id" not in labels
        assert not any("event_id: 11" in text for text in labels)
        assert not any("task_id=1001" in text for text in labels)
        assert page.related_task_button.property("task_id") == 1001
        assert page.related_task_button.isEnabled() is True
        assert page.related_robot_button.property("robot_id") == "pinky2"
        assert page.related_robot_button.isEnabled() is True
    finally:
        page.close()


def test_alert_log_page_collects_operator_filters():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)

    try:
        for widget in (
            page.period_combo,
            page.severity_combo,
            page.source_input,
            page.task_id_input,
            page.robot_id_input,
            page.event_type_input,
        ):
            widget.blockSignals(True)

        page.period_combo.setCurrentIndex(page.period_combo.findData("LAST_1_HOUR"))
        page.severity_combo.setCurrentIndex(page.severity_combo.findData("ERROR"))
        page.source_input.setText("Control Service")
        page.task_id_input.setText("1001")
        page.robot_id_input.setText("pinky2")
        page.event_type_input.setText("TASK_FAILED")

        for widget in (
            page.period_combo,
            page.severity_combo,
            page.source_input,
            page.task_id_input,
            page.robot_id_input,
            page.event_type_input,
        ):
            widget.blockSignals(False)

        assert page._collect_filters() == {
            "period": "LAST_1_HOUR",
            "severity": "ERROR",
            "source_component": "Control Service",
            "task_id": "1001",
            "robot_id": "pinky2",
            "event_type": "TASK_FAILED",
            "limit": 100,
        }
    finally:
        page.close()


def test_alert_log_page_refreshes_when_combo_filters_change():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)
    calls = []

    try:
        page.refresh_data = lambda: calls.append(page._collect_filters())

        page.period_combo.setCurrentIndex(page.period_combo.findData("LAST_1_HOUR"))
        page.severity_combo.setCurrentIndex(page.severity_combo.findData("ERROR"))

        assert calls[0]["period"] == "LAST_1_HOUR"
        assert calls[-1]["severity"] == "ERROR"
    finally:
        page.close()


def test_alert_log_page_debounces_text_filters_and_uses_table_as_candidates():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)
    calls = []

    try:
        page.refresh_data = lambda: calls.append(page._collect_filters())

        page.source_input.setText("Control")

        assert page.filter_timer.isActive() is True
        assert calls == []

        page.filter_timer.stop()
        page._run_debounced_filter_refresh()

        assert calls == [
            {
                "period": "LAST_24_HOURS",
                "severity": None,
                "source_component": "Control",
                "task_id": None,
                "robot_id": None,
                "event_type": None,
                "limit": 100,
            }
        ]
    finally:
        page.close()


def test_alert_log_page_queues_latest_filter_refresh_while_loading():
    _app()

    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

    page = AlertLogPage(autoload=False)
    calls = []

    try:
        page.load_thread = object()

        page.refresh_data()

        assert page._pending_filter_refresh is True

        page.refresh_data = lambda: calls.append("refresh")
        page._clear_load_thread()

        assert calls == ["refresh"]
    finally:
        page.close()


def test_alert_log_load_worker_uses_caregiver_alert_log_rpc(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.alert_log_page as alert_log_page
    from ui.utils.pages.caregiver.alert_log_page import AlertLogLoadWorker

    calls = []

    class FakeCaregiverRemoteService:
        def get_alert_log_bundle(self, **filters):
            calls.append(filters)
            return _bundle()

    monkeypatch.setattr(
        alert_log_page,
        "CaregiverRemoteService",
        FakeCaregiverRemoteService,
    )

    worker = AlertLogLoadWorker({"period": "LAST_24_HOURS", "severity": "ERROR"})
    emitted = []
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))

    worker.run()

    assert calls == [{"period": "LAST_24_HOURS", "severity": "ERROR"}]
    assert emitted[0][0] is True
    assert emitted[0][1]["summary"]["total_event_count"] == 2


def test_alert_log_page_uses_shared_worker_thread_helper():
    source = ALERT_LOG_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in source
    assert "start_worker_thread(" in source
    assert "stop_worker_thread(" in source
    assert "QThread(" not in source
    assert "ui.utils.mock_data" not in source
