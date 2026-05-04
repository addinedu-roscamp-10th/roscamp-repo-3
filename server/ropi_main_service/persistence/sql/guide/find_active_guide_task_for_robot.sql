SELECT
    t.task_id,
    t.assigned_robot_id,
    t.task_status,
    t.phase,
    gtd.guide_phase,
    gtd.target_track_id
FROM task t
JOIN guide_task_detail gtd
  ON gtd.task_id = t.task_id
WHERE t.task_type = 'GUIDE'
  AND t.assigned_robot_id = %s
  AND t.task_status NOT IN ('COMPLETED', 'CANCELLED', 'FAILED')
  AND t.phase IN ('WAIT_TARGET_TRACKING', 'GUIDANCE_RUNNING', 'WAIT_REIDENTIFY')
ORDER BY t.updated_at DESC, t.task_id DESC
LIMIT 1
