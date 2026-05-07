import asyncio
from datetime import datetime

from server.ropi_main_service.application.task_monitor import TaskMonitorService


class FakeTaskMonitorRepository:
    def __init__(self):
        self.calls = []
        self.status_row = None
        self.snapshot = {
            "last_event_seq": 91,
            "tasks": [
                {
                    "task_id": 2001,
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "task_outcome": "FAILED",
                    "result_code": "FAILED",
                    "result_message": "순찰 workflow 실패",
                    "phase": "WAIT_FALL_RESPONSE",
                    "assigned_robot_id": "pinky3",
                    "map_id": "map_test11_0423",
                    "map_name": "map_test11_0423",
                    "map_revision": 1,
                    "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
                    "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
                    "map_frame_id": "map",
                    "patrol_area_id": "ward_3f",
                    "patrol_area_name": "3층 병동",
                    "patrol_area_revision": 2,
                    "patrol_status": "MOVING",
                    "patrol_path_frame_id": "map",
                    "waypoint_count": 3,
                    "current_waypoint_index": 1,
                    "path_snapshot_json": {
                        "header": {"frame_id": "map"},
                        "poses": [
                            {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
                            {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
                            {"x": 0.8577, "y": 0.2560, "yaw": 0.0},
                        ],
                    },
                    "latest_reason_code": "FALL_DETECTED",
                    "requested_at": datetime(2026, 4, 30, 10, 0, 0),
                    "started_at": datetime(2026, 4, 30, 10, 1, 0),
                    "finished_at": None,
                    "updated_at": datetime(2026, 4, 30, 10, 2, 0),
                    "latest_feedback_type": "PATROL_FEEDBACK",
                    "latest_feedback_payload_json": {
                        "feedback_summary": "MOVING / 남은 거리 1.25m",
                        "patrol_status": "MOVING",
                        "current_waypoint_index": 1,
                        "total_waypoints": 3,
                        "current_pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
                        "distance_remaining_m": 1.25,
                    },
                    "latest_feedback_updated_at": datetime(2026, 4, 30, 10, 1, 30),
                    "latest_robot_id": "pinky3",
                    "runtime_state": "RUNNING",
                    "battery_percent": 88.5,
                    "pose_x": 1.2,
                    "pose_y": 0.4,
                    "pose_yaw": 0.0,
                    "frame_id": "map",
                    "last_seen_at": datetime(2026, 4, 30, 10, 1, 35),
                    "latest_alert_payload_json": {
                        "trigger_result": {
                            "result_seq": 44,
                            "frame_id": "frame-44",
                            "fall_streak_ms": 1200,
                            "evidence_image_id": "fall-2001-44",
                            "evidence_image_available": True,
                            "zone_name": "3층 복도",
                            "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                        }
                    },
                    "latest_alert_id": 17,
                    "latest_alert_occurred_at": datetime(2026, 4, 30, 10, 2, 0),
                }
            ],
        }

    def get_task_monitor_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return self.snapshot

    async def async_get_task_monitor_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return self.snapshot

    def get_task_status(self, **kwargs):
        self.calls.append(kwargs)
        return self.status_row

    async def async_get_task_status(self, **kwargs):
        self.calls.append(kwargs)
        return self.status_row


def test_task_monitor_snapshot_formats_nested_feedback_robot_and_alert():
    repository = FakeTaskMonitorRepository()
    service = TaskMonitorService(repository=repository)

    response = service.get_task_monitor_snapshot(
        consumer_id="ui-admin-task-monitor",
        task_types=["patrol"],
        statuses=["running"],
        include_recent_terminal=False,
        recent_terminal_limit=1000,
        limit=500,
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["last_event_seq"] == 91
    assert response["consumer_id"] == "ui-admin-task-monitor"
    assert repository.calls == [
        {
            "task_types": ("PATROL",),
            "statuses": ("RUNNING",),
            "limit": 200,
        }
    ]

    task = response["tasks"][0]
    assert task["task_id"] == 2001
    assert task["task_type"] == "PATROL"
    assert task["task_status"] == "RUNNING"
    assert task["result_code"] == "FAILED"
    assert task["result_message"] == "순찰 workflow 실패"
    assert task["reason_code"] == "FALL_DETECTED"
    assert task["phase"] == "WAIT_FALL_RESPONSE"
    assert task["assigned_robot_id"] == "pinky3"
    assert task["cancellable"] is True
    assert task["patrol_area_name"] == "3층 병동"
    assert task["patrol_status"] == "MOVING"
    assert task["patrol_map"] == {
        "map_id": "map_test11_0423",
        "map_name": "map_test11_0423",
        "map_revision": 1,
        "frame_id": "map",
        "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
        "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
    }
    assert task["patrol_path"] == {
        "frame_id": "map",
        "waypoint_count": 3,
        "current_waypoint_index": 1,
        "poses": [
            {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
            {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
            {"x": 0.8577, "y": 0.2560, "yaw": 0.0},
        ],
    }
    assert task["latest_feedback"] == {
        "feedback_summary": "MOVING / 남은 거리 1.25m",
        "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
        "patrol_status": "MOVING",
        "current_waypoint_index": 1,
        "total_waypoints": 3,
        "distance_remaining_m": 1.25,
        "updated_at": "2026-04-30T10:01:30",
    }
    assert task["latest_robot"] == {
        "robot_id": "pinky3",
        "runtime_state": "RUNNING",
        "battery_percent": 88.5,
        "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0, "frame_id": "map"},
        "last_seen_at": "2026-04-30T10:01:35",
    }
    assert task["latest_alert"]["alert_id"] == 17
    assert task["latest_alert"]["result_seq"] == 44
    assert task["latest_alert"]["evidence_image_id"] == "fall-2001-44"
    assert task["latest_alert"]["alert_pose"] == {"x": 0.9308, "y": 0.185, "yaw": 0.0}


def test_task_monitor_snapshot_defaults_to_active_plus_recent_terminal_statuses():
    repository = FakeTaskMonitorRepository()
    repository.snapshot = {
        "last_event_seq": 5,
        "tasks": [
            {"task_id": 1, "task_status": "RUNNING"},
            {"task_id": 2, "task_status": "COMPLETED"},
            {"task_id": 3, "task_status": "FAILED"},
        ],
    }
    service = TaskMonitorService(repository=repository)

    response = service.get_task_monitor_snapshot(recent_terminal_limit=1)

    assert repository.calls[0]["statuses"] == (
        "WAITING",
        "WAITING_DISPATCH",
        "READY",
        "ASSIGNED",
        "RUNNING",
        "CANCEL_REQUESTED",
        "CANCELLING",
        "PREEMPTING",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
    )
    assert [task["task_id"] for task in response["tasks"]] == [1, 2]


def test_task_monitor_snapshot_async_uses_async_repository_method():
    repository = FakeTaskMonitorRepository()
    service = TaskMonitorService(repository=repository)

    response = asyncio.run(
        service.async_get_task_monitor_snapshot(task_types=["patrol"])
    )

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls[0]["task_types"] == ("PATROL",)


def test_task_monitor_get_task_status_formats_single_task():
    repository = FakeTaskMonitorRepository()
    repository.status_row = {
        "task_id": 3001,
        "task_type": "GUIDE",
        "task_status": "RUNNING",
        "phase": "GUIDANCE_RUNNING",
        "assigned_robot_id": "pinky1",
        "guide_phase": "WAIT_TARGET_TRACKING",
        "guide_target_track_id": "track_17",
        "guide_visitor_id": 4,
        "guide_visitor_name": "김민수",
        "guide_relation_name": "아들",
        "guide_member_id": 1,
        "guide_resident_name": "김영수",
        "guide_room_no": "301",
        "guide_destination_id": "delivery_room_301",
        "guide_destination_map_id": "map_test11_0423",
        "guide_destination_zone_id": "room_301",
        "guide_destination_zone_name": "301호",
        "guide_destination_purpose": "GUIDE_DESTINATION",
        "updated_at": datetime(2026, 5, 4, 15, 10, 0),
    }
    service = TaskMonitorService(repository=repository)

    response = service.get_task_status(task_id="3001")

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert response["task_type"] == "GUIDE"
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "GUIDANCE_RUNNING"
    assert response["assigned_robot_id"] == "pinky1"
    assert response["guide_detail"] == {
        "guide_phase": "WAIT_TARGET_TRACKING",
        "target_track_id": "track_17",
        "visitor_id": 4,
        "visitor_name": "김민수",
        "relation_name": "아들",
        "member_id": 1,
        "resident_name": "김영수",
        "room_no": "301",
        "destination_id": "delivery_room_301",
        "destination_map_id": "map_test11_0423",
        "destination_zone_id": "room_301",
        "destination_zone_name": "301호",
        "destination_purpose": "GUIDE_DESTINATION",
    }
    assert response["updated_at"] == "2026-05-04T15:10:00"
    assert repository.calls[-1] == {"task_id": 3001}


def test_task_monitor_get_task_status_returns_not_found_for_missing_task():
    repository = FakeTaskMonitorRepository()
    service = TaskMonitorService(repository=repository)

    response = service.get_task_status(task_id=9999)

    assert response == {
        "result_code": "NOT_FOUND",
        "result_message": "태스크를 찾을 수 없습니다.",
        "reason_code": "TASK_NOT_FOUND",
        "task_id": 9999,
    }


def test_task_monitor_async_get_task_status_uses_async_repository_method():
    repository = FakeTaskMonitorRepository()
    repository.status_row = {
        "task_id": 3001,
        "task_type": "GUIDE",
        "task_status": "COMPLETED",
        "phase": "GUIDANCE_FINISHED",
    }
    service = TaskMonitorService(repository=repository)

    response = asyncio.run(service.async_get_task_status(task_id="3001"))

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "COMPLETED"
    assert repository.calls[-1] == {"task_id": 3001}
