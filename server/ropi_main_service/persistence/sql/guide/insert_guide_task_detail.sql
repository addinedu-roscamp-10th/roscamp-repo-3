INSERT INTO guide_task_detail (
    task_id,
    visitor_id,
    member_id,
    destination_goal_pose_id,
    guide_phase,
    target_track_id,
    notes
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    'WAIT_GUIDE_START_CONFIRM',
    NULL,
    %s
)
