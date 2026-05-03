UPDATE item
SET
    quantity = %s,
    updated_at = NOW()
WHERE item_id = %s
