UPDATE fms_reservation
SET reservation_status = 'HELD',
    reserved_from = COALESCE(reserved_from, NOW(3)),
    reserved_until = DATE_ADD(NOW(3), INTERVAL %s SECOND),
    reason_code = NULL,
    updated_at = NOW(3)
WHERE reservation_id = %s
  AND released_at IS NULL
  AND reservation_status IN ('WAITING', 'HELD')
