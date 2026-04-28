import asyncio

from server.ropi_main_service.application.auth import AuthService
from server.ropi_main_service.application.caregiver import CaregiverService
from server.ropi_main_service.application.inventory import InventoryService
from server.ropi_main_service.application.patient import PatientService
from server.ropi_main_service.application.staff_call import StaffCallService
from server.ropi_main_service.application.task_request import DeliveryRequestService
from server.ropi_main_service.application.visitor_info import VisitorInfoService
from server.ropi_main_service.application.visit_guide import VisitGuideService
from server.ropi_main_service.application.visitor_register import VisitorRegisterService


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
                "task_id": 101,
                "task_type": "DELIVERY",
                "task_status": "WAITING_DISPATCH",
                "phase": "REQUESTED",
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

    async def async_add_quantity(self, item_id, quantity):
        self.added = (item_id, quantity)
        return True


class FakeAsyncDeliveryRequestRepository:
    async def async_get_all_products(self):
        return [{"item_name": "물티슈"}]

    async def async_create_delivery_request(self, **kwargs):
        self.created = kwargs
        return True, "물품 요청이 접수되었습니다."


class FakeAsyncStaffCallRepository:
    async def async_create_staff_call(self, call_type, detail, member_id=None):
        return True, "직원 호출 요청이 접수되었습니다."


class FakeAsyncVisitGuideRepository:
    async def async_find_patient(self, keyword):
        return {"name": "김환자", "member_id": 1, "room": "301"}

    async def async_create_robot_guide_event(self, patient_name, room_no, member_id=None):
        return True, "로봇 안내 요청이 접수되었습니다."


class FakeAsyncVisitorRegisterRepository:
    async def async_create_visitor_registration(self, **kwargs):
        self.created = kwargs
        return True, "방문 등록이 완료되었습니다."


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
    assert result["flow"]["READY"] == [
        {
            "event_id": 1,
            "task_id": 101,
            "task_type": "DELIVERY",
            "task_status": "WAITING_DISPATCH",
            "phase": "REQUESTED",
            "robot_id": "pinky2",
            "description": "accepted",
            "display_text": "#101 accepted / pinky2",
            "cancellable": True,
        }
    ]


def test_caregiver_flow_board_keeps_cancel_requested_in_running_lane():
    rows = [
        {
            "event_id": 2,
            "task_id": 102,
            "task_type": "DELIVERY",
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
            "robot_id": "pinky2",
            "description": "cancel requested",
        }
    ]

    flow = CaregiverService._format_flow_board_data(rows)

    assert flow["RUNNING"][0]["task_id"] == 102
    assert flow["RUNNING"][0]["task_status"] == "CANCEL_REQUESTED"
    assert flow["RUNNING"][0]["cancellable"] is False
    assert flow["DONE"] == []


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


def test_inventory_service_async_add_inventory():
    repository = FakeAsyncInventoryRepository()
    service = InventoryService(repository=repository)

    result = asyncio.run(service.async_add_inventory("물티슈", 2))

    assert result == (True, "재고가 추가되었습니다.")
    assert repository.added == ("1", 2)


def test_delivery_request_service_async_product_list_and_submit_request():
    repository = FakeAsyncDeliveryRequestRepository()
    service = DeliveryRequestService(repository=repository)

    names = asyncio.run(service.async_get_product_names())
    result = asyncio.run(
        service.async_submit_delivery_request(
            item_name="물티슈",
            quantity=1,
            destination="301호",
            priority="일반",
            detail="요청",
            member_id="1",
        )
    )

    assert names == ["물티슈"]
    assert result == (True, "물품 요청이 접수되었습니다.")
    assert repository.created["item_name"] == "물티슈"


def test_staff_call_service_async_submit_staff_call():
    service = StaffCallService(repository=FakeAsyncStaffCallRepository())

    result = asyncio.run(service.async_submit_staff_call("긴급", "도움 필요", member_id="1"))

    assert result == (True, "직원 호출 요청이 접수되었습니다.")


def test_visit_guide_service_async_search_and_start():
    service = VisitGuideService(repository=FakeAsyncVisitGuideRepository())

    search_result = asyncio.run(service.async_search_patient("김환자"))
    start_result = asyncio.run(
        service.async_start_robot_guide({"name": "김환자", "room": "301"}, member_id="1")
    )

    assert search_result == (
        True,
        "어르신 정보를 찾았습니다.",
        {"name": "김환자", "member_id": 1, "room": "301"},
    )
    assert start_result == (True, "로봇 안내 요청이 접수되었습니다.")


def test_visitor_register_service_async_submit_registration():
    repository = FakeAsyncVisitorRegisterRepository()
    service = VisitorRegisterService(repository=repository)

    result = asyncio.run(
        service.async_submit_registration(
            visitor_name="방문객",
            phone="010-1111-2222",
            patient_name="김환자",
            relation="가족",
            purpose="면회",
            member_id="1",
        )
    )

    assert result == (True, "방문 등록이 완료되었습니다.")
    assert repository.created["visitor_name"] == "방문객"
