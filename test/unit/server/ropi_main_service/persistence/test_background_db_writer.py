import asyncio

from server.ropi_main_service.persistence.background_db_writer import BackgroundDbWriter


class FakeRobotDataLogRepository:
    def __init__(self):
        self.samples = []

    async def async_insert_feedback_sample(self, **kwargs):
        self.samples.append(kwargs)


class FakeRobotRuntimeStatusRepository:
    def __init__(self):
        self.statuses = []

    async def async_upsert_runtime_status(self, **kwargs):
        self.statuses.append(kwargs)


def build_sample():
    return {
        "robot_id": "pinky2",
        "task_id": 101,
        "data_type": "NAVIGATION_FEEDBACK",
        "pose_x": 1.2,
        "pose_y": 0.8,
        "pose_yaw": 0.0,
        "battery_percent": None,
        "payload": {
            "feedback_type": "NAVIGATION_FEEDBACK",
            "payload": {
                "current_pose": {
                    "header": {"frame_id": "map"},
                },
            },
        },
    }


def test_background_db_writer_flushes_robot_data_log_samples():
    robot_data_log_repository = FakeRobotDataLogRepository()
    robot_runtime_status_repository = FakeRobotRuntimeStatusRepository()
    writer = BackgroundDbWriter(
        robot_data_log_repository=robot_data_log_repository,
        robot_runtime_status_repository=robot_runtime_status_repository,
    )

    async def scenario():
        writer.start()
        assert writer.enqueue_robot_data_log_sample(build_sample()) is True
        await writer.flush()
        await writer.stop()

    asyncio.run(scenario())

    assert robot_data_log_repository.samples == [build_sample()]
    assert robot_runtime_status_repository.statuses == [
        {
            "robot_id": "pinky2",
            "robot_kind": "PINKY",
            "runtime_state": "RUNNING",
            "active_task_id": 101,
            "battery_percent": None,
            "pose_x": 1.2,
            "pose_y": 0.8,
            "pose_yaw": 0.0,
            "frame_id": "map",
            "fault_code": None,
        }
    ]


def test_background_db_writer_drops_samples_when_queue_is_full():
    writer = BackgroundDbWriter(
        robot_data_log_repository=FakeRobotDataLogRepository(),
        max_queue_size=1,
    )

    assert writer.enqueue_robot_data_log_sample(build_sample()) is True
    assert writer.enqueue_robot_data_log_sample(build_sample()) is False
