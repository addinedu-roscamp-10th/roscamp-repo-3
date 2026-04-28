from unittest.mock import patch
import asyncio

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.repositories.delivery_task_repository import (
    DeliveryTaskRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    DeliveryRequestRepository,
)


class FakeCursor:
    lastrowid = 101

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeAsyncCursor:
    lastrowid = 101


class FakeAsyncTransaction:
    def __init__(self):
        self.cursor = FakeAsyncCursor()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class RecordingAsyncCursor:
    lastrowid = 101

    def __init__(self, row=None):
        self.calls = []
        self.row = row

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        return self.row


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


class FakeIdempotencyRepository:
    def __init__(self):
        self.inserted = None

    def build_request_hash(self, **payload):
        self.hash_payload = payload
        return "request_hash"

    def find_response(self, cur, *, requester_id, idempotency_key, request_hash):
        self.find_args = {
            "requester_id": requester_id,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
        }
        return None

    def insert_record(self, cur, **kwargs):
        self.inserted = kwargs

    async def async_find_response(self, cur, *, requester_id, idempotency_key, request_hash):
        self.find_args = {
            "requester_id": requester_id,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
        }
        return None

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


class CollaboratorBackedDeliveryRequestRepository(DeliveryRequestRepository):
    def _fetch_product(self, where_clause, params, *, conn=None):
        return {"item_id": "1", "item_name": "물티슈", "quantity": 10}

    def _caregiver_exists(self, cur, caregiver_id):
        return True

    def _goal_pose_exists(self, cur, goal_pose_id):
        return True

    async def _async_fetch_product_by_id(self, cur, item_id):
        return {"item_id": "1", "item_name": "물티슈", "quantity": 10}

    async def _async_caregiver_exists(self, cur, caregiver_id):
        return True

    async def _async_goal_pose_exists(self, cur, goal_pose_id):
        return True


class AsyncInsufficientItemRepository(CollaboratorBackedDeliveryRequestRepository):
    async def _async_fetch_product_by_id(self, cur, item_id):
        return {"item_id": "1", "item_name": "물티슈", "quantity": 0}


def test_create_delivery_task_delegates_persistence_to_collaborators():
    fake_conn = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = CollaboratorBackedDeliveryRequestRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        idempotency_repository=idempotency_repository,
        delivery_task_repository=delivery_task_repository,
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
            notes="note",
            idempotency_key="idem_001",
        )

    assert response["result_code"] == "ACCEPTED"
    assert delivery_task_repository.created["item_id"] == 1
    assert delivery_task_repository.created["destination_goal_pose_id"] == "delivery_room_301"
    assert idempotency_repository.find_args == {
        "requester_id": "1",
        "idempotency_key": "idem_001",
        "request_hash": "request_hash",
    }
    assert idempotency_repository.inserted["task_id"] == 101
    assert fake_conn.committed is True


def test_async_create_delivery_task_delegates_persistence_to_collaborators(monkeypatch):
    fake_transaction = FakeAsyncTransaction()
    idempotency_repository = FakeIdempotencyRepository()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = CollaboratorBackedDeliveryRequestRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        idempotency_repository=idempotency_repository,
        delivery_task_repository=delivery_task_repository,
    )

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        repository.async_create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=1,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes="note",
            idempotency_key="idem_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 101
    assert response["assigned_robot_id"] == "pinky9"
    assert delivery_task_repository.created["item_id"] == 1
    assert delivery_task_repository.created["destination_goal_pose_id"] == "delivery_room_301"
    assert idempotency_repository.find_args == {
        "requester_id": "1",
        "idempotency_key": "idem_001",
        "request_hash": "request_hash",
    }
    assert idempotency_repository.inserted["task_id"] == 101
    assert fake_transaction.entered is True
    assert fake_transaction.exited is True


def test_create_delivery_task_uses_runtime_config_assigned_robot_id():
    fake_conn = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = FakeDeliveryRequestRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        idempotency_repository=idempotency_repository,
        delivery_task_repository=delivery_task_repository,
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
    assert delivery_task_repository.created["destination_goal_pose_id"] == "delivery_room_301"
    assert delivery_task_repository.created["item_id"] == 1
    assert delivery_task_repository.created["quantity"] == 1
    assert idempotency_repository.inserted["task_id"] == 101
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_create_delivery_task_rejects_when_item_quantity_is_insufficient():
    fake_conn = FakeConnection()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = FakeInsufficientItemRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        idempotency_repository=FakeIdempotencyRepository(),
        delivery_task_repository=delivery_task_repository,
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
    assert delivery_task_repository.created is None


def test_async_create_delivery_task_rejects_when_item_quantity_is_insufficient(monkeypatch):
    fake_transaction = FakeAsyncTransaction()
    delivery_task_repository = FakeDeliveryTaskRepository()
    repository = AsyncInsufficientItemRepository(
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        idempotency_repository=FakeIdempotencyRepository(),
        delivery_task_repository=delivery_task_repository,
    )

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        repository.async_create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=2,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes=None,
            idempotency_key="idem_001",
        )
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "ITEM_QUANTITY_INSUFFICIENT"
    assert delivery_task_repository.created is None


def test_async_get_delivery_task_cancel_target_rejects_terminal_task(monkeypatch):
    async def fake_fetch_one(query, params):
        return {
            "task_id": 101,
            "task_status": "COMPLETED",
            "phase": "COMPLETED",
            "assigned_robot_id": "pinky2",
        }

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_fetch_one",
        fake_fetch_one,
    )

    response = asyncio.run(
        DeliveryRequestRepository().async_get_delivery_task_cancel_target("101")
    )

    assert response == {
        "result_code": "REJECTED",
        "result_message": "이미 종료되었거나 취소할 수 없는 운반 task입니다.",
        "reason_code": "TASK_NOT_CANCELLABLE",
        "task_id": 101,
        "task_status": "COMPLETED",
        "assigned_robot_id": "pinky2",
    }


def test_async_get_delivery_task_cancel_target_rejects_missing_task(monkeypatch):
    async def fake_fetch_one(query, params):
        return None

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_fetch_one",
        fake_fetch_one,
    )

    response = asyncio.run(
        DeliveryRequestRepository().async_get_delivery_task_cancel_target("999")
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_NOT_FOUND"
    assert response["task_id"] == 999


def test_async_record_delivery_task_cancel_result_updates_status_history_and_event(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "DELIVERY_PICKUP",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        DeliveryRequestRepository().async_record_delivery_task_cancel_result(
            task_id="101",
            cancel_response={
                "result_code": "CANCEL_REQUESTED",
                "result_message": "action cancel request was accepted.",
                "cancel_requested": True,
            },
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert response["assigned_robot_id"] == "pinky2"
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in cursor.calls[0][0]
    assert "UPDATE task" in cursor.calls[1][0]
    assert "INSERT INTO task_state_history" in cursor.calls[2][0]
    assert "INSERT INTO task_event_log" in cursor.calls[3][0]
    assert cursor.calls[1][1][0:3] == (
        "USER_CANCEL_REQUESTED",
        "CANCEL_REQUESTED",
        "action cancel request was accepted.",
    )


def test_async_record_delivery_task_cancel_result_logs_rejection_without_status_update(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "DELIVERY_PICKUP",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        DeliveryRequestRepository().async_record_delivery_task_cancel_result(
            task_id="101",
            cancel_response={
                "result_code": "NOT_FOUND",
                "result_message": "matching active action goal was not found.",
                "cancel_requested": False,
            },
        )
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["task_status"] == "RUNNING"
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "INSERT",
    ]
    assert "INSERT INTO task_event_log" in cursor.calls[1][0]
    assert cursor.calls[1][1][1:4] == (
        "DELIVERY_TASK_CANCEL_REJECTED",
        "WARNING",
        "pinky2",
    )


def test_async_record_delivery_task_cancelled_result_finalizes_cancel_requested_task(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.task_request_repository.async_transaction",
        lambda: fake_transaction,
    )

    workflow_response = {
        "result_code": "FAILED",
        "result_message": "goal canceled by user request.",
        "status": 5,
    }
    response = asyncio.run(
        DeliveryRequestRepository().async_record_delivery_task_cancelled_result(
            task_id="101",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "CANCELLED"
    assert response["reason_code"] == "ROS_ACTION_CANCELLED"
    assert response["task_status"] == "CANCELLED"
    assert response["assigned_robot_id"] == "pinky2"
    assert response["workflow_result"] == workflow_response
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in cursor.calls[0][0]
    assert "UPDATE task" in cursor.calls[1][0]
    assert "INSERT INTO task_state_history" in cursor.calls[2][0]
    assert "INSERT INTO task_event_log" in cursor.calls[3][0]
    assert cursor.calls[1][1][0:3] == (
        "ROS_ACTION_CANCELLED",
        "CANCELLED",
        "goal canceled by user request.",
    )
    assert cursor.calls[3][1][1:7] == (
        "DELIVERY_TASK_CANCELLED",
        "INFO",
        "pinky2",
        "CANCELLED",
        "ROS_ACTION_CANCELLED",
        "goal canceled by user request.",
    )


def test_find_idempotent_response_rejects_key_reuse_with_different_payload():
    response = IdempotencyRepository().find_response(
        FakeExistingIdempotencyCursor(),
        requester_id="1",
        idempotency_key="idem_001",
        request_hash="expected_hash",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_async_find_idempotent_response_rejects_key_reuse_with_different_payload():
    cursor = RecordingAsyncCursor(
        row={
            "request_hash": "different_hash",
            "response_json": '{"result_code":"ACCEPTED"}',
        }
    )

    response = asyncio.run(
        IdempotencyRepository().async_find_response(
            cursor,
            requester_id="1",
            idempotency_key="idem_001",
            request_hash="expected_hash",
        )
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert "FROM idempotency_record" in cursor.calls[0][0]


def test_async_delivery_task_repository_inserts_records_in_order():
    cursor = RecordingAsyncCursor()
    repository = DeliveryTaskRepository(
        runtime_config=DeliveryRuntimeConfig(
            pinky_id="pinky9",
            pickup_arm_robot_id="jetcobot1",
            destination_arm_robot_id="jetcobot2",
            robot_slot_id="slot_a",
        )
    )

    task_id = asyncio.run(
        repository.async_create_delivery_task_records(
            cursor,
            request_id="req_001",
            idempotency_key="idem_001",
            caregiver_id=1,
            priority="NORMAL",
            destination_goal_pose_id="delivery_room_301",
            notes="note",
            item_id=1,
            quantity=2,
        )
    )

    assert task_id == 101
    assert [call[0].split()[2] for call in cursor.calls[:5]] == [
        "task",
        "delivery_task_detail",
        "delivery_task_item",
        "task_state_history",
        "task_event_log",
    ]
    assert cursor.calls[0][1][4] == "pinky9"
    assert cursor.calls[1][1][3:6] == ("jetcobot1", "jetcobot2", "slot_a")
