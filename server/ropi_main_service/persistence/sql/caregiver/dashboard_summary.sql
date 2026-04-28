SELECT
    (
        SELECT COUNT(*)
        FROM robot_runtime_status
        WHERE runtime_state IN ('IDLE', 'READY')
    ) AS available_robot_count,
    (
        SELECT COUNT(*)
        FROM task
        WHERE task_status IN ('WAITING', 'WAITING_DISPATCH')
    ) AS waiting_job_count,
    (
        SELECT COUNT(*)
        FROM task
        WHERE task_status = 'RUNNING'
    ) AS running_job_count
