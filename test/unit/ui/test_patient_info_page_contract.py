import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
CAREGIVER_PAGE_ROOT = REPO_ROOT / "ui" / "utils" / "pages" / "caregiver"
PATIENT_INFO_PAGE = CAREGIVER_PAGE_ROOT / "patient_info_page.py"


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_patient_info_page_uses_shared_worker_thread_helper():
    source = PATIENT_INFO_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in source
    assert "start_worker_thread(" in source
    assert "stop_worker_thread(" in source
    assert "QThread(" not in source


def test_patient_lookup_worker_uses_patient_rpc(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.patient_info_page as patient_info_page
    from ui.utils.pages.caregiver.patient_info_page import PatientLookupWorker

    calls = []

    class FakePatientRemoteService:
        def search_patient_info(self, name, room_no):
            calls.append((name, room_no))
            return {"member_id": "301", "name": "김환자"}

    monkeypatch.setattr(
        patient_info_page,
        "PatientRemoteService",
        FakePatientRemoteService,
    )

    worker = PatientLookupWorker(7, "김환자", "301")
    emitted = []
    worker.finished.connect(lambda *args: emitted.append(args))

    worker.run()

    assert calls == [("김환자", "301")]
    assert emitted == [(7, True, {"member_id": "301", "name": "김환자"})]


def test_patient_info_page_resets_and_shutdowns_lookup_worker():
    _app()

    from ui.utils.pages.caregiver.patient_info_page import PatientInfoPage

    page = PatientInfoPage()

    try:
        labels = _label_texts(page)
        assert "어르신 정보 조회" in labels
        assert hasattr(page, "shutdown")

        page.name_input.setText("김환자")
        page.room_input.setText("301")
        page.member_value.setText("301")
        page.reset_page()

        assert page.name_input.text() == ""
        assert page.room_input.text() == ""
        assert page.member_value.text() == "-"
    finally:
        page.shutdown()
        page.close()


def test_unused_legacy_caregiver_pages_are_removed():
    legacy_pages = [
        "caregiver_home_page.py",
        "patient_input_page.py",
        "emergency_call_page.py",
        "robot_call_page.py",
    ]

    for page_name in legacy_pages:
        assert not (CAREGIVER_PAGE_ROOT / page_name).exists()
