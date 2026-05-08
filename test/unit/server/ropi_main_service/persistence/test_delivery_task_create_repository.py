import asyncio

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.persistence.repositories.delivery_task_create_repository import (
    DELIVERY_CREATE_SCOPE,
    DeliveryTaskCreateRepository,
)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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


class FakeAsyncTransaction:
    def __init__(self):
        self.cursor = FakeCursor()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class FakeIdempotencyRepository:
    def __init__(self):
        self.find_args = None
        self.inserted = None

    def build_request_hash(self, **payload):
        self.hash_payload = payload
        return "delivery_request_hash"

    def find_response(self, cur, **kwargs):
        self.find_args = kwargs
        return None

    async def async_find_response(self, cur, **kwargs):
        self.find_args = kwargs
        return None

    def insert_record(self, cur, **kwargs):
        self.inserted = kwargs

    async def async_insert_record(self, cur, **kwargs):
        self.inserted = kwargs


class FakeDeliveryTaskRepository:
    def __init__(self):
        self.created = None

    def create_delivery_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 101

    async def async_create_delivery_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 101


def _product(quantity=10):
    return {"item_id": 1, "item_name": "물티슈", "quantity": quantity}


def test_delivery_task_create_repository_creates_sync_delivery_task_records():
    fake_conn = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = DeliveryTaskCreateRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        delivery_task_repository=delivery_task_repository,
        idempotency_repository=idempotency_repository,
        connection_factory=lambda: fake_conn,
        fetch_product_by_id=lambda cur, item_id, conn=None: _product(),
        caregiver_exists=lambda cur, caregiver_id: True,
        goal_pose_exists=lambda cur, goal_pose_id: True,
    )

    response = repository.create_delivery_task(
        request_id="req_001",
        caregiver_id="caregiver-1",
        item_id="item-1",
        quantity=2,
        destination_id="delivery_room_301",
        priority="NORMAL",
        notes="note",
        idempotency_key="idem_001",
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": 101,
        "task_status": "WAITING_DISPATCH",
        "assigned_robot_id": "pinky9",
    }
    assert delivery_task_repository.created == {
        "request_id": "req_001",
        "idempotency_key": "idem_001",
        "caregiver_id": 1,
        "priority": "NORMAL",
        "destination_goal_pose_id": "delivery_room_301",
        "notes": "note",
        "item_id": 1,
        "quantity": 2,
    }
    assert idempotency_repository.find_args["scope"] == DELIVERY_CREATE_SCOPE
    assert idempotency_repository.inserted["scope"] == DELIVERY_CREATE_SCOPE
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_delivery_task_create_repository_creates_async_delivery_task_records():
    fake_transaction = FakeAsyncTransaction()
    idempotency_repository = FakeIdempotencyRepository()
    delivery_task_repository = FakeDeliveryTaskRepository()

    async def async_fetch_product_by_id(cur, item_id):
        return _product()

    async def async_caregiver_exists(cur, caregiver_id):
        return True

    async def async_goal_pose_exists(cur, goal_pose_id):
        return True

    repository = DeliveryTaskCreateRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        delivery_task_repository=delivery_task_repository,
        idempotency_repository=idempotency_repository,
        async_transaction_factory=lambda: fake_transaction,
        async_fetch_product_by_id=async_fetch_product_by_id,
        async_caregiver_exists=async_caregiver_exists,
        async_goal_pose_exists=async_goal_pose_exists,
    )

    response = asyncio.run(
        repository.async_create_delivery_task(
            request_id="req_001",
            caregiver_id=1,
            item_id=1,
            quantity=2,
            destination_id="delivery_room_301",
            priority="URGENT",
            notes=None,
            idempotency_key="idem_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["assigned_robot_id"] == "pinky9"
    assert delivery_task_repository.created["priority"] == "URGENT"
    assert delivery_task_repository.created["quantity"] == 2
    assert idempotency_repository.inserted["task_id"] == 101
    assert fake_transaction.entered is True
    assert fake_transaction.exited is True


def test_delivery_task_create_repository_rejects_insufficient_quantity():
    fake_conn = FakeConnection()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = DeliveryTaskCreateRepository(
        delivery_task_repository=delivery_task_repository,
        idempotency_repository=FakeIdempotencyRepository(),
        connection_factory=lambda: fake_conn,
        fetch_product_by_id=lambda cur, item_id, conn=None: _product(quantity=1),
        caregiver_exists=lambda cur, caregiver_id: True,
        goal_pose_exists=lambda cur, goal_pose_id: True,
    )

    response = repository.create_delivery_task(
        request_id="req_001",
        caregiver_id=1,
        item_id=1,
        quantity=2,
        destination_id="delivery_room_301",
        priority="NORMAL",
        notes=None,
        idempotency_key="idem_001",
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "ITEM_QUANTITY_INSUFFICIENT"
    assert delivery_task_repository.created is None
    assert fake_conn.rolled_back is True
