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
    'CANCEL_REQUESTED',
    %s,
    'CANCEL_REQUESTED',
    %s,
    %s,
    %s,
    NOW(3)
)
