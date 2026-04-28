INSERT INTO task (
    task_type,
    request_id,
    idempotency_key,
    requester_type,
    requester_id,
    priority,
    task_status,
    phase,
    assigned_robot_id,
    map_id,
    created_at,
    updated_at
)
SELECT
    'DELIVERY',
    %s,
    %s,
    'CAREGIVER',
    %s,
    %s,
    'WAITING_DISPATCH',
    'REQUESTED',
    %s,
    gp.map_id,
    NOW(3),
    NOW(3)
FROM goal_pose gp
WHERE gp.goal_pose_id = %s
LIMIT 1
