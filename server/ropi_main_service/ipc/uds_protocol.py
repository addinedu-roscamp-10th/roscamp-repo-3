import json


class UDSProtocolError(RuntimeError):
    """Raised when internal UDS IPC payloads are malformed."""


def build_request_message(command: str, payload: dict | None = None) -> dict:
    return {
        "command": command,
        "payload": payload or {},
    }


def build_response_message(
    *,
    ok: bool,
    payload: dict | None = None,
    error_code: str | None = None,
    error: str | None = None,
) -> dict:
    response = {"ok": ok}

    if ok:
        response["payload"] = payload or {}
        return response

    response["error_code"] = error_code or "IPC_ERROR"
    response["error"] = error or "UDS IPC request failed."
    return response


def encode_message(message: dict) -> bytes:
    return json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"


def decode_message_bytes(data: bytes) -> dict:
    normalized = data.rstrip(b"\n")

    if not normalized:
        raise UDSProtocolError("UDS IPC message is empty.")

    try:
        message = json.loads(normalized.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise UDSProtocolError("UDS IPC message is not valid JSON.") from exc

    if not isinstance(message, dict):
        raise UDSProtocolError("UDS IPC message root must be an object.")

    return message


def read_message_from_socket(sock) -> dict:
    chunks = []

    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise UDSProtocolError("UDS IPC socket closed before a full message was received.")
        chunks.append(chunk)
        if b"\n" in chunk:
            break

    joined = b"".join(chunks)
    message_bytes, _, _ = joined.partition(b"\n")
    return decode_message_bytes(message_bytes)


async def read_message_from_stream(reader) -> dict:
    line = await reader.readline()
    if not line:
        raise UDSProtocolError("UDS IPC stream closed before a full message was received.")
    return decode_message_bytes(line)
