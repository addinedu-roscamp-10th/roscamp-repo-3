import asyncio

from server.ropi_main_service.application.robot_status_event_runtime import (
    RobotStatusEventRuntime,
)


class FakeCaregiverService:
    def __init__(self, bundles):
        self.bundles = list(bundles)

    async def async_get_robot_status_bundle(self):
        if self.bundles:
            return self.bundles.pop(0)
        return {"robots": []}


class FakeTaskEventPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, payload):
        self.events.append((event_type, payload))


def test_robot_status_event_runtime_publishes_changed_pinky_and_arm_status():
    publisher = FakeTaskEventPublisher()
    service = FakeCaregiverService(
        [
            {
                "robots": [
                    {
                        "robot_id": "pinky2",
                        "robot_type": "MOBILE",
                        "connection_status": "ONLINE",
                        "runtime_state": "MOVING",
                        "battery_percent": 80.0,
                        "current_task_id": 101,
                        "current_phase": "DELIVERY_DESTINATION",
                        "current_location": "303호 앞",
                        "current_pose": {
                            "map_id": "map_0504",
                            "frame_id": "map",
                            "x": 1.0,
                            "y": 2.0,
                            "yaw": 0.1,
                        },
                        "last_seen_at": "2026-05-03T12:00:00",
                    },
                    {
                        "robot_id": "jetcobot1",
                        "robot_type": "ARM",
                        "connection_status": "ONLINE",
                        "runtime_state": "BUSY",
                        "current_task_id": 101,
                        "station_roles": [
                            {
                                "task_type": "DELIVERY",
                                "station_role": "PICKUP",
                            }
                        ],
                        "fault_code": None,
                        "last_seen_at": "2026-05-03T12:00:00",
                    },
                ]
            },
            {
                "robots": [
                    {
                        "robot_id": "pinky2",
                        "robot_type": "MOBILE",
                        "connection_status": "ONLINE",
                        "runtime_state": "MOVING",
                        "battery_percent": 80.0,
                        "current_task_id": 101,
                        "current_phase": "DELIVERY_DESTINATION",
                        "current_location": "303호 앞",
                        "current_pose": {
                            "map_id": "map_0504",
                            "frame_id": "map",
                            "x": 1.0,
                            "y": 2.0,
                            "yaw": 0.1,
                        },
                        "last_seen_at": "2026-05-03T12:00:00",
                    }
                ]
            },
        ]
    )
    runtime = RobotStatusEventRuntime(
        caregiver_service=service,
        task_event_publisher=publisher,
    )

    first = asyncio.run(runtime.poll_once())
    second = asyncio.run(runtime.poll_once())

    assert first["published_count"] == 2
    assert second["published_count"] == 0
    assert publisher.events[0] == (
        "PINKY_UPDATED",
        {
            "pinky_id": "pinky2",
            "robot_id": "pinky2",
            "pinky_state": "MOVING",
            "runtime_state": "MOVING",
            "connection_status": "ONLINE",
            "battery_percent": 80.0,
            "active_task_id": 101,
            "current_phase": "DELIVERY_DESTINATION",
            "pose": {
                "map_id": "map_0504",
                "frame_id": "map",
                "x": 1.0,
                "y": 2.0,
                "yaw": 0.1,
            },
            "current_pose": {
                "map_id": "map_0504",
                "frame_id": "map",
                "x": 1.0,
                "y": 2.0,
                "yaw": 0.1,
            },
            "zone_id": None,
            "zone_name": "303호 앞",
            "fault_code": None,
            "last_seen_at": "2026-05-03T12:00:00",
        },
    )
    assert publisher.events[1][0] == "ARM_UPDATED"
    assert publisher.events[1][1]["robot_id"] == "jetcobot1"
    assert publisher.events[1][1]["arm_id"] == "arm1"
    assert publisher.events[1][1]["station_role"] == "PICKUP"
