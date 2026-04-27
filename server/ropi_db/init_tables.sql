SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `preference`;
DROP TABLE IF EXISTS `member`;
DROP TABLE IF EXISTS `visitor`;
DROP TABLE IF EXISTS `event`;
DROP TABLE IF EXISTS `event_type`;
DROP TABLE IF EXISTS `prescription`;
DROP TABLE IF EXISTS `robot`;
DROP TABLE IF EXISTS `robot_event`;
DROP TABLE IF EXISTS `supply`;
DROP TABLE IF EXISTS `map_table`;
DROP TABLE IF EXISTS `caregiver`;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `preference` (
    `preference_id` SMALLINT UNSIGNED NOT NULL,
    `preference` TEXT NOT NULL,
    `dislike` TEXT NOT NULL,
    `comment` TEXT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_preference_id` PRIMARY KEY (`preference_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `member` (
    `member_id` VARCHAR(50) NOT NULL,
    `member_name` VARCHAR(10) NOT NULL,
    `admission_date` DATE NOT NULL,
    `birth_date` DATE NOT NULL,
    `gender_code` CHAR(1) NOT NULL,
    `address` VARCHAR(255) NULL,
    `room_no` VARCHAR(10) NOT NULL,
    `care_grade_code` SMALLINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_member` PRIMARY KEY (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `visitor` (
    `visitor_id` VARCHAR(100) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `phone_no` VARCHAR(20) NOT NULL,
    `visitor_name` VARCHAR(30) NOT NULL,
    `address` VARCHAR(255) NULL,
    `relation_name` VARCHAR(20) NOT NULL,
    `member_id` VARCHAR(50) NOT NULL,
    `created_at` DATETIME NULL,
    `updated_at` DATETIME NULL,
    CONSTRAINT `pk_visitor` PRIMARY KEY (`visitor_id`),
    CONSTRAINT `fk_visitor_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `event_type` (
    `event_type_id` SMALLINT UNSIGNED NOT NULL,
    `event_type_name` VARCHAR(30) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_event_type` PRIMARY KEY (`event_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `event` (
    `event_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `event_name` VARCHAR(100) NOT NULL,
    `description` TEXT NOT NULL,
    `event_at` DATETIME NOT NULL,
    `member_id` VARCHAR(50) NOT NULL,
    `event_type_id` SMALLINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_event` PRIMARY KEY (`event_id`),
    CONSTRAINT `fk_event_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`),
    CONSTRAINT `fk_event_type`
        FOREIGN KEY (`event_type_id`)
        REFERENCES `event_type` (`event_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `prescription` (
    `prescription_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `prescription_image_path` VARCHAR(500) NOT NULL,
    `member_id` VARCHAR(50) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_prescription` PRIMARY KEY (`prescription_id`),
    CONSTRAINT `fk_prescription_member`
        FOREIGN KEY (`member_id`)
        REFERENCES `member` (`member_id`)
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

CREATE TABLE `robot_event` (
    `robot_event_id` BIGINT UNSIGNED NOT NULL,
    `robot_event_type` VARCHAR(10) NOT NULL,
    `event_description` TEXT NOT NULL,
    `event_at` DATETIME NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_robot_event` PRIMARY KEY (`robot_event_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE `supply` (
    `supply_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `supply_type` VARCHAR(100) NOT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `quantity` INT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_supply` PRIMARY KEY (`supply_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `map_table` (
    `location_id` BIGINT UNSIGNED NOT NULL,
    `location_name` VARCHAR(100) NOT NULL,
    `location_coord_x1` FLOAT NOT NULL,
    `location_coord_y1` FLOAT NOT NULL,
    `location_coord_x2` FLOAT NOT NULL,
    `location_coord_y2` FLOAT NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_location_id` PRIMARY KEY (`location_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `caregiver` (
    `caregiver_id` BIGINT UNSIGNED NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `caregiver_name` VARCHAR(30) NOT NULL,
    `phone_no` VARCHAR(20) NOT NULL,
    `address` VARCHAR(255) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    CONSTRAINT `pk_caregiver` PRIMARY KEY (`caregiver_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
