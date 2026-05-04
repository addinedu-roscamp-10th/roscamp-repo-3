SELECT
    request_hash,
    response_json
FROM idempotency_record
WHERE scope = %s
  AND requester_type = 'KIOSK'
  AND requester_id = %s
  AND idempotency_key = %s
LIMIT 1
