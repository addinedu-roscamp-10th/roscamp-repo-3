USE care_service;

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM `visitor`;
DELETE FROM `event`;
DELETE FROM `prescription`;
DELETE FROM `robot_event`;
DELETE FROM `member`;
DELETE FROM `event_type`;
DELETE FROM `robot`;
DELETE FROM `supply`;
DELETE FROM `map_table`;
DELETE FROM `caregiver`;
DELETE FROM `preference`;

SET FOREIGN_KEY_CHECKS = 1;

-- =========================
-- preference
-- =========================
INSERT INTO `preference`
(`preference_id`, `preference`, `dislike`, `comment`, `created_at`, `updated_at`)
VALUES
(1, '부드러운 음식, 산책', '매운 음식', '식사 속도가 느림', NOW(), NOW()),
(2, 'TV 시청, 음악 감상', '소음', '낮잠 시간 중요', NOW(), NOW()),
(3, '커피, 신문 읽기', '찬 음식', '아침 일찍 기상', NOW(), NOW());

-- =========================
-- member (어르신)
-- =========================
INSERT INTO `member`
(`member_id`, `member_name`, `admission_date`, `birth_date`, `gender_code`,
 `address`, `room_no`, `care_grade_code`, `created_at`, `updated_at`)
VALUES
('MEM001', '김영수', '2025-01-10', '1942-03-11', 'M',
 '서울시 강남구', '301', 2, NOW(), NOW()),

('MEM002', '이순자', '2025-02-15', '1945-08-22', 'F',
 '서울시 송파구', '302', 3, NOW(), NOW()),

('MEM003', '박철호', '2025-03-01', '1939-11-09', 'M',
 '서울시 강동구', '305', 1, NOW(), NOW()),

('MEM004', '정미자', '2025-03-20', '1947-05-17', 'F',
 '서울시 광진구', '306', 2, NOW(), NOW());

-- =========================
-- visitor (보호자/방문객)
-- =========================
INSERT INTO `visitor`
(`visitor_id`, `password`, `phone_no`, `visitor_name`, `address`,
 `relation_name`, `member_id`, `created_at`, `updated_at`)
VALUES
('VIS001', '1234', '010-1111-1111', '김민수', '서울시 강남구',
 '아들', 'MEM001', NOW(), NOW()),

('VIS002', '1234', '010-2222-2222', '이정희', '서울시 송파구',
 '딸', 'MEM002', NOW(), NOW()),

('VIS003', '1234', '010-3333-3333', '박성민', '서울시 강동구',
 '아들', 'MEM003', NOW(), NOW());

-- =========================
-- caregiver (요양보호사)
-- =========================
INSERT INTO `caregiver`
(`caregiver_id`, `password`, `caregiver_name`, `phone_no`, `address`,
 `created_at`, `updated_at`)
VALUES
(1, '1234', '최보호', '010-9000-1111', '서울시 강남구', NOW(), NOW()),
(2, '1234', '한케어', '010-9000-2222', '서울시 송파구', NOW(), NOW());

-- =========================
-- event_type
-- =========================
INSERT INTO `event_type`
(`event_type_id`, `event_type_name`, `created_at`, `updated_at`)
VALUES
(1, '낙상', NOW(), NOW()),
(2, '식사', NOW(), NOW()),
(3, '복약', NOW(), NOW()),
(4, '응급호출', NOW(), NOW()),
(5, '순찰이상', NOW(), NOW());

-- =========================
-- event
-- =========================
INSERT INTO `event`
(`event_name`, `description`, `event_at`,
 `member_id`, `event_type_id`, `created_at`, `updated_at`)
VALUES
('아침 식사 완료', '정상적으로 식사 완료', NOW(),
 'MEM001', 2, NOW(), NOW()),

('복약 완료', '혈압약 복용 완료', NOW(),
 'MEM002', 3, NOW(), NOW()),

('낙상 감지', '305호 앞 복도에서 쓰러짐 감지', NOW(),
 'MEM003', 1, NOW(), NOW()),

('응급 호출', '보호사 호출 버튼 입력', NOW(),
 'MEM004', 4, NOW(), NOW());

-- =========================
-- prescription
-- =========================
INSERT INTO `prescription`
(`prescription_image_path`, `member_id`, `created_at`, `updated_at`)
VALUES
('/images/prescription_001.png', 'MEM001', NOW(), NOW()),
('/images/prescription_002.png', 'MEM002', NOW(), NOW()),
('/images/prescription_003.png', 'MEM003', NOW(), NOW());

-- =========================
-- robot
-- =========================
INSERT INTO `robot`
(`robot_id`, `robot_type_name`, `ip_address`,
 `robot_status_name`, `robot_manager_name`,
 `created_at`, `updated_at`)
VALUES
('RB001', 'Pinky Pro', '192.168.0.101',
 '대기', '최보호', NOW(), NOW()),

('RB002', 'Pinky Pro', '192.168.0.102',
 '작업중', '한케어', NOW(), NOW()),

('RB003', 'JetCobot', '192.168.0.103',
 '충전중', '최보호', NOW(), NOW());

-- =========================
-- robot_event
-- =========================
INSERT INTO `robot_event`
(`robot_event_id`, `robot_event_type`, `event_description`,
 `event_at`, `created_at`, `updated_at`)
VALUES
(1, '운반', '약품 배송 완료', NOW(), NOW(), NOW()),
(2, '순찰', '3층 순찰 완료', NOW(), NOW(), NOW()),
(3, '안내', '방문객 302호 안내 완료', NOW(), NOW(), NOW()),
(4, '추종', '보호사 추종 시작', NOW(), NOW(), NOW());

-- =========================
-- supply
-- =========================
INSERT INTO `supply`
(`supply_type`, `item_name`, `quantity`, `created_at`, `updated_at`)
VALUES
('생활용품', '기저귀', 120, NOW(), NOW()),
('생활용품', '물티슈', 80, NOW(), NOW()),
('의약품', '혈압약', 35, NOW(), NOW()),
('의약품', '소화제', 50, NOW(), NOW()),
('생활용품', '휴지', 200, NOW(), NOW());

-- =========================
-- map_table
-- =========================
INSERT INTO `map_table`
(`location_id`, `location_name`,
 `location_coord_x1`, `location_coord_y1`,
 `location_coord_x2`, `location_coord_y2`,
 `created_at`, `updated_at`)
VALUES
(1, '301호', 1.0, 1.0, 2.0, 2.0, NOW(), NOW()),
(2, '302호', 3.0, 1.0, 4.0, 2.0, NOW(), NOW()),
(3, '305호', 1.0, 4.0, 2.0, 5.0, NOW(), NOW()),
(4, '간호스테이션', 5.0, 5.0, 7.0, 7.0, NOW(), NOW()),
(5, '면회실', 8.0, 2.0, 10.0, 4.0, NOW(), NOW()),
(6, '충전소', 0.0, 0.0, 1.0, 1.0, NOW(), NOW());