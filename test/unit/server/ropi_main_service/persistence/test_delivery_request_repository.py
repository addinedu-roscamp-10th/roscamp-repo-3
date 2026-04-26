from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
)


class FakeDeliveryRequestRepository(DeliveryRequestRepository):
    def get_product_by_id(self, item_id, conn=None):
        return {"item_id": item_id, "item_name": "물티슈"}


def test_create_delivery_task_uses_runtime_config_assigned_pinky_id():
    repository = FakeDeliveryRequestRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9")
    )

    response = repository.create_delivery_task(
        request_id="req_001",
        caregiver_id="cg_001",
        item_id="supply_001",
        quantity=1,
        destination_id="room2",
        priority="NORMAL",
        notes=None,
        idempotency_key="idem_001",
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["assigned_pinky_id"] == "pinky9"
