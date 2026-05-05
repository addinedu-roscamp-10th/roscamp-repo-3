SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `idempotency_record`;
DROP TABLE IF EXISTS `kiosk_staff_call_log`;
DROP TABLE IF EXISTS `stream_metrics_log`;
DROP TABLE IF EXISTS `ai_inference_log`;
DROP TABLE IF EXISTS `robot_data_log`;
DROP TABLE IF EXISTS `robot_runtime_status`;
DROP TABLE IF EXISTS `command_execution`;
DROP TABLE IF EXISTS `task_event_log`;
DROP TABLE IF EXISTS `task_state_history`;
DROP TABLE IF EXISTS `guide_task_detail`;
DROP TABLE IF EXISTS `patrol_task_zone`;
DROP TABLE IF EXISTS `patrol_task_detail`;
DROP TABLE IF EXISTS `delivery_task_item`;
DROP TABLE IF EXISTS `delivery_task_detail`;
DROP TABLE IF EXISTS `task`;
DROP TABLE IF EXISTS `fms_route_waypoint`;
DROP TABLE IF EXISTS `fms_route`;
DROP TABLE IF EXISTS `fms_edge`;
DROP TABLE IF EXISTS `fms_waypoint`;
DROP TABLE IF EXISTS `goal_pose`;
DROP TABLE IF EXISTS `operation_zone`;
DROP TABLE IF EXISTS `patrol_area`;
DROP TABLE IF EXISTS `map_profile`;
DROP TABLE IF EXISTS `item`;
DROP TABLE IF EXISTS `member_event`;
DROP TABLE IF EXISTS `prescription`;
DROP TABLE IF EXISTS `preference`;
DROP TABLE IF EXISTS `visitor`;
DROP TABLE IF EXISTS `caregiver`;
DROP TABLE IF EXISTS `robot`;
DROP TABLE IF EXISTS `member`;

-- Legacy tables removed by the new logical design.
DROP TABLE IF EXISTS `event`;
DROP TABLE IF EXISTS `event_type`;
DROP TABLE IF EXISTS `robot_event`;
DROP TABLE IF EXISTS `supply`;
DROP TABLE IF EXISTS `map_table`;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `member` (
    `member_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `member_name` VARCHAR(30) NOT NULL,
    `admission_date` DATE NOT NULL,
    `birth_date` DATE NOT NULL,
    `gender_code` CHAR(1) NOT NULL,
    `address` VARCHAR(255) NULL,
    `room_no` VARCHAR(20) NOT NULL,
    `care_grade_code` SMALLINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_member` PRIMARY KEY (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `caregiver` (
    `caregiver_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `password` VARCHAR(255) NOT NULL,
    `caregiver_name` VARCHAR(30) NOT NULL,
    `phone_no` VARCHAR(20) NOT NULL,
    `address` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_caregiver` PRIMARY KEY (`caregiver_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `visitor` (
    `visitor_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `password` VARCHAR(255) NOT NULL,
    `phone_no` VARCHAR(20) NOT NULL,
    `visitor_name` VARCHAR(30) NOT NULL,
    `address` VARCHAR(255) NULL,
    `relation_name` VARCHAR(20) NOT NULL,
    `member_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_visitor` PRIMARY KEY (`visitor_id`),
    CONSTRAINT `fk_visitor_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `preference` (
    `preference_id` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `member_id` BIGINT UNSIGNED NOT NULL,
    `preference` TEXT NOT NULL,
    `dislike` TEXT NOT NULL,
    `comment` TEXT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_preference` PRIMARY KEY (`preference_id`),
    CONSTRAINT `fk_preference_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`),
    UNIQUE KEY `uq_preference_member` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `prescription` (
    `prescription_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `prescription_image_path` VARCHAR(500) NOT NULL,
    `member_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_prescription` PRIMARY KEY (`prescription_id`),
    CONSTRAINT `fk_prescription_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `member_event` (
    `member_event_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `member_id` BIGINT UNSIGNED NOT NULL,
    `event_type_code` VARCHAR(50) NOT NULL,
    `event_type_name` VARCHAR(50) NOT NULL,
    `event_category` VARCHAR(30) NOT NULL,
    `severity` VARCHAR(20) NOT NULL,
    `event_name` VARCHAR(100) NOT NULL,
    `description` TEXT NOT NULL,
    `event_at` DATETIME NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_member_event` PRIMARY KEY (`member_event_id`),
    CONSTRAINT `fk_member_event_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`),
    KEY `idx_member_event_member_event_at` (`member_id`, `event_at`),
    KEY `idx_member_event_type_event_at` (`event_type_code`, `event_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `robot` (
    `robot_id` VARCHAR(50) NOT NULL,
    `robot_type_name` VARCHAR(50) NOT NULL,
    `ip_address` VARCHAR(45) NOT NULL,
    `robot_status_name` VARCHAR(30) NOT NULL,
    `robot_manager_name` VARCHAR(50) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_robot` PRIMARY KEY (`robot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `item` (
    `item_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `item_type` VARCHAR(100) NOT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `quantity` INT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_item` PRIMARY KEY (`item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `map_profile` (
    `map_id` VARCHAR(100) NOT NULL,
    `map_name` VARCHAR(100) NOT NULL,
    `map_revision` INT UNSIGNED NOT NULL,
    `git_ref` VARCHAR(100) NULL,
    `yaml_path` VARCHAR(500) NOT NULL,
    `pgm_path` VARCHAR(500) NOT NULL,
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `is_active` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_map_profile` PRIMARY KEY (`map_id`),
    UNIQUE KEY `uq_map_profile_name_revision` (`map_name`, `map_revision`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `operation_zone` (
    `zone_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `zone_name` VARCHAR(100) NOT NULL,
    `zone_type` VARCHAR(50) NOT NULL,
    `revision` INT UNSIGNED NOT NULL DEFAULT 1,
    `boundary_json` JSON NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_operation_zone` PRIMARY KEY (`zone_id`),
    CONSTRAINT `fk_operation_zone_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `patrol_area` (
    `patrol_area_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `patrol_area_name` VARCHAR(100) NOT NULL,
    `revision` INT UNSIGNED NOT NULL DEFAULT 1,
    `path_json` JSON NOT NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_patrol_area` PRIMARY KEY (`patrol_area_id`),
    CONSTRAINT `fk_patrol_area_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_patrol_area_map_enabled_name` (`map_id`, `is_enabled`, `patrol_area_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `goal_pose` (
    `goal_pose_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `zone_id` VARCHAR(100) NULL,
    `purpose` VARCHAR(50) NOT NULL,
    `pose_x` DOUBLE NOT NULL,
    `pose_y` DOUBLE NOT NULL,
    `pose_yaw` DOUBLE NOT NULL,
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_goal_pose` PRIMARY KEY (`goal_pose_id`),
    CONSTRAINT `fk_goal_pose_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    CONSTRAINT `fk_goal_pose_operation_zone`
        FOREIGN KEY (`zone_id`)
        REFERENCES `operation_zone` (`zone_id`),
    KEY `idx_goal_pose_map_purpose` (`map_id`, `purpose`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fms_waypoint` (
    `waypoint_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `display_name` VARCHAR(100) NOT NULL,
    `waypoint_type` VARCHAR(50) NOT NULL,
    `pose_x` DOUBLE NOT NULL,
    `pose_y` DOUBLE NOT NULL,
    `pose_yaw` DOUBLE NOT NULL,
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `snap_group` VARCHAR(100) NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_waypoint` PRIMARY KEY (`waypoint_id`),
    CONSTRAINT `fk_fms_waypoint_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_fms_waypoint_map_enabled_name`
        (`map_id`, `is_enabled`, `display_name`),
    KEY `idx_fms_waypoint_map_type`
        (`map_id`, `waypoint_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fms_edge` (
    `edge_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `from_waypoint_id` VARCHAR(100) NOT NULL,
    `to_waypoint_id` VARCHAR(100) NOT NULL,
    `is_bidirectional` BOOLEAN NOT NULL DEFAULT TRUE,
    `traversal_cost` DOUBLE NULL,
    `priority` INT NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_edge` PRIMARY KEY (`edge_id`),
    CONSTRAINT `fk_fms_edge_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    CONSTRAINT `fk_fms_edge_from_waypoint`
        FOREIGN KEY (`from_waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    CONSTRAINT `fk_fms_edge_to_waypoint`
        FOREIGN KEY (`to_waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    KEY `idx_fms_edge_map_enabled`
        (`map_id`, `is_enabled`),
    KEY `idx_fms_edge_from_to`
        (`from_waypoint_id`, `to_waypoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fms_route` (
    `route_id` VARCHAR(100) NOT NULL,
    `map_id` VARCHAR(100) NOT NULL,
    `route_name` VARCHAR(100) NOT NULL,
    `route_scope` VARCHAR(20) NOT NULL,
    `revision` INT UNSIGNED NOT NULL DEFAULT 1,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_route` PRIMARY KEY (`route_id`),
    CONSTRAINT `fk_fms_route_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_fms_route_map_scope_enabled_name`
        (`map_id`, `route_scope`, `is_enabled`, `route_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fms_route_waypoint` (
    `route_id` VARCHAR(100) NOT NULL,
    `sequence_no` INT UNSIGNED NOT NULL,
    `waypoint_id` VARCHAR(100) NOT NULL,
    `yaw_policy` VARCHAR(20) NOT NULL DEFAULT 'AUTO_NEXT',
    `fixed_pose_yaw` DOUBLE NULL,
    `stop_required` BOOLEAN NOT NULL DEFAULT TRUE,
    `dwell_sec` DOUBLE NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_fms_route_waypoint` PRIMARY KEY (`route_id`, `sequence_no`),
    CONSTRAINT `fk_fms_route_waypoint_route`
        FOREIGN KEY (`route_id`)
        REFERENCES `fms_route` (`route_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_fms_route_waypoint_waypoint`
        FOREIGN KEY (`waypoint_id`)
        REFERENCES `fms_waypoint` (`waypoint_id`),
    KEY `idx_fms_route_waypoint_waypoint` (`waypoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `task` (
    `task_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_type` VARCHAR(20) NOT NULL,
    `request_id` VARCHAR(100) NOT NULL,
    `idempotency_key` VARCHAR(100) NULL,
    `requester_type` VARCHAR(20) NOT NULL,
    `requester_id` VARCHAR(100) NOT NULL,
    `priority` VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    `task_status` VARCHAR(30) NOT NULL,
    `phase` VARCHAR(50) NULL,
    `assigned_robot_id` VARCHAR(50) NULL,
    `latest_reason_code` VARCHAR(100) NULL,
    `result_code` VARCHAR(50) NULL,
    `result_message` TEXT NULL,
    `map_id` VARCHAR(100) NULL,
    `created_at` DATETIME(3) NOT NULL,
    `updated_at` DATETIME(3) NOT NULL,
    `started_at` DATETIME(3) NULL,
    `finished_at` DATETIME(3) NULL,
    CONSTRAINT `pk_task` PRIMARY KEY (`task_id`),
    CONSTRAINT `fk_task_assigned_robot`
        FOREIGN KEY (`assigned_robot_id`)
        REFERENCES `robot` (`robot_id`),
    CONSTRAINT `fk_task_map_profile`
        FOREIGN KEY (`map_id`)
        REFERENCES `map_profile` (`map_id`),
    KEY `idx_task_status_type_created_at` (`task_status`, `task_type`, `created_at`),
    KEY `idx_task_robot_status_updated_at` (`assigned_robot_id`, `task_status`, `updated_at`),
    KEY `idx_task_requester_created_at` (`requester_type`, `requester_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `delivery_task_detail` (
    `task_id` BIGINT UNSIGNED NOT NULL,
    `pickup_goal_pose_id` VARCHAR(100) NOT NULL,
    `destination_goal_pose_id` VARCHAR(100) NOT NULL,
    `pickup_arm_robot_id` VARCHAR(50) NULL,
    `dropoff_arm_robot_id` VARCHAR(50) NULL,
    `robot_slot_id` VARCHAR(50) NULL,
    `notes` TEXT NULL,
    CONSTRAINT `pk_delivery_task_detail` PRIMARY KEY (`task_id`),
    CONSTRAINT `fk_delivery_task_detail_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_delivery_task_detail_pickup_goal`
        FOREIGN KEY (`pickup_goal_pose_id`)
        REFERENCES `goal_pose` (`goal_pose_id`),
    CONSTRAINT `fk_delivery_task_detail_destination_goal`
        FOREIGN KEY (`destination_goal_pose_id`)
        REFERENCES `goal_pose` (`goal_pose_id`),
    CONSTRAINT `fk_delivery_task_detail_pickup_arm`
        FOREIGN KEY (`pickup_arm_robot_id`)
        REFERENCES `robot` (`robot_id`),
    CONSTRAINT `fk_delivery_task_detail_dropoff_arm`
        FOREIGN KEY (`dropoff_arm_robot_id`)
        REFERENCES `robot` (`robot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `delivery_task_item` (
    `delivery_task_item_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NOT NULL,
    `item_id` BIGINT UNSIGNED NOT NULL,
    `requested_quantity` INT UNSIGNED NOT NULL,
    `loaded_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
    `delivered_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
    `item_status` VARCHAR(30) NOT NULL DEFAULT 'REQUESTED',
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_delivery_task_item` PRIMARY KEY (`delivery_task_item_id`),
    CONSTRAINT `fk_delivery_task_item_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_delivery_task_item_item`
        FOREIGN KEY (`item_id`)
        REFERENCES `item` (`item_id`),
    KEY `idx_delivery_task_item_task` (`task_id`),
    KEY `idx_delivery_task_item_item` (`item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `patrol_task_detail` (
    `task_id` BIGINT UNSIGNED NOT NULL,
    `patrol_area_id` VARCHAR(100) NOT NULL,
    `patrol_area_revision` INT UNSIGNED NOT NULL,
    `patrol_status` VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    `frame_id` VARCHAR(50) NOT NULL DEFAULT 'map',
    `waypoint_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `current_waypoint_index` INT UNSIGNED NULL,
    `path_snapshot_json` JSON NOT NULL,
    `notes` TEXT NULL,
    CONSTRAINT `pk_patrol_task_detail` PRIMARY KEY (`task_id`),
    CONSTRAINT `fk_patrol_task_detail_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_patrol_task_detail_patrol_area`
        FOREIGN KEY (`patrol_area_id`)
        REFERENCES `patrol_area` (`patrol_area_id`),
    KEY `idx_patrol_task_detail_area_revision` (`patrol_area_id`, `patrol_area_revision`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `guide_task_detail` (
    `task_id` BIGINT UNSIGNED NOT NULL,
    `visitor_id` BIGINT UNSIGNED NOT NULL,
    `member_id` BIGINT UNSIGNED NOT NULL,
    `destination_goal_pose_id` VARCHAR(100) NOT NULL,
    `guide_phase` VARCHAR(50) NULL,
    `target_track_id` VARCHAR(100) NULL,
    `notes` TEXT NULL,
    CONSTRAINT `pk_guide_task_detail` PRIMARY KEY (`task_id`),
    CONSTRAINT `fk_guide_task_detail_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_guide_task_detail_visitor`
        FOREIGN KEY (`visitor_id`)
        REFERENCES `visitor` (`visitor_id`),
    CONSTRAINT `fk_guide_task_detail_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`),
    CONSTRAINT `fk_guide_task_detail_goal_pose`
        FOREIGN KEY (`destination_goal_pose_id`)
        REFERENCES `goal_pose` (`goal_pose_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `task_state_history` (
    `task_state_history_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NOT NULL,
    `from_status` VARCHAR(30) NULL,
    `to_status` VARCHAR(30) NOT NULL,
    `from_phase` VARCHAR(50) NULL,
    `to_phase` VARCHAR(50) NULL,
    `reason_code` VARCHAR(100) NULL,
    `message` TEXT NULL,
    `changed_by_component` VARCHAR(100) NOT NULL,
    `changed_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_task_state_history` PRIMARY KEY (`task_state_history_id`),
    CONSTRAINT `fk_task_state_history_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    KEY `idx_task_state_history_task_changed_at` (`task_id`, `changed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `task_event_log` (
    `task_event_log_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NOT NULL,
    `event_name` VARCHAR(100) NOT NULL,
    `severity` VARCHAR(20) NOT NULL,
    `component` VARCHAR(100) NOT NULL,
    `robot_id` VARCHAR(50) NULL,
    `correlation_id` VARCHAR(100) NULL,
    `result_code` VARCHAR(50) NULL,
    `reason_code` VARCHAR(100) NULL,
    `message` TEXT NULL,
    `payload_json` JSON NULL,
    `occurred_at` DATETIME(3) NOT NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_task_event_log` PRIMARY KEY (`task_event_log_id`),
    CONSTRAINT `fk_task_event_log_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_task_event_log_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`),
    KEY `idx_task_event_log_task_occurred_at` (`task_id`, `occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `command_execution` (
    `command_execution_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NULL,
    `transport` VARCHAR(30) NOT NULL,
    `command_type` VARCHAR(50) NOT NULL,
    `command_phase` VARCHAR(50) NULL,
    `target_component` VARCHAR(100) NOT NULL,
    `target_robot_id` VARCHAR(50) NULL,
    `target_endpoint` VARCHAR(255) NULL,
    `request_json` JSON NULL,
    `accepted` BOOLEAN NULL,
    `result_code` VARCHAR(50) NULL,
    `result_message` TEXT NULL,
    `response_json` JSON NULL,
    `started_at` DATETIME(3) NOT NULL,
    `finished_at` DATETIME(3) NULL,
    `elapsed_ms` INT UNSIGNED NULL,
    CONSTRAINT `pk_command_execution` PRIMARY KEY (`command_execution_id`),
    CONSTRAINT `fk_command_execution_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    CONSTRAINT `fk_command_execution_robot`
        FOREIGN KEY (`target_robot_id`)
        REFERENCES `robot` (`robot_id`),
    KEY `idx_command_execution_task_started_at` (`task_id`, `started_at`),
    KEY `idx_command_execution_robot_started_at` (`target_robot_id`, `started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `robot_runtime_status` (
    `robot_id` VARCHAR(50) NOT NULL,
    `robot_kind` VARCHAR(50) NOT NULL,
    `runtime_state` VARCHAR(50) NOT NULL,
    `active_task_id` BIGINT UNSIGNED NULL,
    `battery_percent` FLOAT NULL,
    `pose_x` DOUBLE NULL,
    `pose_y` DOUBLE NULL,
    `pose_yaw` DOUBLE NULL,
    `frame_id` VARCHAR(50) NULL,
    `fault_code` VARCHAR(100) NULL,
    `last_seen_at` DATETIME(3) NOT NULL,
    `updated_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_robot_runtime_status` PRIMARY KEY (`robot_id`),
    CONSTRAINT `fk_robot_runtime_status_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_robot_runtime_status_task`
        FOREIGN KEY (`active_task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `robot_data_log` (
    `robot_data_log_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `robot_id` VARCHAR(50) NOT NULL,
    `task_id` BIGINT UNSIGNED NULL,
    `data_type` VARCHAR(50) NOT NULL,
    `pose_x` DOUBLE NULL,
    `pose_y` DOUBLE NULL,
    `pose_yaw` DOUBLE NULL,
    `battery_percent` FLOAT NULL,
    `payload_json` JSON NULL,
    `sampled_at` DATETIME(3) NULL,
    `received_at` DATETIME(3) NOT NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_robot_data_log` PRIMARY KEY (`robot_data_log_id`),
    CONSTRAINT `fk_robot_data_log_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`),
    CONSTRAINT `fk_robot_data_log_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    KEY `idx_robot_data_log_robot_received_at` (`robot_id`, `received_at`),
    KEY `idx_robot_data_log_task_received_at` (`task_id`, `received_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `ai_inference_log` (
    `ai_inference_log_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NULL,
    `robot_id` VARCHAR(50) NULL,
    `stream_name` VARCHAR(50) NOT NULL,
    `frame_id` VARCHAR(100) NULL,
    `inference_type` VARCHAR(50) NOT NULL,
    `confidence` FLOAT NULL,
    `result_json` JSON NULL,
    `inferred_at` DATETIME(3) NOT NULL,
    `received_at` DATETIME(3) NOT NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_ai_inference_log` PRIMARY KEY (`ai_inference_log_id`),
    CONSTRAINT `fk_ai_inference_log_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    CONSTRAINT `fk_ai_inference_log_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`),
    KEY `idx_ai_inference_task_inferred_at` (`task_id`, `inferred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `stream_metrics_log` (
    `stream_metrics_log_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_id` BIGINT UNSIGNED NULL,
    `robot_id` VARCHAR(50) NULL,
    `stream_name` VARCHAR(50) NOT NULL,
    `direction` VARCHAR(50) NOT NULL,
    `window_started_at` DATETIME(3) NOT NULL,
    `window_ended_at` DATETIME(3) NOT NULL,
    `received_frame_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `relayed_frame_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `dropped_frame_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `dropped_frame_rate` FLOAT NOT NULL DEFAULT 0,
    `incomplete_frame_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `crc_mismatch_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `assembly_timeout_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `avg_latency_ms` FLOAT NULL,
    `max_latency_ms` FLOAT NULL,
    `latest_frame_id` BIGINT UNSIGNED NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_stream_metrics_log` PRIMARY KEY (`stream_metrics_log_id`),
    CONSTRAINT `fk_stream_metrics_log_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    CONSTRAINT `fk_stream_metrics_log_robot`
        FOREIGN KEY (`robot_id`)
        REFERENCES `robot` (`robot_id`),
    KEY `idx_stream_metrics_robot_window` (`robot_id`, `stream_name`, `window_started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `kiosk_staff_call_log` (
    `kiosk_staff_call_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `idempotency_key` VARCHAR(100) NOT NULL,
    `request_hash` CHAR(64) NOT NULL,
    `call_type` VARCHAR(100) NOT NULL,
    `description` TEXT NULL,
    `visitor_id` BIGINT UNSIGNED NULL,
    `member_id` BIGINT UNSIGNED NULL,
    `kiosk_id` VARCHAR(100) NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_kiosk_staff_call_log` PRIMARY KEY (`kiosk_staff_call_id`),
    CONSTRAINT `fk_kiosk_staff_call_visitor`
        FOREIGN KEY (`visitor_id`)
        REFERENCES `visitor` (`visitor_id`)
        ON DELETE SET NULL,
    CONSTRAINT `fk_kiosk_staff_call_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`)
        ON DELETE SET NULL,
    UNIQUE KEY `uq_kiosk_staff_call_idempotency` (`idempotency_key`),
    KEY `idx_kiosk_staff_call_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `idempotency_record` (
    `idempotency_record_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `scope` VARCHAR(50) NOT NULL,
    `requester_type` VARCHAR(20) NOT NULL,
    `requester_id` VARCHAR(100) NOT NULL,
    `idempotency_key` VARCHAR(100) NOT NULL,
    `request_hash` CHAR(64) NOT NULL,
    `response_json` JSON NULL,
    `task_id` BIGINT UNSIGNED NULL,
    `expires_at` DATETIME(3) NOT NULL,
    `created_at` DATETIME(3) NOT NULL,
    CONSTRAINT `pk_idempotency_record` PRIMARY KEY (`idempotency_record_id`),
    CONSTRAINT `fk_idempotency_record_task`
        FOREIGN KEY (`task_id`)
        REFERENCES `task` (`task_id`)
        ON DELETE SET NULL,
    UNIQUE KEY `uq_idempotency` (
        `scope`,
        `requester_type`,
        `requester_id`,
        `idempotency_key`
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
