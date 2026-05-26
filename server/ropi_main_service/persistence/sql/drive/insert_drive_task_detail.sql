INSERT INTO drive_task_detail (
    task_id,
    route_id,
    route_revision,
    drive_status,
    frame_id,
    waypoint_count,
    path_snapshot_json,
    notes
)
VALUES (
    %s,
    %s,
    %s,
    'PENDING',
    %s,
    %s,
    %s,
    %s
)
