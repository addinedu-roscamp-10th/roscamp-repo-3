from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


ROBOT_DISPLAY_NAMES = {
    "pinky1": "ROPI 1",
    "pinky2": "ROPI 2",
    "pinky3": "ROPI 3",
    "핑키1": "ROPI 1",
    "핑키2": "ROPI 2",
    "핑키3": "ROPI 3",
    "핑키 1": "ROPI 1",
    "핑키 2": "ROPI 2",
    "핑키 3": "ROPI 3",
}

DISPLAY_RUNTIME_ROBOT_IDS = {
    "ROPI 1": "pinky1",
    "ROPI 2": "pinky2",
    "ROPI 3": "pinky3",
    "ROPI1": "pinky1",
    "ROPI2": "pinky2",
    "ROPI3": "pinky3",
}

DEVICE_DISPLAY_NAMES = {
    "arm1": "운반 장치",
    "arm2": "운반 장치",
    "jetcobot1": "운반 장치",
    "jetcobot2": "운반 장치",
}

DISPLAY_VALUE_LABELS = {
    "Control Service": "관제 서버",
    "DELIVERY": "운반",
    "PATROL": "순찰",
    "GUIDE": "안내",
    "FOLLOW": "추종",
    "RUNNING": "진행 중",
    "WAITING": "대기",
    "WAITING_DISPATCH": "배정 대기",
    "READY": "준비",
    "ASSIGNED": "배정 완료",
    "COMPLETED": "완료",
    "FAILED": "실패",
    "CANCEL_REQUESTED": "취소 요청",
    "CANCELLING": "취소 처리 중",
    "CANCELLED": "취소 완료",
    "PREEMPTING": "중단 처리 중",
    "ACCEPTED": "접수",
    "OK": "정상",
    "REJECTED": "거절",
    "CLIENT_ERROR": "클라이언트 오류",
    "NOT_ALLOWED": "허용 안 됨",
    "NOT_FOUND": "찾을 수 없음",
    "INFO": "정보",
    "WARNING": "주의",
    "ERROR": "오류",
    "CRITICAL": "긴급",
    "MOVE_TO_PICKUP": "픽업지 이동",
    "DELIVERY_PICKUP": "물품 적재",
    "DELIVERY_DESTINATION": "목적지 이동",
    "HANDOVER_WAITING": "전달 대기",
    "RETURN_TO_DOCK": "복귀 중",
    "WAIT_TARGET_TRACKING": "안내 대상 확인",
    "READY_TO_START_GUIDANCE": "안내 시작 준비",
    "GUIDANCE_RUNNING": "안내 주행 중",
    "GUIDANCE_FINISHED": "안내 완료",
    "PATROL_RUNNING": "순찰 중",
    "WAIT_FALL_RESPONSE": "낙상 의심 확인",
    "TASK_COMPLETED": "작업 완료",
    "TASK_UPDATED": "작업 갱신",
    "ACTION_FEEDBACK_UPDATED": "주행 피드백 갱신",
    "ALERT_CREATED": "알림 생성",
    "FALL_ALERT_CREATED": "낙상 알림 생성",
    "PINKY_UPDATED": "로봇 상태 갱신",
    "ARM_UPDATED": "운반 장치 상태 갱신",
    "TASK_FAILED": "작업 실패",
    "TASK_CANCELLED": "작업 취소",
    "PATROL_RUNTIME_NOT_READY": "순찰 실행 준비 안 됨",
    "PATROL_PATH_SERVICE_UNAVAILABLE": "순찰 서비스 연결 안 됨",
    "DELIVERY_RUNTIME_NOT_READY": "운반 실행 준비 안 됨",
    "GUIDE_RUNTIME_NOT_READY": "안내 실행 준비 안 됨",
    "ROS_RUNTIME_NOT_READY": "로봇 런타임 준비 안 됨",
    "DESTINATION_CONFIG_MISSING": "목적지 설정 없음",
    "CLIENT_RESPONSE_INVALID": "응답 형식 오류",
    "WORKFLOW_RESULT_RECORDED": "업무 흐름 결과 기록됨",
    "WAITING_FMS_RESERVATION": "FMS 예약 대기",
    "TASK_STATE_HISTORY": "작업 상태 이력",
}

DISPLAY_KEY_LABELS = {
    "alert_pose": "알림 위치",
    "arm_id": "운반 장치",
    "assigned_robot_id": "담당 ROPI",
    "current_pose": "현재 위치",
    "event_id": "이벤트 번호",
    "event_type": "이벤트",
    "feedback_summary": "피드백",
    "frame_id": "좌표계",
    "history_name": "이력 이름",
    "latest_reason_code": "최근 사유",
    "message": "메시지",
    "phase": "단계",
    "reason_code": "사유",
    "result_code": "결과",
    "result_message": "결과 메시지",
    "robot_id": "로봇",
    "severity": "심각도",
    "source_component": "출처",
    "task_id": "작업 번호",
    "task_history": "작업 이력",
    "task_status": "상태",
    "task_type": "작업 유형",
    "waiting_state": "대기 상태",
    "workflow_event": "업무 흐름 이벤트",
}

DISPLAY_TOKEN_LABELS = {
    "ACTION": "동작",
    "ALERT": "알림",
    "ARM": "운반 장치",
    "ASSIGNED": "배정됨",
    "CANCEL": "취소",
    "CANCELLED": "취소됨",
    "CANCELLING": "취소 중",
    "CLIENT": "클라이언트",
    "COMMAND": "명령",
    "COMPLETED": "완료됨",
    "CONFIG": "설정",
    "CREATED": "생성됨",
    "DESTINATION": "목적지",
    "DETECTED": "감지됨",
    "DISPATCH": "배정",
    "DOCK": "충전 위치",
    "ERROR": "오류",
    "EVIDENCE": "증거",
    "FAILED": "실패",
    "FALL": "낙상",
    "FEEDBACK": "피드백",
    "FINISHED": "완료됨",
    "FMS": "FMS",
    "FOUND": "찾음",
    "GUIDANCE": "안내",
    "GUIDE": "안내",
    "HANDOVER": "인계",
    "HISTORY": "이력",
    "ID": "번호",
    "IMAGE": "이미지",
    "INVALID": "유효하지 않음",
    "LATEST": "최근",
    "LOCATION": "위치",
    "MESSAGE": "메시지",
    "MISSING": "없음",
    "MOVE": "이동",
    "NOT": "안 됨",
    "PATH": "경로",
    "PATROL": "순찰",
    "PHASE": "단계",
    "PICKUP": "픽업",
    "PINKY": "로봇",
    "POSE": "위치",
    "READY": "준비",
    "RECORDED": "기록됨",
    "REJECTED": "거절됨",
    "RESERVATION": "예약",
    "RESPONSE": "응답",
    "RESULT": "결과",
    "RETURN": "복귀",
    "ROBOT": "로봇",
    "ROS": "로봇 런타임",
    "RUNTIME": "실행",
    "RUNNING": "진행 중",
    "SERVICE": "서비스",
    "START": "시작",
    "STATE": "상태",
    "STATUS": "상태",
    "STREAM": "스트림",
    "SUMMARY": "요약",
    "TARGET": "대상",
    "TASK": "작업",
    "TO": "이동",
    "TRACKING": "추적",
    "TRANSPORT": "전송",
    "UNAVAILABLE": "연결 안 됨",
    "UPDATED": "갱신됨",
    "WAIT": "대기",
    "WAITING": "대기",
    "WAYPOINT": "경유지",
    "WORKFLOW": "업무 흐름",
    "ZONE": "구역",
}

_UPPER_SNAKE_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

_TEXT_REPLACEMENTS = tuple(
    sorted(
        {
            **DEVICE_DISPLAY_NAMES,
            **DISPLAY_KEY_LABELS,
            **DISPLAY_VALUE_LABELS,
            **ROBOT_DISPLAY_NAMES,
            "상세\npayload": "상세\n내용",
            "event type": "이벤트",
            "frame_id": "좌표계",
            "waypoint": "경유지",
            "이벤트 ID": "이벤트 번호",
            "로봇 ID": "로봇",
            "작업 ID": "작업 번호",
            "추적 ID": "추적 번호",
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def _translate_payload_key(key: Any) -> str:
    text = str(key)
    if text in DISPLAY_KEY_LABELS:
        return DISPLAY_KEY_LABELS[text]
    if "_" not in text:
        return text
    labels = [
        DISPLAY_TOKEN_LABELS.get(part.upper())
        for part in text.split("_")
        if part
    ]
    if labels and all(labels):
        return " ".join(labels)
    return text


def _translate_snake_code(code: str) -> str:
    if code in DISPLAY_VALUE_LABELS:
        return DISPLAY_VALUE_LABELS[code]
    labels = [DISPLAY_TOKEN_LABELS.get(part) for part in code.split("_")]
    if labels and all(labels):
        return " ".join(labels)
    return code


def display_robot_name(value: Any) -> str:
    text = str(value or "").strip()
    return ROBOT_DISPLAY_NAMES.get(text, DEVICE_DISPLAY_NAMES.get(text, text))


def runtime_robot_id_for_display(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return DISPLAY_RUNTIME_ROBOT_IDS.get(text, text)


def translate_robot_display_text(value: str) -> str:
    text = DISPLAY_VALUE_LABELS.get(value, value)
    text = _UPPER_SNAKE_CODE_RE.sub(
        lambda match: _translate_snake_code(match.group(0)),
        text,
    )
    for raw, display in _TEXT_REPLACEMENTS:
        text = text.replace(raw, display)
    return text


def translate_robot_display_payload(payload: Any, *, translate_keys: bool = False) -> Any:
    if isinstance(payload, str):
        return translate_robot_display_text(payload)

    if isinstance(payload, Mapping):
        return {
            (
                _translate_payload_key(key) if translate_keys else key
            ): translate_robot_display_payload(
                    value,
                    translate_keys=translate_keys or key == "payload",
                )
            for key, value in payload.items()
        }

    if isinstance(payload, list):
        return [
            translate_robot_display_payload(value, translate_keys=translate_keys)
            for value in payload
        ]

    if isinstance(payload, tuple):
        return tuple(
            translate_robot_display_payload(value, translate_keys=translate_keys)
            for value in payload
        )

    return payload


def translate_robot_identity_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        text = payload
        for raw, display in {
            **DEVICE_DISPLAY_NAMES,
            **ROBOT_DISPLAY_NAMES,
        }.items():
            text = text.replace(raw, display)
        return text

    if isinstance(payload, Mapping):
        return {
            key: translate_robot_identity_payload(value)
            for key, value in payload.items()
        }

    if isinstance(payload, list):
        return [translate_robot_identity_payload(value) for value in payload]

    if isinstance(payload, tuple):
        return tuple(translate_robot_identity_payload(value) for value in payload)

    return payload


__all__ = [
    "DEVICE_DISPLAY_NAMES",
    "DISPLAY_KEY_LABELS",
    "DISPLAY_RUNTIME_ROBOT_IDS",
    "DISPLAY_VALUE_LABELS",
    "ROBOT_DISPLAY_NAMES",
    "display_robot_name",
    "runtime_robot_id_for_display",
    "translate_robot_identity_payload",
    "translate_robot_display_payload",
    "translate_robot_display_text",
]
