from unittest.mock import patch

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
)


class FakeCursor:
    lastrowid = 101

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeExistingIdempotencyCursor:
    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchone(self):
        return {
            "request_hash": "different_hash",
            "response_json": '{"result_code":"ACCEPTED"}',
        }


class FakeConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def begin(self):
        pass

    def cursor(self):
        return FakeCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeDeliveryRequestRepository(DeliveryRequestRepository):
    def _find_idempotent_response(self, cur, *, requester_id, idempotency_key, request_hash):
        return None

    def _fetch_product(self, where_clause, params, *, conn=None):
        return {"item_id": "1", "item_name": "물티슈", "quantity": 10}

    def _caregiver_exists(self, cur, caregiver_id):
        return True

    def _goal_pose_exists(self, cur, goal_pose_id):
        return True

    def _insert_delivery_task(self, cur, **kwargs):
        self.inserted_task_kwargs = kwargs
        return 101

    def _insert_delivery_detail(self, cur, **kwargs):
        self.inserted_detail_kwargs = kwargs

    def _insert_delivery_item(self, cur, **kwargs):
        self.inserted_item_kwargs = kwargs

    def _insert_initial_task_history(self, cur, *, task_id):
        self.history_task_id = task_id

    def _insert_initial_task_event(self, cur, *, task_id):
        self.event_task_id = task_id

    def _insert_idempotency_record(self, cur, **kwargs):
        self.idempotency_kwargs = kwargs


class FakeInsufficientItemRepository(FakeDeliveryRequestRepository):
    def _fetch_product(self, where_clause, params, *, conn=None):
        return {"item_id": "1", "item_name": "물티슈", "quantity": 0}


def test_create_delivery_task_uses_runtime_config_assigned_robot_id():
    fake_conn = FakeConnection()
    repository = FakeDeliveryRequestRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9")
    )

    with patch(
        "server.ropi_main_service.persistence.repositories.task_request_repository.get_connection",
        return_value=fake_conn,
    ):
        response = repository.create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=1,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes=None,
            idempotency_key="idem_001",
        )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 101
    assert response["assigned_robot_id"] == "pinky9"
    assert "assigned_pinky_id" not in response
    assert repository.inserted_task_kwargs["destination_goal_pose_id"] == "delivery_room_301"
    assert repository.inserted_detail_kwargs["destination_goal_pose_id"] == "delivery_room_301"
    assert repository.inserted_item_kwargs == {"task_id": 101, "item_id": 1, "quantity": 1}
    assert repository.history_task_id == 101
    assert repository.event_task_id == 101
    assert repository.idempotency_kwargs["task_id"] == 101
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_create_delivery_task_rejects_when_item_quantity_is_insufficient():
    fake_conn = FakeConnection()
    repository = FakeInsufficientItemRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9")
    )

    with patch(
        "server.ropi_main_service.persistence.repositories.task_request_repository.get_connection",
        return_value=fake_conn,
    ):
        response = repository.create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=2,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes=None,
            idempotency_key="idem_001",
        )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "ITEM_QUANTITY_INSUFFICIENT"
    assert fake_conn.rolled_back is True
    assert not hasattr(repository, "inserted_task_kwargs")


def test_find_idempotent_response_rejects_key_reuse_with_different_payload():
    response = DeliveryRequestRepository._find_idempotent_response(
        FakeExistingIdempotencyCursor(),
        requester_id="1",
        idempotency_key="idem_001",
        request_hash="expected_hash",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "IDEMPOTENCY_KEY_CONFLICT"
