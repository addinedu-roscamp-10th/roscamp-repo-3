from server.ropi_main_service.persistence.repositories.drive_task_execution_repository import (
    DriveTaskExecutionRepository,
)


def test_drive_execution_repository_builds_segment_reservation_resources():
    path_snapshot = {
        "poses": [
            {"sequence_no": 1, "waypoint_id": "hall_1"},
            {"sequence_no": 2, "waypoint_id": "hall_2"},
            {"sequence_no": 3, "waypoint_id": "hall_3"},
        ]
    }
    edge_rows = [
        {
            "from_sequence_no": 1,
            "edge_id": "edge_hall_1_2",
            "conflict_zone_id": "cz_cross_01",
        },
        {"from_sequence_no": 2, "edge_id": "edge_hall_2_3"},
    ]

    segments = DriveTaskExecutionRepository._build_reservation_segments(
        path_snapshot=path_snapshot,
        edge_rows=edge_rows,
    )

    assert segments == [
        {
            "sequence_no": 1,
            "waypoint_id": "hall_1",
            "resources": [{"resource_type": "WAYPOINT", "resource_id": "hall_1"}],
        },
        {
            "sequence_no": 2,
            "waypoint_id": "hall_2",
            "resources": [
                {"resource_type": "EDGE", "resource_id": "edge_hall_1_2"},
                {"resource_type": "CONFLICT_ZONE", "resource_id": "cz_cross_01"},
                {"resource_type": "WAYPOINT", "resource_id": "hall_2"},
            ],
        },
        {
            "sequence_no": 3,
            "waypoint_id": "hall_3",
            "resources": [
                {"resource_type": "EDGE", "resource_id": "edge_hall_2_3"},
                {"resource_type": "WAYPOINT", "resource_id": "hall_3"},
            ],
        },
    ]
