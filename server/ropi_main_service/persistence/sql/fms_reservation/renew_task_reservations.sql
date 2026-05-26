UPDATE fms_reservation
SET reserved_until = DATE_ADD(NOW(3), INTERVAL %s SECOND),
    updated_at = NOW(3)
WHERE task_id = %s
  AND released_at IS NULL
  AND reservation_status = 'HELD'
  AND (reserved_until IS NULL OR reserved_until > NOW(3))
