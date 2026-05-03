UPDATE guide_task_detail
SET guide_phase = %s,
    target_track_id = %s
WHERE task_id = %s
