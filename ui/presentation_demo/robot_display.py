from __future__ import annotations

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

_TEXT_REPLACEMENTS = tuple(
    sorted(
        {
            **DEVICE_DISPLAY_NAMES,
            **ROBOT_DISPLAY_NAMES,
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


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
    text = value
    for raw, display in _TEXT_REPLACEMENTS:
        text = text.replace(raw, display)
    return text


def translate_robot_display_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        return translate_robot_display_text(payload)

    if isinstance(payload, Mapping):
        return {
            key: translate_robot_display_payload(value)
            for key, value in payload.items()
        }

    if isinstance(payload, list):
        return [translate_robot_display_payload(value) for value in payload]

    if isinstance(payload, tuple):
        return tuple(translate_robot_display_payload(value) for value in payload)

    return payload


__all__ = [
    "DEVICE_DISPLAY_NAMES",
    "DISPLAY_RUNTIME_ROBOT_IDS",
    "ROBOT_DISPLAY_NAMES",
    "display_robot_name",
    "runtime_robot_id_for_display",
    "translate_robot_display_payload",
    "translate_robot_display_text",
]
