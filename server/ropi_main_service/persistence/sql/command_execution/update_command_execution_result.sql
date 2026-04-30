UPDATE command_execution
SET accepted = %s,
    result_code = %s,
    result_message = %s,
    response_json = %s,
    finished_at = NOW(3),
    elapsed_ms = GREATEST(0, TIMESTAMPDIFF(MICROSECOND, started_at, NOW(3)) DIV 1000)
WHERE command_execution_id = %s
