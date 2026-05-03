SELECT
    (
        SELECT COUNT(*)
        FROM robot_runtime_status
        WHERE runtime_state IN ('IDLE', 'READY')
          AND last_seen_at >= DATE_SUB(NOW(3), INTERVAL 60 SECOND)
    ) AS available_robot_count,
    (
        SELECT COUNT(*)
        FROM robot
    ) AS total_robot_count,
    (
        SELECT COUNT(*)
        FROM task
        WHERE task_status IN ('WAITING', 'WAITING_DISPATCH', 'READY')
    ) AS waiting_job_count,
    (
        SELECT COUNT(*)
        FROM task
        WHERE task_status IN ('ASSIGNED', 'RUNNING', 'IN_PROGRESS')
    ) AS running_job_count,
    (
        SELECT COUNT(*)
        FROM task_event_log
        WHERE severity IN ('WARNING', 'ERROR', 'CRITICAL')
          AND occurred_at >= DATE_SUB(NOW(3), INTERVAL 1 DAY)
    ) AS warning_error_count
