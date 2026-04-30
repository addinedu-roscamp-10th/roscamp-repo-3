INSERT INTO delivery_task_detail (
    task_id,
    pickup_goal_pose_id,
    destination_goal_pose_id,
    pickup_arm_robot_id,
    dropoff_arm_robot_id,
    robot_slot_id,
    notes
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
