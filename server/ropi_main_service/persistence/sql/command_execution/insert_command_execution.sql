INSERT INTO command_execution (
    task_id,
    transport,
    command_type,
    command_phase,
    target_component,
    target_robot_id,
    target_endpoint,
    request_json,
    started_at
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW(3)
)
