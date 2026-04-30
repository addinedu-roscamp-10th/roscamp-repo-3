from importlib import import_module

from .tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
    MESSAGE_CODE_PATROL_CREATE_TASK,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrame,
    TCPFrameError,
    build_frame,
    decode_frame_bytes,
    encode_frame,
    read_frame_from_socket,
    read_frame_from_stream,
    resolve_message_code,
)
from .rudp import (
    HEADER_SIZE as RUDP_HEADER_SIZE,
    PACKET_TYPE_FRAME_CHUNK,
    RudpFrame,
    RudpFrameAssembler,
    RudpPacket,
    RudpProtocolError,
    decode_datagram,
    encode_packet,
    split_frame,
)
from .vision_frame_gateway import (
    StreamMetricsSnapshot,
    VisionFrameGateway,
    VisionFrameGatewayConfig,
    VisionFrameGatewayProtocol,
    VisionFrameGatewayResult,
)
from .fall_inference_stream import (
    FallInferenceStreamClient,
    FallInferenceStreamConfig,
    FallInferenceStreamError,
)


_EXPORTS = {
    "ControlServiceServer": ("tcp_server", "ControlServiceServer"),
    "main": ("tcp_server", "main"),
}


def __getattr__(name):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc

    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "ControlServiceServer",
    "FallInferenceStreamClient",
    "FallInferenceStreamConfig",
    "FallInferenceStreamError",
    "MESSAGE_CODE_DELIVERY_CREATE_TASK",
    "MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY",
    "MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE",
    "MESSAGE_CODE_HEARTBEAT",
    "MESSAGE_CODE_INTERNAL_RPC",
    "MESSAGE_CODE_LOGIN",
    "MESSAGE_CODE_PATROL_CREATE_TASK",
    "MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY",
    "MESSAGE_CODE_PATROL_RESUME_TASK",
    "MESSAGE_CODE_TASK_EVENT_SUBSCRIBE",
    "PACKET_TYPE_FRAME_CHUNK",
    "RUDP_HEADER_SIZE",
    "RudpFrame",
    "RudpFrameAssembler",
    "RudpPacket",
    "RudpProtocolError",
    "StreamMetricsSnapshot",
    "TCPFrame",
    "TCPFrameError",
    "VisionFrameGateway",
    "VisionFrameGatewayConfig",
    "VisionFrameGatewayProtocol",
    "VisionFrameGatewayResult",
    "build_frame",
    "decode_datagram",
    "decode_frame_bytes",
    "encode_packet",
    "encode_frame",
    "main",
    "read_frame_from_socket",
    "read_frame_from_stream",
    "resolve_message_code",
    "split_frame",
]
