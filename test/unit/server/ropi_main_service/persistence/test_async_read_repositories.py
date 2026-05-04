import asyncio

from server.ropi_main_service.persistence.repositories import caregiver_repository
from server.ropi_main_service.persistence.repositories import inventory_repository
from server.ropi_main_service.persistence.repositories import patient_repository
from server.ropi_main_service.persistence.repositories import staff_call_repository
from server.ropi_main_service.persistence.repositories import (
    delivery_request_event_repository,
)
from server.ropi_main_service.persistence.repositories import task_request_repository
from server.ropi_main_service.persistence.repositories import (
    task_request_lookup_repository,
)
from server.ropi_main_service.persistence.repositories import user_repository
from server.ropi_main_service.persistence.repositories import visit_guide_repository
from server.ropi_main_service.persistence.repositories import visitor_info_repository
from server.ropi_main_service.persistence.repositories import visitor_register_repository


def test_user_repository_async_login_uses_async_fetch_one(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"user_id": "1"}

    monkeypatch.setattr(user_repository, "async_fetch_one", fake_async_fetch_one)

    row = asyncio.run(
        user_repository.UserRepository().async_find_user_for_login("1", "caregiver")
    )

    assert row == {"user_id": "1"}
    assert "FROM caregiver" in calls[0][0]
    assert calls[0][1] == ("1",)


def test_caregiver_repository_async_dashboard_uses_async_fetch_one(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"available_robot_count": 2}

    monkeypatch.setattr(caregiver_repository, "async_fetch_one", fake_async_fetch_one)

    row = asyncio.run(
        caregiver_repository.CaregiverRepository().async_get_dashboard_summary()
    )

    assert row == {"available_robot_count": 2}
    assert "FROM robot_runtime_status" in calls[0][0]


def test_caregiver_repository_async_timeline_uses_async_fetch_all(monkeypatch):
    calls = []

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [{"event_name": "DELIVERY_TASK_ACCEPTED"}]

    monkeypatch.setattr(caregiver_repository, "async_fetch_all", fake_async_fetch_all)

    rows = asyncio.run(
        caregiver_repository.CaregiverRepository().async_get_timeline(limit=10)
    )

    assert rows == [{"event_name": "DELIVERY_TASK_ACCEPTED"}]
    assert "FROM task_event_log" in calls[0][0]
    assert calls[0][1] == (10,)


def test_caregiver_repository_async_alert_logs_use_partial_text_filters(monkeypatch):
    calls = []

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [{"event_id": 11}]

    monkeypatch.setattr(caregiver_repository, "async_fetch_all", fake_async_fetch_all)

    rows = asyncio.run(
        caregiver_repository.CaregiverRepository().async_get_alert_logs(
            period_start=None,
            severity=None,
            source_component="Control",
            task_id="1001",
            robot_id="pinky",
            event_type="TASK",
            limit=25,
        )
    )

    assert rows == [{"event_id": 11}]
    assert "tel.component LIKE" in calls[0][0]
    assert "tel.robot_id LIKE" in calls[0][0]
    assert "tel.event_name LIKE" in calls[0][0]
    assert "tel.task_id = %s" in calls[0][0]
    assert calls[0][1] == (
        None,
        None,
        None,
        None,
        "Control",
        "Control",
        "1001",
        "1001",
        "pinky",
        "pinky",
        "TASK",
        "TASK",
        25,
    )


def test_patient_repository_async_member_lookup_uses_async_fetch_one(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"member_id": 1}

    monkeypatch.setattr(patient_repository, "async_fetch_one", fake_async_fetch_one)

    row = asyncio.run(
        patient_repository.PatientRepository().async_find_member_by_name_and_room(
            "김환자",
            "301",
        )
    )

    assert row == {"member_id": 1}
    assert "FROM member" in calls[0][0]
    assert calls[0][1] == ("김환자", "301")


def test_patient_repository_async_candidates_use_partial_filters(monkeypatch):
    calls = []

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [{"member_id": 1}]

    monkeypatch.setattr(patient_repository, "async_fetch_all", fake_async_fetch_all)

    rows = asyncio.run(
        patient_repository.PatientRepository().async_list_member_candidates(
            name="김",
            room_no="",
            limit=7,
        )
    )

    assert rows == [{"member_id": 1}]
    assert "LIKE" in calls[0][0]
    assert "LIMIT %s" in calls[0][0]
    assert calls[0][1] == ("김", "김", "", "", 7)


def test_patient_repository_async_member_lookup_by_id_uses_async_fetch_one(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"member_id": 1}

    monkeypatch.setattr(patient_repository, "async_fetch_one", fake_async_fetch_one)

    row = asyncio.run(patient_repository.PatientRepository().async_find_member_by_id(1))

    assert row == {"member_id": 1}
    assert "WHERE member_id = %s" in calls[0][0]
    assert calls[0][1] == (1,)


def test_visitor_info_repository_async_visit_info_uses_async_fetch_one(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"name": "김환자", "room": "301"}

    monkeypatch.setattr(visitor_info_repository, "async_fetch_one", fake_async_fetch_one)

    row = asyncio.run(
        visitor_info_repository.VisitorInfoRepository().async_get_visitor_patient_info(
            "김환자"
        )
    )

    assert row["name"] == "김환자"
    assert "FROM member m" in calls[0][0]
    assert calls[0][1] == ("%김환자%", "%김환자%")


def test_inventory_repository_async_list_uses_async_fetch_all(monkeypatch):
    calls = []

    async def fake_async_fetch_all(query, params=None):
        calls.append((query, params))
        return [{"item_id": "1"}]

    monkeypatch.setattr(inventory_repository, "async_fetch_all", fake_async_fetch_all)

    rows = asyncio.run(inventory_repository.InventoryRepository().async_get_all_products())

    assert rows == [{"item_id": "1"}]
    assert "FROM item" in calls[0][0]


def test_inventory_repository_async_add_quantity_uses_async_execute(monkeypatch):
    calls = []

    async def fake_async_execute(query, params=None):
        calls.append((query, params))
        return 1

    monkeypatch.setattr(inventory_repository, "async_execute", fake_async_execute)

    updated = asyncio.run(
        inventory_repository.InventoryRepository().async_add_quantity("1", 3)
    )

    assert updated is True
    assert "UPDATE item" in calls[0][0]
    assert calls[0][1] == (3, "1")


def test_inventory_repository_async_set_quantity_uses_async_execute(monkeypatch):
    calls = []

    async def fake_async_execute(query, params=None):
        calls.append((query, params))
        return 1

    monkeypatch.setattr(inventory_repository, "async_execute", fake_async_execute)

    updated = asyncio.run(
        inventory_repository.InventoryRepository().async_set_quantity("1", 12)
    )

    assert updated is True
    assert "UPDATE item" in calls[0][0]
    assert "quantity = %s" in calls[0][0]
    assert calls[0][1] == (12, "1")


def test_staff_call_repository_async_create_uses_staff_call_transaction(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.lastrowid = 9102
            self._last_query = ""

        async def execute(self, query, params=None):
            self.calls.append((query, params))
            self._last_query = query

        async def fetchone(self):
            if "FROM idempotency_record" in self._last_query:
                return None
            if "FROM member" in self._last_query:
                return {"member_id": 7, "member_name": "김영수", "room_no": "301"}
            return None

    class FakeTransaction:
        def __init__(self):
            self.cursor = FakeCursor()

        async def __aenter__(self):
            return self.cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_transaction = FakeTransaction()
    monkeypatch.setattr(
        staff_call_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        staff_call_repository.StaffCallRepository().async_create_staff_call(
            "긴급",
            "도움 필요",
            member_id="7",
        )
    )

    assert result["result_code"] == "ACCEPTED"
    assert result["call_id"] == "member_event_9102"
    event_params = next(
        params
        for query, params in fake_transaction.cursor.calls
        if "INSERT INTO member_event" in query
    )
    assert event_params[0] == 7
    assert event_params[1] == "STAFF_CALL"


def test_task_request_repository_async_create_delivery_request_uses_member_event(monkeypatch):
    fetch_calls = []
    execute_calls = []

    async def fake_async_fetch_one(query, params=None):
        fetch_calls.append((query, params))
        return {"item_id": "1", "item_name": "물티슈", "quantity": 10}

    async def fake_async_execute(query, params=None):
        execute_calls.append((query, params))
        return 1

    monkeypatch.setattr(
        task_request_lookup_repository,
        "async_fetch_one",
        fake_async_fetch_one,
    )
    monkeypatch.setattr(
        delivery_request_event_repository,
        "async_execute",
        fake_async_execute,
    )

    result = asyncio.run(
        task_request_repository.DeliveryRequestRepository().async_create_delivery_request(
            item_name="물티슈",
            quantity=2,
            destination="301호",
            priority="일반",
            detail="요청",
            member_id="7",
        )
    )

    assert result == (True, "물품 요청이 접수되었습니다.")
    assert "FROM item" in fetch_calls[0][0]
    assert "INSERT INTO member_event" in execute_calls[0][0]
    assert execute_calls[0][1][0] == 7
    assert execute_calls[0][1][1] == "DELIVERY_REQUESTED"


def test_visit_guide_repository_async_find_patient_and_create_event(monkeypatch):
    fetch_calls = []
    execute_calls = []

    async def fake_async_fetch_one(query, params=None):
        fetch_calls.append((query, params))
        return {"patient_name": "김환자", "member_id": 8, "room_no": "301"}

    async def fake_async_execute(query, params=None):
        execute_calls.append((query, params))
        return 1

    monkeypatch.setattr(visit_guide_repository, "async_fetch_one", fake_async_fetch_one)
    monkeypatch.setattr(visit_guide_repository, "async_execute", fake_async_execute)

    repository = visit_guide_repository.VisitGuideRepository()
    patient = asyncio.run(repository.async_find_patient("김환자"))
    result = asyncio.run(
        repository.async_create_robot_guide_event("김환자", "301", member_id="8")
    )

    assert patient["name"] == "김환자"
    assert fetch_calls[0][1] == ("%김환자%", "%김환자%")
    assert result == (True, "로봇 안내 요청이 접수되었습니다.")
    assert execute_calls[0][1][0] == 8
    assert execute_calls[0][1][1] == "GUIDE_REQUESTED"


def test_visitor_register_repository_async_create_uses_transaction(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []

        async def execute(self, query, params=None):
            self.calls.append((query, params))

        async def fetchone(self):
            return {"member_id": 9}

    class FakeTransaction:
        def __init__(self):
            self.cursor = FakeCursor()

        async def __aenter__(self):
            return self.cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_transaction = FakeTransaction()
    monkeypatch.setattr(
        visitor_register_repository,
        "async_transaction",
        lambda: fake_transaction,
    )

    result = asyncio.run(
        visitor_register_repository.VisitorRegisterRepository().async_create_visitor_registration(
            visitor_name="방문객",
            phone="010-1111-2222",
            patient_name="김환자",
            relation="가족",
            purpose="면회",
        )
    )

    assert result == (True, "방문 등록이 완료되었습니다.")
    assert "SELECT member_id" in fake_transaction.cursor.calls[0][0]
    assert "INSERT INTO member_event" in fake_transaction.cursor.calls[1][0]
    assert fake_transaction.cursor.calls[1][1][0] == 9
    assert fake_transaction.cursor.calls[1][1][1] == "VISIT_CHECKIN"
