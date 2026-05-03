SELECT
    t.task_id,
    t.task_type,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    gtd.guide_phase,
    gtd.target_track_id
FROM task t
JOIN guide_task_detail gtd
  ON gtd.task_id = t.task_id
WHERE t.task_id = %s
FOR UPDATE
