INSERT INTO patrol_task_detail (
    task_id,
    patrol_area_id,
    patrol_area_revision,
    patrol_status,
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
