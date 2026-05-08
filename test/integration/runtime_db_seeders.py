import json
import uuid

import pytest

from server.ropi_main_service.application.guide_runtime import get_guide_map_id
from server.ropi_main_service.persistence.connection import fetch_one, get_connection


def safe_fetch_one(query: str, params=None):
    try:
        return fetch_one(query, params)
    except Exception:
        return None


def _zone_id_from_room(room_no) -> str:
    raw = str(room_no or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("room_"):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits:
        return f"room_{digits}"
    return f"room_{raw.replace(' ', '_')}"


def _find_guide_destination_visitor(guide_map_id: str):
    return safe_fetch_one(
        """
        SELECT
            v.visitor_id,
            v.member_id,
            m.member_name,
            m.room_no,
            gp.goal_pose_id,
            gp.map_id,
            gp.zone_id,
            gp.purpose
        FROM visitor v
        JOIN member m
          ON m.member_id = v.member_id
        JOIN goal_pose gp
          ON gp.zone_id = CONCAT('room_', m.room_no)
         AND gp.map_id = %s
         AND gp.is_enabled = TRUE
         AND gp.purpose IN ('GUIDE_DESTINATION', 'DESTINATION')
        ORDER BY
            v.visitor_id,
            FIELD(gp.purpose, 'GUIDE_DESTINATION', 'DESTINATION'),
            gp.goal_pose_id
        LIMIT 1
        """,
        (guide_map_id,),
    )


@pytest.fixture
def guide_destination_seed():
    guide_map_id = get_guide_map_id()
    existing = _find_guide_destination_visitor(guide_map_id)
    if existing is not None:
        yield existing
        return

    visitor_row = safe_fetch_one(
        """
        SELECT
            v.visitor_id,
            v.member_id,
            m.member_name,
            m.room_no
        FROM visitor v
        JOIN member m
          ON m.member_id = v.member_id
        ORDER BY v.visitor_id
        LIMIT 1
        """
    )
    assert visitor_row is not None, "The runtime DB has no visitor/member row."

    room_no = visitor_row["room_no"]
    zone_id = _zone_id_from_room(room_no)
    assert zone_id, "The selected visitor member has no room_no for guide destination."

    goal_pose_id = f"it_guide_{zone_id}_{uuid.uuid4().hex[:8]}"
    inserted_map_profile = False
    inserted_zone = False
    inserted_goal_pose = False

    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute("SELECT map_id FROM map_profile WHERE map_id = %s", (guide_map_id,))
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO map_profile
                    (map_id, map_name, map_revision, git_ref, yaml_path, pgm_path,
                     frame_id, is_active, created_at, updated_at)
                    VALUES
                    (%s, %s, 1, NULL,
                     %s, %s,
                     'map', FALSE, NOW(), NOW())
                    """,
                    (
                        guide_map_id,
                        guide_map_id,
                        f"device/ropi_mobile/src/ropi_nav_config/maps/{guide_map_id}.yaml",
                        f"device/ropi_mobile/src/ropi_nav_config/maps/{guide_map_id}.pgm",
                    ),
                )
                inserted_map_profile = True

            cursor.execute(
                "SELECT zone_id FROM operation_zone WHERE map_id = %s AND zone_id = %s",
                (guide_map_id, zone_id),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO operation_zone
                    (zone_id, map_id, zone_name, zone_type, revision, boundary_json,
                     is_enabled, created_at, updated_at)
                    VALUES
                    (%s, %s, %s, 'ROOM', 1, NULL,
                     TRUE, NOW(), NOW())
                    """,
                    (zone_id, guide_map_id, f"{room_no}호"),
                )
                inserted_zone = True

            cursor.execute(
                """
                INSERT INTO goal_pose
                (goal_pose_id, map_id, zone_id, purpose, pose_x, pose_y, pose_yaw,
                 frame_id, is_enabled, created_at, updated_at)
                VALUES
                (%s, %s, %s, 'GUIDE_DESTINATION', 0.0, 0.0, 0.0,
                 'map', TRUE, NOW(), NOW())
                """,
                (goal_pose_id, guide_map_id, zone_id),
            )
            inserted_goal_pose = True
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {
            **visitor_row,
            "goal_pose_id": goal_pose_id,
            "map_id": guide_map_id,
            "zone_id": zone_id,
            "purpose": "GUIDE_DESTINATION",
        }
    finally:
        cleanup_conn = get_connection()
        try:
            with cleanup_conn.cursor() as cursor:
                if inserted_goal_pose:
                    cursor.execute(
                        "DELETE FROM goal_pose WHERE goal_pose_id = %s",
                        (goal_pose_id,),
                    )
                if inserted_zone:
                    cursor.execute(
                        "DELETE FROM operation_zone WHERE map_id = %s AND zone_id = %s",
                        (guide_map_id, zone_id),
                    )
                if inserted_map_profile:
                    cursor.execute(
                        "DELETE FROM map_profile WHERE map_id = %s",
                        (guide_map_id,),
                    )
        finally:
            cleanup_conn.close()


@pytest.fixture
def fall_evidence_seed():
    robot_row = safe_fetch_one("SELECT robot_id FROM robot WHERE robot_id = 'pinky3'")
    if robot_row is None:
        robot_row = safe_fetch_one("SELECT robot_id FROM robot LIMIT 1")

    robot_id = robot_row["robot_id"] if robot_row else None
    evidence_image_id = f"it-fall-evidence-{uuid.uuid4().hex}"
    request_id = f"runtime-pat-007-{uuid.uuid4().hex}"
    result_seq = 541
    task_id = None

    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task
                (task_type, request_id, idempotency_key, requester_type, requester_id,
                 priority, task_status, phase, assigned_robot_id, latest_reason_code,
                 created_at, updated_at, started_at)
                VALUES
                ('PATROL', %s, %s, 'CAREGIVER', 'integration-test',
                 'NORMAL', 'RUNNING', 'WAIT_FALL_RESPONSE', %s, 'FALL_DETECTED',
                 NOW(3), NOW(3), NOW(3))
                """,
                (request_id, request_id, robot_id),
            )
            task_id = cursor.lastrowid
            payload = {
                "trigger_result": {
                    "result_seq": result_seq,
                    "frame_id": "front_cam_frame_541",
                    "fall_streak_ms": 1200,
                    "evidence_image_id": evidence_image_id,
                    "evidence_image_available": True,
                    "pinky_id": robot_id,
                    "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                }
            }
            cursor.execute(
                """
                INSERT INTO task_event_log
                (task_id, event_name, severity, component, robot_id, correlation_id,
                 result_code, reason_code, message, payload_json, occurred_at, created_at)
                VALUES
                (%s, 'FALL_ALERT_CREATED', 'WARN', 'ai_fall_detector', %s, NULL,
                 'FALL_DETECTED', 'FALL_DETECTED', 'integration fall alert',
                 %s, NOW(3), NOW(3))
                """,
                (task_id, robot_id, json.dumps(payload, ensure_ascii=False)),
            )
            alert_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {
            "task_id": task_id,
            "alert_id": str(alert_id),
            "evidence_image_id": evidence_image_id,
            "result_seq": result_seq,
            "robot_id": robot_id,
        }
    finally:
        if task_id is not None:
            cleanup_conn = get_connection()
            try:
                with cleanup_conn.cursor() as cursor:
                    cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
            finally:
                cleanup_conn.close()


@pytest.fixture
def active_patrol_task_seed():
    robot_row = safe_fetch_one("SELECT robot_id FROM robot WHERE robot_id = 'pinky3'")
    assert robot_row is not None, "The remote DB has no pinky3 robot row."

    patrol_area = safe_fetch_one(
        "SELECT patrol_area_id, revision FROM patrol_area WHERE is_enabled = TRUE LIMIT 1"
    )
    assert patrol_area is not None, "The remote DB has no enabled patrol_area row."

    request_id = f"runtime-pat-005-{uuid.uuid4().hex}"
    task_id = None
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task
                (task_type, request_id, idempotency_key, requester_type, requester_id,
                 priority, task_status, phase, assigned_robot_id, latest_reason_code,
                 created_at, updated_at, started_at)
                VALUES
                ('PATROL', %s, %s, 'CAREGIVER', 'integration-test',
                 'NORMAL', 'RUNNING', 'FOLLOW_PATROL_PATH', 'pinky3', NULL,
                 NOW(3), NOW(3), NOW(3))
                """,
                (request_id, request_id),
            )
            task_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO patrol_task_detail
                (task_id, patrol_area_id, patrol_area_revision, patrol_status,
                 frame_id, waypoint_count, current_waypoint_index, path_snapshot_json, notes)
                VALUES
                (%s, %s, %s, 'MOVING', 'map', 1, 0,
                 '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0}]}',
                 'runtime PAT-005 integration test')
                """,
                (task_id, patrol_area["patrol_area_id"], patrol_area["revision"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {"task_id": task_id}
    finally:
        if task_id is not None:
            cleanup_conn = get_connection()
            try:
                with cleanup_conn.cursor() as cursor:
                    cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
            finally:
                cleanup_conn.close()


@pytest.fixture
def waiting_guide_task_seed(guide_destination_seed):
    robot_row = safe_fetch_one("SELECT robot_id FROM robot WHERE robot_id = 'pinky1'")
    assert robot_row is not None, "The remote DB has no pinky1 robot row."

    visitor_row = guide_destination_seed

    request_id = f"runtime-guide-task-wait-{uuid.uuid4().hex}"
    task_id = None
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO task
                (task_type, request_id, idempotency_key, requester_type, requester_id,
                 priority, task_status, phase, assigned_robot_id, latest_reason_code, map_id,
                 created_at, updated_at, started_at)
                VALUES
                ('GUIDE', %s, %s, 'VISITOR', %s,
                 'NORMAL', 'RUNNING', 'WAIT_TARGET_TRACKING', 'pinky1', 'GUIDE_COMMAND_ACCEPTED', %s,
                 NOW(3), NOW(3), NOW(3))
                """,
                (
                    request_id,
                    request_id,
                    str(visitor_row["visitor_id"]),
                    visitor_row["map_id"],
                ),
            )
            task_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO guide_task_detail
                (task_id, visitor_id, member_id, destination_goal_pose_id,
                 guide_phase, target_track_id, notes)
                VALUES
                (%s, %s, %s, %s,
                 'WAIT_TARGET_TRACKING', NULL, 'runtime guide task status test')
                """,
                (
                    task_id,
                    visitor_row["visitor_id"],
                    visitor_row["member_id"],
                    visitor_row["goal_pose_id"],
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        yield {
            "task_id": task_id,
            "pinky_id": "pinky1",
            "target_track_id": 17,
        }
    finally:
        if task_id is not None:
            cleanup_conn = get_connection()
            try:
                with cleanup_conn.cursor() as cursor:
                    cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
            finally:
                cleanup_conn.close()
