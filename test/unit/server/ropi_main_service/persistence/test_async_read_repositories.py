import asyncio

from server.ropi_main_service.persistence.repositories import caregiver_repository
from server.ropi_main_service.persistence.repositories import inventory_repository
from server.ropi_main_service.persistence.repositories import patient_repository
from server.ropi_main_service.persistence.repositories import user_repository
from server.ropi_main_service.persistence.repositories import visitor_info_repository


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
