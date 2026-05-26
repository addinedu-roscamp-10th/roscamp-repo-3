UPDATE fms_reservation
SET reservation_status = 'RELEASED',
    released_at = NOW(3),
    reason_code = %s,
    updated_at = NOW(3)
WHERE task_id = %s
  AND robot_id = %s
  AND released_at IS NULL
  AND reservation_status IN ('HELD', 'WAITING')
