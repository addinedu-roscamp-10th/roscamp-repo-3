from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeDeliveryRequestRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_delivery_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)


class FakeGoalPoseNavigationService:
    def __init__(self):
        self.calls = []

    def navigate(self, **kwargs):
        self.calls.append(kwargs)
        return {"accepted": True}


class FakeDestinationGoalPoseResolver:
    def __init__(self, goal_pose):
        self.goal_pose = goal_pose
        self.calls = []

    def __call__(self, destination_id):
        self.calls.append(destination_id)
        return self.goal_pose


def build_goal_pose():
    return {
        "header": {
            "stamp": {
                "sec": 1776554120,
                "nanosec": 0,
            },
            "frame_id": "map",
        },
        "pose": {
            "position": {
                "x": 18.4,
                "y": 7.2,
                "z": 0.0,
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "w": 1.0,
            },
        },
    }


def build_request_payload():
    return {
        "request_id": "req_001",
        "caregiver_id": "cg_001",
        "item_id": "supply_001",
        "quantity": 2,
        "destination_id": "room_301",
        "priority": "NORMAL",
        "notes": "Medication after meals",
        "idempotency_key": "idem_delivery_001",
    }


def test_create_delivery_task_wires_if_com_007_delivery_destination_after_acceptance():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": "task_delivery_001",
            "task_status": "WAITING_DISPATCH",
            "assigned_pinky_id": "pinky2",
        }
    )
    goal_service = FakeGoalPoseNavigationService()
    resolver = FakeDestinationGoalPoseResolver(build_goal_pose())
    service = DeliveryRequestService(
        repository=repository,
        goal_pose_navigation_service=goal_service,
        destination_goal_pose_resolver=resolver,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "ACCEPTED"
    assert resolver.calls == ["room_301"]
    assert goal_service.calls == [
        {
            "task_id": "task_delivery_001",
            "nav_phase": "DELIVERY_DESTINATION",
            "goal_pose": build_goal_pose(),
            "timeout_sec": 120,
        }
    ]


def test_create_delivery_task_does_not_wire_navigation_when_request_is_rejected():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
            "reason_code": "ITEM_NOT_FOUND",
            "task_id": None,
            "task_status": None,
            "assigned_pinky_id": None,
        }
    )
    goal_service = FakeGoalPoseNavigationService()
    resolver = FakeDestinationGoalPoseResolver(build_goal_pose())
    service = DeliveryRequestService(
        repository=repository,
        goal_pose_navigation_service=goal_service,
        destination_goal_pose_resolver=resolver,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "REJECTED"
    assert resolver.calls == []
    assert goal_service.calls == []
