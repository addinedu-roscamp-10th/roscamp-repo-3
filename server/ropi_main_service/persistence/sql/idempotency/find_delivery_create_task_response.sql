SELECT request_hash, response_json
FROM idempotency_record
WHERE scope = 'DELIVERY_CREATE_TASK'
  AND requester_type = 'CAREGIVER'
  AND requester_id = %s
  AND idempotency_key = %s
LIMIT 1
