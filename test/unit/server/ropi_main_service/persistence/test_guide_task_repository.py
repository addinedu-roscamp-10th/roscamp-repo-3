import asyncio

from server.ropi_main_service.persistence.repositories.guide_task_repository import (
    GUIDE_CREATE_SCOPE,
    GuideTaskRepository,
)


class FakeAsyncCursor:
    def __init__(self):
        self.calls = []
        self.lastrowid = 3001
        self._last_query = ""

    async def execute(self, query, params=None):
        self.calls.append((query, params))
        self._last_query = query

    async def fetchone(self):
        if "FROM visitor" in self._last_query:
            return {
                "visitor_id": 1,
                "visitor_name": "김민수",
                "relation_name": "아들",
                "member_id": 7,
                "member_name": "김영수",
                "room_no": "301",
            }
        if "FROM goal_pose" in self._last_query:
            return {
                "goal_pose_id": "delivery_room_301",
                "map_id": "map_test11_0423",
                "zone_id": "room_301",
                "zone_name": "301호",
                "purpose": "DESTINATION",
            }
        return None


class FakeSyncCursor:
    def __init__(self):
        self.calls = []
        self.lastrowid = 3001
        self._last_query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        self._last_query = query

    def fetchone(self):
        if "FROM visitor" in self._last_query:
            return {
                "visitor_id": 1,
                "visitor_name": "김민수",
                "relation_name": "아들",
                "member_id": 7,
                "member_name": "김영수",
                "room_no": "301",
            }
        if "FROM goal_pose" in self._last_query:
            return {
                "goal_pose_id": "delivery_room_301",
                "map_id": "map_test11_0423",
                "zone_id": "room_301",
                "zone_name": "301호",
                "purpose": "DESTINATION",
            }
        return None


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeSyncCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def begin(self):
        pass

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


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


class FakeIdempotencyRepository:
    def __init__(self):
        self.find_args = None
        self.inserted = None

    def build_request_hash(self, **payload):
        self.hash_payload = payload
        return "guide_request_hash"

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


def test_create_guide_task_writes_records_in_transaction():
    connection = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    repository = GuideTaskRepository(
        idempotency_repository=idempotency_repository,
        connection_factory=lambda: connection,
        default_pinky_id="pinky1",
    )

    response = repository.create_guide_task(
        request_id="req_guide_001",
        visitor_id=1,
        priority="NORMAL",
        idempotency_key="idem_guide_001",
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert idempotency_repository.find_args["requester_type"] == "VISITOR"
    assert idempotency_repository.inserted["task_id"] == 3001
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert connection.cursor_instance.calls[2][1] == (
        "req_guide_001",
        "idem_guide_001",
        "1",
        "NORMAL",
        "pinky1",
        "map_test11_0423",
    )


def test_async_create_guide_task_writes_task_detail_history_and_event():
    transaction = FakeAsyncTransaction()
    idempotency_repository = FakeIdempotencyRepository()
    repository = GuideTaskRepository(
        idempotency_repository=idempotency_repository,
        async_transaction_factory=lambda: transaction,
        default_pinky_id="pinky1",
    )

    response = asyncio.run(
        repository.async_create_guide_task(
            request_id="req_guide_001",
            visitor_id=1,
            priority="NORMAL",
            idempotency_key="idem_guide_001",
        )
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": "안내 요청이 접수되었습니다.",
        "reason_code": None,
        "task_id": 3001,
        "task_status": "WAITING_DISPATCH",
        "phase": "WAIT_GUIDE_START_CONFIRM",
        "assigned_robot_id": "pinky1",
        "visitor_id": 1,
        "visitor_name": "김민수",
        "relation_name": "아들",
        "member_id": 7,
        "resident_name": "김영수",
        "room_no": "301",
        "destination_id": "delivery_room_301",
        "destination_map_id": "map_test11_0423",
        "destination_zone_id": "room_301",
        "destination_zone_name": "301호",
        "destination_purpose": "DESTINATION",
    }
    assert idempotency_repository.find_args["scope"] == GUIDE_CREATE_SCOPE
    assert idempotency_repository.find_args["requester_type"] == "VISITOR"
    assert idempotency_repository.inserted["scope"] == GUIDE_CREATE_SCOPE
    assert idempotency_repository.inserted["requester_type"] == "VISITOR"
    assert [call[0].split()[2] for call in transaction.cursor.calls[2:6]] == [
        "task",
        "guide_task_detail",
        "task_state_history",
        "task_event_log",
    ]


def test_async_create_guide_task_rejects_missing_destination_goal_pose():
    class MissingDestinationCursor(FakeAsyncCursor):
        async def fetchone(self):
            if "FROM visitor" in self._last_query:
                return {
                    "visitor_id": 1,
                    "visitor_name": "김민수",
                    "relation_name": "아들",
                    "member_id": 7,
                    "member_name": "김영수",
                    "room_no": "306",
                }
            if "FROM goal_pose" in self._last_query:
                return None
            return None

    transaction = FakeAsyncTransaction()
    transaction.cursor = MissingDestinationCursor()
    repository = GuideTaskRepository(
        idempotency_repository=FakeIdempotencyRepository(),
        async_transaction_factory=lambda: transaction,
    )

    response = asyncio.run(
        repository.async_create_guide_task(
            request_id="req_guide_001",
            visitor_id=1,
            priority="NORMAL",
            idempotency_key="idem_guide_001",
        )
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_DESTINATION_NOT_CONFIGURED"
