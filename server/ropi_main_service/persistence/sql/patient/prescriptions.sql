SELECT
    prescription_image_path AS image_path
FROM prescription
WHERE member_id = %s
ORDER BY prescription_id DESC
