import asyncio
from datetime import datetime

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
            "total_robot_count": 5,
            "waiting_job_count": 3,
            "running_job_count": 1,
            "warning_error_count": 4,
        }

    async def async_get_robot_board(self):
        return [
            {
                "robot_id": "pinky2",
                "robot_type_name": "MOBILE",
                "robot_status": "IDLE",
                "current_location": "x=1.0, y=2.0",
                "battery_percent": 90,
                "current_task_id": 101,
                "current_task_phase": None,
                "current_task_status": None,
                "last_seen_at": "2026-05-03T12:00:00",
                "last_seen_age_sec": 5,
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
    def __init__(self):
        self.rows = [
            {
                "item_id": "1",
                "item_type": "생활용품",
                "item_name": "기저귀",
                "quantity": 0,
                "updated_at": "2026-05-03T10:00:00",
            },
            {
                "item_id": "2",
                "item_type": "생활용품",
                "item_name": "물티슈",
                "quantity": 8,
                "updated_at": "2026-05-03T11:00:00",
            },
            {
                "item_id": "3",
                "item_type": "식료품",
                "item_name": "두유",
                "quantity": 25,
                "updated_at": "2026-05-03T09:00:00",
            },
        ]

    def get_all_products(self):
        return list(self.rows)

    def add_quantity(self, item_id, quantity):
        self.added = (item_id, quantity)
        return True

    def set_quantity(self, item_id, quantity):
        self.set = (item_id, quantity)
        return True

    async def async_get_all_products(self):
        return list(self.rows)

    async def async_add_quantity(self, item_id, quantity):
        self.added = (item_id, quantity)
        return True

    async def async_set_quantity(self, item_id, quantity):
        self.set = (item_id, quantity)
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
        "total_robot_count": 5,
        "waiting_job_count": 3,
        "running_job_count": 1,
        "warning_error_count": 4,
    }
    assert result["robots"][0]["robot_name"] == "pinky2"
    assert result["robots"][0]["robot_id"] == "pinky2"
    assert result["robots"][0]["robot_type"] == "MOBILE"
    assert "robot_role" not in result["robots"][0]
    assert result["robots"][0]["connection_status"] == "ONLINE"
    assert result["robots"][0]["runtime_state"] == "IDLE"
    assert result["robots"][0]["current_task_id"] == 101
    assert result["robots"][0]["last_seen_at"] == "2026-05-03T12:00:00"
    assert result["robots"][0]["chip_type"] == "green"
    assert result["timeline"] == [["12:00:00", "1", "DELIVERY_TASK_ACCEPTED", "accepted"]]
    assert result["flow"]["WAITING"] == [
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


def test_caregiver_service_robot_status_bundle_is_robot_centered():
    rows = [
        {
            "robot_id": "pinky2",
            "robot_type_name": "Pinky Pro",
            "robot_manager_name": "모바일팀",
            "robot_status": "RUNNING",
            "current_location": "x=1.0, y=2.0",
            "battery_percent": 87.5,
            "current_task_id": 101,
            "current_task_phase": "DELIVERY_DESTINATION",
            "current_task_status": "RUNNING",
            "last_seen_at": "2026-05-03T12:00:00",
            "last_seen_age_sec": 5,
            "fault_code": None,
        },
        {
            "robot_id": "jetcobot1",
            "robot_type_name": "JetCobot",
            "robot_manager_name": "운반팀",
            "robot_status": "ERROR",
            "current_location": None,
            "battery_percent": None,
            "current_task_id": None,
            "current_task_phase": None,
            "current_task_status": None,
            "last_seen_at": "2026-05-03T11:59:00",
            "last_seen_age_sec": 5,
            "fault_code": "ARM_FAULT",
        },
        {
            "robot_id": "pinky3",
            "robot_type_name": "Pinky Pro",
            "robot_manager_name": "모바일팀",
            "robot_status": "IDLE",
            "current_location": None,
            "battery_percent": 55,
            "current_task_id": None,
            "current_task_phase": None,
            "current_task_status": None,
            "last_seen_at": None,
            "fault_code": None,
        },
    ]

    robots = CaregiverService._format_robot_board_data(rows)
    bundle = CaregiverService._format_robot_status_bundle(robots)

    assert bundle["summary"] == {
        "total_robot_count": 3,
        "online_robot_count": 1,
        "offline_robot_count": 1,
        "caution_robot_count": 1,
    }
    assert bundle["robots"][0]["robot_id"] == "pinky2"
    assert bundle["robots"][0]["display_name"] == "Pinky Pro"
    assert bundle["robots"][0]["robot_type"] == "MOBILE"
    assert "scenario_role" not in bundle["robots"][0]
    assert bundle["robots"][0]["manager_group"] == "모바일팀"
    assert bundle["robots"][0]["capabilities"] == ["GUIDE", "DELIVERY", "PATROL"]
    assert bundle["robots"][0]["connection_status"] == "ONLINE"
    assert bundle["robots"][0]["current_phase"] == "DELIVERY_DESTINATION"
    assert bundle["robots"][1]["station_roles"] == [
        {"task_type": "DELIVERY", "station_role": "PICKUP"}
    ]
    assert bundle["robots"][1]["connection_status"] == "DEGRADED"
    assert bundle["robots"][2]["connection_status"] == "OFFLINE"
    assert bundle["delivery_composition"] == [
        {"label": "픽업 로봇팔", "value": "jetcobot1"},
        {"label": "ROS adapter arm_id", "value": "arm1 / arm2"},
    ]


def test_caregiver_service_marks_stale_runtime_offline_and_hides_ip_location():
    rows = [
        {
            "robot_id": "pinky2",
            "robot_type_name": "Pinky Pro",
            "robot_manager_name": "운반팀",
            "robot_status": "IDLE",
            "current_location": "좌표 x=1.2, y=0.8",
            "battery_percent": 87.5,
            "current_task_id": None,
            "current_task_phase": None,
            "current_task_status": None,
            "last_seen_at": "2026-05-03T12:00:00",
            "last_seen_age_sec": 3600,
            "fault_code": None,
        },
        {
            "robot_id": "pinky3",
            "robot_type_name": "Pinky Pro",
            "robot_manager_name": "모바일팀",
            "robot_status": "IDLE",
            "current_location": "192.168.0.13",
            "battery_percent": 80,
            "current_task_id": None,
            "current_task_phase": None,
            "current_task_status": None,
            "last_seen_at": "2026-05-03T12:00:00",
            "last_seen_age_sec": 5,
            "fault_code": None,
        },
    ]

    robots = CaregiverService._format_robot_board_data(rows)

    assert robots[0]["connection_status"] == "OFFLINE"
    assert robots[0]["chip_type"] == "red"
    assert robots[0]["current_location"] == "-"
    assert robots[0]["zone"] == "-"
    assert robots[0]["battery"] == "-"
    assert robots[0]["battery_percent"] is None
    assert robots[1]["connection_status"] == "ONLINE"
    assert robots[1]["current_location"] == "-"


def test_caregiver_service_flow_board_uses_dashboard_status_buckets():
    rows = [
        {"task_id": 1, "task_status": "WAITING_DISPATCH", "description": "waiting"},
        {"task_id": 2, "task_status": "READY", "description": "ready"},
        {"task_id": 3, "task_status": "ASSIGNED", "description": "assigned"},
        {"task_id": 4, "task_status": "RUNNING", "description": "running"},
        {"task_id": 5, "task_status": "CANCEL_REQUESTED", "description": "canceling"},
        {"task_id": 6, "task_status": "FAILED", "description": "failed"},
    ]

    flow = CaregiverService._format_flow_board_data(rows)

    assert list(flow) == ["WAITING", "ASSIGNED", "IN_PROGRESS", "CANCELING", "DONE"]
    assert [task["task_id"] for task in flow["WAITING"]] == [1, 2]
    assert [task["task_id"] for task in flow["ASSIGNED"]] == [3]
    assert [task["task_id"] for task in flow["IN_PROGRESS"]] == [4]
    assert [task["task_id"] for task in flow["CANCELING"]] == [5]
    assert [task["task_id"] for task in flow["DONE"]] == [6]


def test_caregiver_service_alert_log_bundle_formats_operator_events():
    rows = [
        {
            "event_id": 11,
            "occurred_at": datetime(2026, 5, 3, 12, 0, 0),
            "severity": "ERROR",
            "source_component": "Control Service",
            "task_id": 1001,
            "robot_id": "pinky2",
            "event_type": "TASK_FAILED",
            "result_code": "FAILED",
            "reason_code": "ROS_ACTION_FAILED",
            "message": "navigation failed",
            "payload_json": '{"phase":"DELIVERY_DESTINATION"}',
        },
        {
            "event_id": 12,
            "occurred_at": "2026-05-03T12:01:00",
            "severity": "WARNING",
            "source_component": "AI Server",
            "task_id": 1002,
            "robot_id": "pinky3",
            "event_type": "FALL_ALERT_CREATED",
            "result_code": "ACCEPTED",
            "reason_code": None,
            "message": "fall alert candidate accepted",
            "payload_json": '{"evidence_image_available":true}',
        },
    ]

    bundle = CaregiverService._format_alert_log_bundle(rows)

    assert bundle["summary"] == {
        "total_event_count": 2,
        "info_count": 0,
        "warning_count": 1,
        "error_count": 1,
        "critical_count": 0,
    }
    assert bundle["events"][0] == {
        "event_id": 11,
        "occurred_at": "2026-05-03T12:00:00",
        "severity": "ERROR",
        "source_component": "Control Service",
        "task_id": 1001,
        "robot_id": "pinky2",
        "event_type": "TASK_FAILED",
        "result_code": "FAILED",
        "reason_code": "ROS_ACTION_FAILED",
        "message": "navigation failed",
        "payload": {"phase": "DELIVERY_DESTINATION"},
    }


def test_caregiver_service_alert_log_period_and_limit_normalization():
    from server.ropi_main_service.application.formatting import bounded_int

    assert CaregiverService._alert_log_period_start("ALL") is None
    assert bounded_int(0, default=100, minimum=1, maximum=200) == 1
    assert bounded_int(500, default=100, minimum=1, maximum=200) == 200
    assert bounded_int("50", default=100, minimum=1, maximum=200) == 50


def test_caregiver_flow_board_keeps_cancel_requested_in_canceling_lane():
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

    assert flow["CANCELING"][0]["task_id"] == 102
    assert flow["CANCELING"][0]["task_status"] == "CANCEL_REQUESTED"
    assert flow["CANCELING"][0]["cancellable"] is False
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

    assert rows[0]["item_id"] == "1"
    assert rows[0]["item_name"] == "기저귀"


def test_inventory_service_get_inventory_bundle_normalizes_phase1_item_summary():
    service = InventoryService(repository=FakeAsyncInventoryRepository())

    bundle = service.get_inventory_bundle()

    assert bundle["summary"] == {
        "total_item_count": 3,
        "total_quantity": 33,
        "low_stock_item_count": 2,
        "empty_item_count": 1,
        "low_stock_threshold": 10,
        "last_updated_at": "2026-05-03T11:00:00",
    }
    assert bundle["items"][0] == {
        "item_id": "1",
        "item_type": "생활용품",
        "item_name": "기저귀",
        "quantity": 0,
        "updated_at": "2026-05-03T10:00:00",
    }
    assert [item["item_id"] for item in bundle["low_stock_items"]] == ["1", "2"]


def test_inventory_service_item_id_quantity_mutations_return_rpc_shape():
    repository = FakeAsyncInventoryRepository()
    service = InventoryService(repository=repository)

    add_result = service.add_item_quantity("2", 4)
    set_result = service.set_item_quantity("2", 12)

    assert add_result == {
        "result_code": "UPDATED",
        "result_message": "재고가 추가되었습니다.",
        "item_id": "2",
        "quantity_delta": 4,
    }
    assert set_result == {
        "result_code": "UPDATED",
        "result_message": "재고 수량이 수정되었습니다.",
        "item_id": "2",
        "quantity": 12,
    }
    assert repository.added == ("2", 4)
    assert repository.set == ("2", 12)


def test_inventory_service_async_add_inventory():
    repository = FakeAsyncInventoryRepository()
    service = InventoryService(repository=repository)

    result = asyncio.run(service.async_add_inventory("물티슈", 2))

    assert result == (True, "재고가 추가되었습니다.")
    assert repository.added == ("2", 2)


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
