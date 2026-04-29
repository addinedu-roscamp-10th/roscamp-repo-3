INSERT INTO ai_inference_log (
    task_id,
    robot_id,
    stream_name,
    frame_id,
    inference_type,
    confidence,
    result_json,
    inferred_at,
    received_at,
    created_at
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
    NOW(3),
    NOW(3)
)
