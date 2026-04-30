import json
import uuid

import pytest

from server.ropi_main_service.persistence.connection import fetch_one, get_connection


def safe_fetch_one(query: str):
    try:
        return fetch_one(query)
    except Exception:
        return None


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
