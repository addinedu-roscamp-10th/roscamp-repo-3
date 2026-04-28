import asyncio

from server.ropi_main_service.application.auth import AuthService
from server.ropi_main_service.application.caregiver import CaregiverService
from server.ropi_main_service.application.inventory import InventoryService
from server.ropi_main_service.application.patient import PatientService
from server.ropi_main_service.application.visitor_info import VisitorInfoService


class FakeAsyncUserRepository:
    async def async_find_user_for_login(self, login_id, role):
        return {
            "user_id": login_id,
            "user_password": "1234",
            "user_name": "최보호",
        }


class FakeAsyncCaregiverRepository:
    async def async_get_dashboard_summary(self):
        return {
            "available_robot_count": 2,
            "waiting_job_count": 3,
            "running_job_count": 1,
        }

    async def async_get_robot_board(self):
        return [
            {
                "robot_id": "pinky2",
                "robot_status": "IDLE",
                "current_location": "x=1.0, y=2.0",
                "battery_percent": 90,
                "current_task_phase": None,
                "current_task_status": None,
            }
        ]

    async def async_get_timeline(self, limit=20):
        return [
            {
                "timeline_time": "12:00:00",
                "work_id": 1,
                "event_name": "DELIVERY_TASK_ACCEPTED",
                "detail": "accepted",
            }
        ]

    async def async_get_flow_board_events(self, limit=50):
        return [
            {
                "event_id": 1,
                "robot_id": "pinky2",
                "description": "accepted",
                "event_type": "WAITING_DISPATCH",
            }
        ]


class FakeAsyncPatientRepository:
    async def async_find_member_by_name_and_room(self, name, room_no):
        return {
            "member_id": 1,
            "member_name": name,
            "room_no": room_no,
            "admission_date": "2026-04-01",
        }

    async def async_get_recent_events(self, member_id, limit=20):
        return [{"event_at": "2026-04-28T10:00:00", "description": "식사 완료"}]

    async def async_get_preference(self, member_id):
        return {"preference": "창가 자리", "dislike": "매운 음식", "comment": "천천히 안내"}

    async def async_get_prescriptions(self, member_id):
        return [{"image_path": "/tmp/prescription.png"}]


class FakeAsyncVisitorInfoRepository:
    async def async_get_visitor_patient_info(self, keyword):
        return {"name": "김환자", "room": "301"}


class FakeAsyncInventoryRepository:
    async def async_get_all_products(self):
        return [{"item_id": "1", "item_name": "물티슈"}]


def test_auth_service_async_authenticate_uses_async_repository():
    service = AuthService(repository=FakeAsyncUserRepository())

    ok, result = asyncio.run(
        service.async_authenticate("1", "1234", "caregiver")
    )

    assert ok is True
    assert result == {
        "user_id": "1",
        "name": "최보호",
        "role": "caregiver",
    }


def test_caregiver_service_async_methods_keep_response_shape():
    service = CaregiverService(repository=FakeAsyncCaregiverRepository())

    async def scenario():
        return {
            "summary": await service.async_get_dashboard_summary(),
            "robots": await service.async_get_robot_board_data(),
            "timeline": await service.async_get_timeline_data(),
            "flow": await service.async_get_flow_board_data(),
        }

    result = asyncio.run(scenario())

    assert result["summary"] == {
        "available_robot_count": 2,
        "waiting_job_count": 3,
        "running_job_count": 1,
    }
    assert result["robots"][0]["robot_name"] == "pinky2"
    assert result["robots"][0]["chip_type"] == "green"
    assert result["timeline"] == [["12:00:00", "1", "DELIVERY_TASK_ACCEPTED", "accepted"]]
    assert result["flow"]["READY"] == ["#1 accepted / pinky2"]


def test_patient_service_async_search_keeps_response_shape():
    service = PatientService(repository=FakeAsyncPatientRepository())

    result = asyncio.run(service.async_search_patient_info("김환자", "301"))

    assert result["member_id"] == 1
    assert result["name"] == "김환자"
    assert result["preference"] == "창가 자리"
    assert result["events"] == [
        {"event_at": "2026-04-28T10:00:00", "description": "식사 완료"}
    ]
    assert result["prescription_paths"] == ["/tmp/prescription.png"]


def test_visitor_info_service_async_get_patient_visit_info():
    service = VisitorInfoService(repository=FakeAsyncVisitorInfoRepository())

    result = asyncio.run(service.async_get_patient_visit_info("김환자"))

    assert result == (True, "면회 정보를 조회했습니다.", {"name": "김환자", "room": "301"})


def test_inventory_service_async_get_inventory_rows():
    service = InventoryService(repository=FakeAsyncInventoryRepository())

    rows = asyncio.run(service.async_get_inventory_rows())

    assert rows == [{"item_id": "1", "item_name": "물티슈"}]
