SELECT
    t.task_id,
    t.task_type,
    t.task_status,
    t.phase,
    t.assigned_robot_id,
    gtd.destination_goal_pose_id,
    gp.pose_x,
    gp.pose_y,
    gp.pose_yaw,
    gp.frame_id
FROM task t
JOIN guide_task_detail gtd
  ON gtd.task_id = t.task_id
JOIN goal_pose gp
  ON gp.goal_pose_id = gtd.destination_goal_pose_id
WHERE t.task_id = %s
