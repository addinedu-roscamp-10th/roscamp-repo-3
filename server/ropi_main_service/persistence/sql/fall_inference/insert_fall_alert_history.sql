INSERT INTO task_state_history (
    task_id,
    from_status,
    to_status,
    from_phase,
    to_phase,
    reason_code,
    message,
    changed_by_component,
    changed_at
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    'WAIT_FALL_RESPONSE',
    %s,
    %s,
    'control_service',
    NOW(3)
)
