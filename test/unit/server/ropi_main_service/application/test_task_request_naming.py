from server.ropi_main_service.application import TaskRequestService
from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
    TaskRequestRepository,
)
from server.ropi_main_service.application.rpc_service_registry import SERVICE_REGISTRY


def test_task_request_service_is_canonical_name_with_delivery_alias():
    assert TaskRequestService.__name__ == "TaskRequestService"
    assert DeliveryRequestService is TaskRequestService
    assert SERVICE_REGISTRY["task_request"] is TaskRequestService


def test_task_request_repository_is_canonical_name_with_delivery_alias():
    assert TaskRequestRepository.__name__ == "TaskRequestRepository"
    assert DeliveryRequestRepository is TaskRequestRepository
