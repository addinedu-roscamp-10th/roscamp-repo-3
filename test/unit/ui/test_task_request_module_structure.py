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
