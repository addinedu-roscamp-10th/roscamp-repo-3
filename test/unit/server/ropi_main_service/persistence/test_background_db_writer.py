import asyncio

from server.ropi_main_service.persistence.background_db_writer import BackgroundDbWriter


class FakeRobotDataLogRepository:
    def __init__(self):
        self.samples = []
        self.sample_batches = []

    async def async_insert_feedback_sample(self, **kwargs):
        self.samples.append(kwargs)

    async def async_insert_feedback_samples(self, samples):
        self.sample_batches.append(list(samples))


class FakeRobotRuntimeStatusRepository:
    def __init__(self):
        self.statuses = []
        self.status_batches = []

    async def async_upsert_runtime_status(self, **kwargs):
        self.statuses.append(kwargs)

    async def async_upsert_runtime_statuses(self, statuses):
        self.status_batches.append(list(statuses))


class BlockingRobotDataLogRepository(FakeRobotDataLogRepository):
    def __init__(self, *, entered, release):
        super().__init__()
        self.entered = entered
        self.release = release

    async def async_insert_feedback_samples(self, samples):
        self.sample_batches.append(list(samples))
        self.entered.set()
        await self.release.wait()


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


def build_status(*, robot_id="pinky2", active_task_id=101, pose_x=1.2):
    return {
        "robot_id": robot_id,
        "robot_kind": "PINKY",
        "runtime_state": "RUNNING",
        "active_task_id": active_task_id,
        "battery_percent": None,
        "pose_x": pose_x,
        "pose_y": 0.8,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "fault_code": None,
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

    assert robot_data_log_repository.samples == []
    assert robot_data_log_repository.sample_batches == [[build_sample()]]
    assert robot_runtime_status_repository.statuses == []
    assert robot_runtime_status_repository.status_batches == [[build_status()]]


def test_background_db_writer_batches_samples_and_keeps_latest_status_per_robot():
    robot_data_log_repository = FakeRobotDataLogRepository()
    robot_runtime_status_repository = FakeRobotRuntimeStatusRepository()
    writer = BackgroundDbWriter(
        robot_data_log_repository=robot_data_log_repository,
        robot_runtime_status_repository=robot_runtime_status_repository,
    )

    first_sample = build_sample()
    second_sample = {
        **build_sample(),
        "task_id": 102,
        "pose_x": 2.4,
    }

    async def scenario():
        writer.start()
        assert writer.enqueue_robot_data_log_sample(first_sample) is True
        assert writer.enqueue_robot_data_log_sample(second_sample) is True
        await writer.flush()
        await writer.stop()

    asyncio.run(scenario())

    assert robot_data_log_repository.sample_batches == [[first_sample, second_sample]]
    assert robot_runtime_status_repository.status_batches == [
        [
            build_status(active_task_id=102, pose_x=2.4),
        ]
    ]


def test_background_db_writer_batches_direct_runtime_status_with_latest_per_robot():
    robot_runtime_status_repository = FakeRobotRuntimeStatusRepository()
    writer = BackgroundDbWriter(
        robot_data_log_repository=FakeRobotDataLogRepository(),
        robot_runtime_status_repository=robot_runtime_status_repository,
    )

    first_status = build_status(active_task_id=101, pose_x=1.2)
    second_status = build_status(active_task_id=102, pose_x=2.4)

    async def scenario():
        writer.start()
        assert writer.enqueue_robot_runtime_status(first_status) is True
        assert writer.enqueue_robot_runtime_status(second_status) is True
        await writer.flush()
        await writer.stop()

    asyncio.run(scenario())

    assert robot_runtime_status_repository.status_batches == [[second_status]]


def test_background_db_writer_drops_samples_when_queue_is_full():
    writer = BackgroundDbWriter(
        robot_data_log_repository=FakeRobotDataLogRepository(),
        max_queue_size=1,
    )

    assert writer.enqueue_robot_data_log_sample(build_sample()) is True
    assert writer.enqueue_robot_data_log_sample(build_sample()) is False


def test_background_db_writer_rejects_enqueue_after_stop_starts():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        writer = BackgroundDbWriter(
            robot_data_log_repository=BlockingRobotDataLogRepository(
                entered=entered,
                release=release,
            ),
            robot_runtime_status_repository=FakeRobotRuntimeStatusRepository(),
        )

        writer.start()
        assert writer.enqueue_robot_data_log_sample(build_sample()) is True
        await asyncio.wait_for(entered.wait(), timeout=1.0)

        stop_task = asyncio.create_task(writer.stop())
        await asyncio.sleep(0)
        accepted_after_stop_started = writer.enqueue_robot_data_log_sample(build_sample())

        release.set()
        await asyncio.wait_for(stop_task, timeout=1.0)
        return accepted_after_stop_started, writer.queue.qsize()

    accepted_after_stop_started, remaining_queue_size = asyncio.run(scenario())

    assert accepted_after_stop_started is False
    assert remaining_queue_size == 0


def test_background_db_writer_rejects_enqueue_after_stop_until_restarted():
    robot_data_log_repository = FakeRobotDataLogRepository()
    writer = BackgroundDbWriter(
        robot_data_log_repository=robot_data_log_repository,
        robot_runtime_status_repository=FakeRobotRuntimeStatusRepository(),
    )

    async def scenario():
        writer.start()
        await writer.stop()
        accepted_after_stop = writer.enqueue_robot_data_log_sample(build_sample())

        writer.start()
        accepted_after_restart = writer.enqueue_robot_data_log_sample(build_sample())
        await writer.flush()
        await writer.stop()
        return accepted_after_stop, accepted_after_restart

    accepted_after_stop, accepted_after_restart = asyncio.run(scenario())

    assert accepted_after_stop is False
    assert accepted_after_restart is True
    assert robot_data_log_repository.sample_batches == [[build_sample()]]
