import json
import socket
import struct
from dataclasses import dataclass


MAGIC = 0x5250
VERSION = 1
HEADER_FORMAT = "!HBBHHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

FLAG_RESPONSE = 1 << 0
FLAG_ERROR = 1 << 1
FLAG_PUSH = 1 << 2

MESSAGE_CODE_HEARTBEAT = 0x1001
MESSAGE_CODE_LOGIN = 0x1002
MESSAGE_CODE_TASK_EVENT_SUBSCRIBE = 0x1003
MESSAGE_CODE_INTERNAL_RPC = 0x10F0
MESSAGE_CODE_DELIVERY_CREATE_TASK = 0x2001
MESSAGE_CODE_PATROL_CREATE_TASK = 0x3001
MESSAGE_CODE_PATROL_RESUME_TASK = 0x3002
MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE = 0x5001

LEGACY_MESSAGE_CODES = {
    "HEARTBEAT": MESSAGE_CODE_HEARTBEAT,
    "LOGIN": MESSAGE_CODE_LOGIN,
    "TASK_EVENT_SUBSCRIBE": MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    "RPC": MESSAGE_CODE_INTERNAL_RPC,
    "PATROL_CREATE_TASK": MESSAGE_CODE_PATROL_CREATE_TASK,
    "PATROL_RESUME_TASK": MESSAGE_CODE_PATROL_RESUME_TASK,
    "FALL_INFERENCE_RESULT_SUBSCRIBE": MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
}


class TCPFrameError(RuntimeError):
    """Raised when custom TCP frame encoding or decoding fails."""


@dataclass(init=False)
class TCPFrame:
    message_code: int
    sequence_no: int
    payload: object
    flags: int = 0
    reserved: int = 0
    version: int = VERSION
    magic: int = MAGIC

    def __init__(
        self,
        message_code: int,
        sequence_no: int,
        payload: object,
        flags: int = 0,
        reserved: int = 0,
        version: int = VERSION,
        magic: int = MAGIC,
        *,
        is_response: bool = False,
        is_error: bool = False,
        is_push: bool = False,
    ):
        if is_response:
            flags |= FLAG_RESPONSE
        if is_error:
            flags |= FLAG_ERROR
        if is_push:
            flags |= FLAG_PUSH

        self.message_code = message_code
        self.sequence_no = sequence_no
        self.payload = payload
        self.flags = flags
        self.reserved = reserved
        self.version = version
        self.magic = magic

    @property
    def is_response(self) -> bool:
        return bool(self.flags & FLAG_RESPONSE)

    @property
    def is_error(self) -> bool:
        return bool(self.flags & FLAG_ERROR)

    @property
    def is_push(self) -> bool:
        return bool(self.flags & FLAG_PUSH)


def resolve_message_code(message_code_or_alias: int | str) -> int:
    if isinstance(message_code_or_alias, int):
        return message_code_or_alias

    try:
        return LEGACY_MESSAGE_CODES[message_code_or_alias]
    except KeyError as exc:
        raise TCPFrameError(f"지원하지 않는 message_code alias입니다: {message_code_or_alias}") from exc


def build_frame(
    message_code: int | str,
    sequence_no: int,
    payload: object = None,
    *,
    is_response: bool = False,
    is_error: bool = False,
    is_push: bool = False,
) -> TCPFrame:
    flags = 0
    if is_response:
        flags |= FLAG_RESPONSE
    if is_error:
        flags |= FLAG_ERROR
    if is_push:
        flags |= FLAG_PUSH

    return TCPFrame(
        message_code=resolve_message_code(message_code),
        sequence_no=sequence_no,
        payload=payload if payload is not None else {},
        flags=flags,
    )


def encode_frame(frame: TCPFrame) -> bytes:
    body = json.dumps(frame.payload, ensure_ascii=False).encode("utf-8")
    header = struct.pack(
        HEADER_FORMAT,
        frame.magic,
        frame.version,
        frame.flags,
        frame.message_code,
        frame.reserved,
        frame.sequence_no,
        len(body),
    )
    return header + body


def decode_frame_bytes(data: bytes) -> TCPFrame:
    if len(data) < HEADER_SIZE:
        raise TCPFrameError("프레임 헤더 길이가 부족합니다.")

    header = data[:HEADER_SIZE]
    body = data[HEADER_SIZE:]
    magic, version, flags, message_code, reserved, sequence_no, body_length = struct.unpack(
        HEADER_FORMAT,
        header,
    )

    if magic != MAGIC:
        raise TCPFrameError(f"프레임 magic 값이 올바르지 않습니다: {magic:#06x}")

    if version != VERSION:
        raise TCPFrameError(f"지원하지 않는 프레임 버전입니다: {version}")

    if len(body) != body_length:
        raise TCPFrameError("프레임 body 길이가 헤더와 일치하지 않습니다.")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError as exc:
        raise TCPFrameError("프레임 body JSON이 올바르지 않습니다.") from exc

    return TCPFrame(
        magic=magic,
        version=version,
        flags=flags,
        message_code=message_code,
        reserved=reserved,
        sequence_no=sequence_no,
        payload=payload,
    )


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    received = 0

    while received < size:
        chunk = sock.recv(size - received)
        if not chunk:
            raise TCPFrameError("소켓에서 필요한 바이트 수만큼 데이터를 읽지 못했습니다.")
        chunks.append(chunk)
        received += len(chunk)

    return b"".join(chunks)


def read_frame_from_socket(sock: socket.socket) -> TCPFrame:
    header = recv_exact(sock, HEADER_SIZE)
    _, _, _, _, _, _, body_length = struct.unpack(HEADER_FORMAT, header)
    body = recv_exact(sock, body_length) if body_length else b""
    return decode_frame_bytes(header + body)


async def read_frame_from_stream(reader) -> TCPFrame:
    try:
        header = await reader.readexactly(HEADER_SIZE)
    except Exception as exc:
        raise TCPFrameError("스트림에서 프레임 헤더를 읽지 못했습니다.") from exc

    _, _, _, _, _, _, body_length = struct.unpack(HEADER_FORMAT, header)
    body = await reader.readexactly(body_length) if body_length else b""
    return decode_frame_bytes(header + body)
