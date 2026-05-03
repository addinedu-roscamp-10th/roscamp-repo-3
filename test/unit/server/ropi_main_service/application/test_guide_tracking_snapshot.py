from server.ropi_main_service.application.guide_tracking_snapshot import (
    GuideTrackingSnapshotStore,
)


def test_snapshot_store_returns_latest_snapshot_by_task_and_robot():
    store = GuideTrackingSnapshotStore()

    store.record(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "ACQUIRING",
            "tracking_result_seq": 880,
        }
    )
    store.record(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "TRACKING",
            "active_track_id": "track_17",
            "tracking_result_seq": 881,
        }
    )

    assert store.get(task_id=3001)["tracking_status"] == "TRACKING"
    assert store.get(pinky_id="pinky1")["active_track_id"] == "track_17"


def test_snapshot_store_ignores_older_sequence_for_same_task():
    store = GuideTrackingSnapshotStore()

    store.record(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "TRACKING",
            "active_track_id": "track_17",
            "tracking_result_seq": 881,
        }
    )
    store.record(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "ACQUIRING",
            "tracking_result_seq": 880,
        }
    )

    assert store.get(task_id="3001")["tracking_result_seq"] == 881


def test_snapshot_store_does_not_fallback_to_robot_when_task_id_is_unknown():
    store = GuideTrackingSnapshotStore()

    store.record(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "tracking_status": "TRACKING",
            "active_track_id": "track_17",
            "tracking_result_seq": 881,
        }
    )

    assert store.get(task_id=3002, pinky_id="pinky1") is None
    assert store.get(pinky_id="pinky1")["task_id"] == 3001
