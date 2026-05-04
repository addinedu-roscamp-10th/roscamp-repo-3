SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM `idempotency_record`;
DELETE FROM `stream_metrics_log`;
DELETE FROM `ai_inference_log`;
DELETE FROM `robot_data_log`;
DELETE FROM `robot_runtime_status`;
DELETE FROM `command_execution`;
DELETE FROM `task_event_log`;
DELETE FROM `task_state_history`;
DELETE FROM `guide_task_detail`;
DELETE FROM `patrol_task_detail`;
DELETE FROM `delivery_task_item`;
DELETE FROM `delivery_task_detail`;
DELETE FROM `task`;
DELETE FROM `goal_pose`;
DELETE FROM `operation_zone`;
DELETE FROM `patrol_area`;
DELETE FROM `map_profile`;
DELETE FROM `item`;
DELETE FROM `member_event`;
DELETE FROM `prescription`;
DELETE FROM `preference`;
DELETE FROM `visitor`;
DELETE FROM `caregiver`;
DELETE FROM `robot`;
DELETE FROM `member`;

SET FOREIGN_KEY_CHECKS = 1;

-- =========================
-- member (어르신)
-- =========================
INSERT INTO `member`
(`member_id`, `member_name`, `admission_date`, `birth_date`, `gender_code`,
 `address`, `room_no`, `care_grade_code`, `created_at`, `updated_at`)
VALUES
(1, '김영수', '2025-01-10', '1942-03-11', 'M',
 '서울시 강남구', '301', 2, NOW(), NOW()),

(2, '이순자', '2025-02-15', '1945-08-22', 'F',
 '서울시 송파구', '302', 3, NOW(), NOW()),

(3, '박철호', '2025-03-01', '1939-11-09', 'M',
 '서울시 강동구', '305', 1, NOW(), NOW()),

(4, '정미자', '2025-03-20', '1947-05-17', 'F',
 '서울시 광진구', '306', 2, NOW(), NOW());

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
-- visitor (보호자/방문객)
-- =========================
INSERT INTO `visitor`
(`visitor_id`, `password`, `phone_no`, `visitor_name`, `address`,
 `relation_name`, `member_id`, `created_at`, `updated_at`)
VALUES
(1, '1234', '010-1111-1111', '김민수', '서울시 강남구',
 '아들', 1, NOW(), NOW()),

(2, '1234', '010-2222-2222', '이정희', '서울시 송파구',
 '딸', 2, NOW(), NOW()),

(3, '1234', '010-3333-3333', '박성민', '서울시 강동구',
 '아들', 3, NOW(), NOW());

-- =========================
-- preference
-- =========================
INSERT INTO `preference`
(`preference_id`, `member_id`, `preference`, `dislike`, `comment`, `created_at`, `updated_at`)
VALUES
(1, 1, '부드러운 음식, 산책', '매운 음식', '식사 속도가 느림', NOW(), NOW()),
(2, 2, 'TV 시청, 음악 감상', '소음', '낮잠 시간 중요', NOW(), NOW()),
(3, 3, '커피, 신문 읽기', '찬 음식', '아침 일찍 기상', NOW(), NOW());

-- =========================
-- prescription
-- =========================
INSERT INTO `prescription`
(`prescription_image_path`, `member_id`, `created_at`, `updated_at`)
VALUES
('/images/prescription_001.png', 1, NOW(), NOW()),
('/images/prescription_002.png', 2, NOW(), NOW()),
('/images/prescription_003.png', 3, NOW(), NOW());

-- =========================
-- member_event
-- =========================
INSERT INTO `member_event`
(`member_id`, `event_type_code`, `event_type_name`, `event_category`, `severity`,
 `event_name`, `description`, `event_at`, `created_at`, `updated_at`)
VALUES
(1, 'MEAL_RECORDED', '식사', 'CARE', 'INFO',
 '아침 식사 완료', '정상적으로 식사 완료', NOW(), NOW(), NOW()),

(2, 'MEDICATION_RECORDED', '복약', 'HEALTH', 'INFO',
 '복약 완료', '혈압약 복용 완료', NOW(), NOW(), NOW()),

(3, 'FALL_DETECTED', '낙상', 'HEALTH', 'CRITICAL',
 '낙상 감지', '305호 앞 복도에서 쓰러짐 감지', NOW(), NOW(), NOW()),

(4, 'STAFF_CALL', '직원 호출', 'CARE', 'WARNING',
 '직원 호출', '보호사 호출 버튼 입력', NOW(), NOW(), NOW());

-- =========================
-- robot
-- =========================
INSERT INTO `robot`
(`robot_id`, `robot_type_name`, `ip_address`,
 `robot_status_name`, `robot_manager_name`,
 `created_at`, `updated_at`)
VALUES
('pinky1', 'Pinky Pro', '192.168.0.101',
 'IDLE', '모바일팀', NOW(), NOW()),

('pinky2', 'Pinky Pro', '192.168.0.102',
 'IDLE', '모바일팀', NOW(), NOW()),

('pinky3', 'Pinky Pro', '192.168.0.103',
 'IDLE', '모바일팀', NOW(), NOW()),

('jetcobot1', 'JetCobot', '192.168.0.111',
 'IDLE', '운반팀', NOW(), NOW()),

('jetcobot2', 'JetCobot', '192.168.0.112',
 'IDLE', '운반팀', NOW(), NOW());

-- =========================
-- item
-- =========================
INSERT INTO `item`
(`item_id`, `item_type`, `item_name`, `quantity`, `created_at`, `updated_at`)
VALUES
(1, '생활용품', '기저귀', 120, NOW(), NOW()),
(2, '생활용품', '물티슈', 80, NOW(), NOW()),
(3, '의약품', '혈압약', 35, NOW(), NOW()),
(4, '의약품', '소화제', 50, NOW(), NOW()),
(5, '생활용품', '휴지', 200, NOW(), NOW()),
(6, '식료품', '두유', 60, NOW(), NOW());

-- =========================
-- map_profile
-- =========================
INSERT INTO `map_profile`
(`map_id`, `map_name`, `map_revision`, `git_ref`, `yaml_path`, `pgm_path`,
 `frame_id`, `is_active`, `created_at`, `updated_at`)
VALUES
('map_test11_0423', 'map_test11_0423', 1, NULL,
 'device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml',
 'device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm',
 'map', TRUE, NOW(), NOW());

-- =========================
-- operation_zone
-- =========================
INSERT INTO `operation_zone`
(`zone_id`, `map_id`, `zone_name`, `zone_type`, `revision`, `boundary_json`,
 `is_enabled`, `created_at`, `updated_at`)
VALUES
('room_301', 'map_test11_0423', '301호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":1.2,"y":-0.4},{"x":2.2,"y":-0.4},{"x":2.2,"y":0.5},{"x":1.2,"y":0.5}]}',
 TRUE, NOW(), NOW()),
('room_302', 'map_test11_0423', '302호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":2.6,"y":0.6},{"x":3.4,"y":0.6},{"x":3.4,"y":1.4},{"x":2.6,"y":1.4}]}',
 TRUE, NOW(), NOW()),
('room_305', 'map_test11_0423', '305호', 'ROOM', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.5,"y":3.5},{"x":1.5,"y":3.5},{"x":1.5,"y":4.5},{"x":0.5,"y":4.5}]}',
 TRUE, NOW(), NOW()),
('nursing_station', 'map_test11_0423', '간호스테이션', 'STAFF_STATION', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":-0.7,"y":0.8},{"x":0.3,"y":0.8},{"x":0.3,"y":1.6},{"x":-0.7,"y":1.6}]}',
 TRUE, NOW(), NOW()),
('supply_station', 'map_test11_0423', '물품 적재 위치', 'SUPPLY_STATION', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":-0.3,"y":-0.9},{"x":0.6,"y":-0.9},{"x":0.6,"y":-0.1},{"x":-0.3,"y":-0.1}]}',
 TRUE, NOW(), NOW()),
('dock', 'map_test11_0423', '충전소', 'DOCK', 1,
 '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.5,"y":-0.1},{"x":1.2,"y":-0.1},{"x":1.2,"y":0.6},{"x":0.5,"y":0.6}]}',
 TRUE, NOW(), NOW());

-- =========================
-- patrol_area
-- =========================
INSERT INTO `patrol_area`
(`patrol_area_id`, `map_id`, `patrol_area_name`, `revision`, `path_json`,
 `is_enabled`, `created_at`, `updated_at`)
VALUES
('patrol_ward_night_01', 'map_test11_0423', '야간 병동 순찰', 7,
 '{"header":{"frame_id":"map"},"poses":[{"x":0.1665755137108074,"y":-0.4496830900440016,"yaw":1.5707963267948966},{"x":1.6946025435218914,"y":0.0043433854992070454,"yaw":0.0},{"x":0.8577123880386353,"y":0.25597259402275085,"yaw":0.0}]}',
 TRUE, NOW(), NOW());

-- =========================
-- goal_pose
-- =========================
INSERT INTO `goal_pose`
(`goal_pose_id`, `map_id`, `zone_id`, `purpose`, `pose_x`, `pose_y`, `pose_yaw`,
 `frame_id`, `is_enabled`, `created_at`, `updated_at`)
VALUES
('pickup_supply', 'map_test11_0423', 'supply_station', 'PICKUP', 0.1665755137108074, -0.4496830900440016, 1.5707963267948966,
 'map', TRUE, NOW(), NOW()),

('delivery_room_301', 'map_test11_0423', 'room_301', 'DESTINATION', 1.6946025435218914, 0.0043433854992070454, 0.0,
 'map', TRUE, NOW(), NOW()),

('delivery_room_302', 'map_test11_0423', 'room_302', 'DESTINATION', 3.0, 1.0, 0.0,
 'map', TRUE, NOW(), NOW()),

('delivery_room_305', 'map_test11_0423', 'room_305', 'DESTINATION', 1.0, 4.0, 0.0,
 'map', TRUE, NOW(), NOW()),

('dock_home', 'map_test11_0423', 'dock', 'DOCK', 0.8577123880386353, 0.25597259402275085, 0.0,
 'map', TRUE, NOW(), NOW());

-- =========================
-- sample task / logs
-- =========================
INSERT INTO `task`
(`task_id`, `task_type`, `request_id`, `idempotency_key`, `requester_type`, `requester_id`,
 `priority`, `task_status`, `phase`, `assigned_robot_id`, `map_id`,
 `created_at`, `updated_at`, `started_at`)
VALUES
(1, 'DELIVERY', 'seed_delivery_001', 'seed_delivery_001', 'CAREGIVER', '1',
 'NORMAL', 'RUNNING', 'MOVE_TO_PICKUP', 'pinky2', 'map_test11_0423',
 NOW(3), NOW(3), NOW(3));

INSERT INTO `delivery_task_detail`
(`task_id`, `pickup_goal_pose_id`, `destination_goal_pose_id`,
 `pickup_arm_robot_id`, `dropoff_arm_robot_id`, `robot_slot_id`, `notes`)
VALUES
(1, 'pickup_supply', 'delivery_room_301', 'jetcobot1', 'jetcobot2', 'front_tray',
 'seed 운반 task');

INSERT INTO `delivery_task_item`
(`task_id`, `item_id`, `requested_quantity`, `loaded_quantity`, `delivered_quantity`,
 `item_status`, `created_at`, `updated_at`)
VALUES
(1, 2, 1, 0, 0, 'REQUESTED', NOW(), NOW());

INSERT INTO `task_state_history`
(`task_id`, `from_status`, `to_status`, `from_phase`, `to_phase`, `reason_code`,
 `message`, `changed_by_component`, `changed_at`)
VALUES
(1, NULL, 'RUNNING', NULL, 'MOVE_TO_PICKUP', NULL,
 'seed task started', 'seed', NOW(3));

INSERT INTO `task_event_log`
(`task_id`, `event_name`, `severity`, `component`, `robot_id`, `correlation_id`,
 `result_code`, `reason_code`, `message`, `payload_json`, `occurred_at`, `created_at`)
VALUES
(1, 'TASK_STARTED', 'INFO', 'control_service', 'pinky2', NULL,
 'SUCCESS', NULL, 'seed delivery task started', NULL, NOW(3), NOW(3));

INSERT INTO `command_execution`
(`task_id`, `transport`, `command_type`, `command_phase`, `target_component`,
 `target_robot_id`, `target_endpoint`, `request_json`, `accepted`, `result_code`,
 `result_message`, `response_json`, `started_at`, `finished_at`, `elapsed_ms`)
VALUES
(1, 'ROS_ACTION', 'NAVIGATE_TO_GOAL', 'MOVE_TO_PICKUP', 'pinky',
 'pinky2', '/ropi/control/pinky2/navigate_to_goal',
 '{"task_id":"1","nav_phase":"DELIVERY_PICKUP"}',
 TRUE, 'SUCCESS', 'seed command result', '{"result_code":"SUCCESS"}',
 NOW(3), NOW(3), 1200);

INSERT INTO `robot_runtime_status`
(`robot_id`, `robot_kind`, `runtime_state`, `active_task_id`, `battery_percent`,
 `pose_x`, `pose_y`, `pose_yaw`, `frame_id`, `fault_code`, `last_seen_at`, `updated_at`)
VALUES
('pinky2', 'PINKY', 'RUNNING', 1, 87.5, 1.2, 0.8, 0.0, 'map', NULL,
 DATE_SUB(NOW(3), INTERVAL 1 DAY), DATE_SUB(NOW(3), INTERVAL 1 DAY));
