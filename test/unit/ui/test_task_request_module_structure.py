from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_REQUEST_PAGE = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_request_page.py"
)
TASK_REQUEST_FORMS = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "task_request_forms.py"
)
DELIVERY_REQUEST_FORM = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "delivery_request_form.py"
)
PATROL_REQUEST_FORM = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "patrol_request_form.py"
)
NOT_READY_SCENARIO_FORM = (
    REPO_ROOT
    / "ui"
    / "utils"
    / "pages"
    / "caregiver"
    / "not_ready_scenario_form.py"
)


def test_task_request_page_keeps_only_page_orchestration_classes():
    from ui.utils.pages.caregiver.task_request_forms import (
        DeliveryRequestForm,
        PatrolRequestForm,
    )
    from ui.utils.pages.caregiver.task_request_page import TaskRequestPage

    source = TASK_REQUEST_PAGE.read_text(encoding="utf-8")

    assert TaskRequestPage.__name__ == "TaskRequestPage"
    assert DeliveryRequestForm.__name__ == "DeliveryRequestForm"
    assert PatrolRequestForm.__name__ == "PatrolRequestForm"
    assert "class DeliveryRequestForm" not in source
    assert "class PatrolRequestForm" not in source
    assert "class NotReadyScenarioForm" not in source
    assert "class DeliveryItemsLoadWorker" not in source
    assert "class DeliverySubmitWorker" not in source


def test_task_request_forms_module_only_reexports_scenario_forms():
    from ui.utils.pages.caregiver.task_request_forms import (
        DeliveryRequestForm,
        FollowRequestForm,
        GuideRequestForm,
        NotReadyScenarioForm,
        PatrolRequestForm,
    )

    source = TASK_REQUEST_FORMS.read_text(encoding="utf-8")

    assert DeliveryRequestForm.__module__.endswith("delivery_request_form")
    assert PatrolRequestForm.__module__.endswith("patrol_request_form")
    assert NotReadyScenarioForm.__module__.endswith("not_ready_scenario_form")
    assert GuideRequestForm.__module__.endswith("not_ready_scenario_form")
    assert FollowRequestForm.__module__.endswith("not_ready_scenario_form")
    assert "class DeliveryRequestForm" not in source
    assert "class PatrolRequestForm" not in source
    assert "class NotReadyScenarioForm" not in source
    assert DELIVERY_REQUEST_FORM.exists()
    assert PATROL_REQUEST_FORM.exists()
    assert NOT_READY_SCENARIO_FORM.exists()


def test_task_request_options_worker_name_matches_shared_options_role(monkeypatch):
    from ui.utils.pages.caregiver import task_request_workers
    from ui.utils.pages.caregiver.task_request_workers import TaskRequestOptionsLoadWorker

    class FakeService:
        def get_delivery_items(self):
            return [{"item_id": 1}]

        def get_delivery_destinations(self):
            return [{"destination_id": "delivery_room_301"}]

        def get_patrol_areas(self):
            return [{"patrol_area_id": "patrol_ward_night_01"}]

    monkeypatch.setattr(
        task_request_workers,
        "DeliveryRequestRemoteService",
        FakeService,
    )

    emitted = []
    worker = TaskRequestOptionsLoadWorker()
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))
    worker.run()

    assert not hasattr(task_request_workers, "DeliveryItemsLoadWorker")
    assert emitted == [
        (
            True,
            {
                "items": [{"item_id": 1}],
                "destinations": [{"destination_id": "delivery_room_301"}],
                "patrol_areas": [{"patrol_area_id": "patrol_ward_night_01"}],
            },
        )
    ]


def test_delivery_cancel_worker_calls_remote_cancel_service(monkeypatch):
    from ui.utils.pages.caregiver import task_request_workers
    from ui.utils.pages.caregiver.task_request_workers import DeliveryCancelWorker

    calls = []

    class FakeService:
        def cancel_delivery_task(self, task_id):
            calls.append(task_id)
            return {
                "result_code": "CANCEL_REQUESTED",
                "task_id": task_id,
                "task_status": "CANCEL_REQUESTED",
                "cancel_requested": True,
            }

    monkeypatch.setattr(
        task_request_workers,
        "DeliveryRequestRemoteService",
        FakeService,
    )

    emitted = []
    worker = DeliveryCancelWorker(task_id=1001)
    worker.finished.connect(lambda ok, payload: emitted.append((ok, payload)))
    worker.run()

    assert calls == [1001]
    assert emitted == [
        (
            True,
            {
                "result_code": "CANCEL_REQUESTED",
                "task_id": 1001,
                "task_status": "CANCEL_REQUESTED",
                "cancel_requested": True,
            },
        )
    ]


def test_patrol_submit_worker_calls_remote_patrol_create_service(monkeypatch):
    from ui.utils.pages.caregiver import task_request_workers
    from ui.utils.pages.caregiver.task_request_workers import PatrolSubmitWorker

    payload = {
        "request_id": "req_patrol_001",
        "caregiver_id": 1,
        "patrol_area_id": "patrol_ward_night_01",
        "priority": "NORMAL",
        "idempotency_key": "idem_patrol_001",
    }
    calls = []

    class FakeService:
        def create_patrol_task(self, **kwargs):
            calls.append(kwargs)
            return {
                "result_code": "ACCEPTED",
                "task_id": 2001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky3",
            }

    monkeypatch.setattr(
        task_request_workers,
        "DeliveryRequestRemoteService",
        FakeService,
    )

    emitted = []
    worker = PatrolSubmitWorker(payload)
    worker.finished.connect(lambda ok, response: emitted.append((ok, response)))
    worker.run()

    assert calls == [payload]
    assert emitted == [
        (
            True,
            {
                "result_code": "ACCEPTED",
                "task_id": 2001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky3",
            },
        )
    ]
