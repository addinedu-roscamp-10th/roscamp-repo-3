from server.ropi_main_service.tcp_protocol import (
    MAGIC,
    VERSION,
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    TCPFrame,
    decode_frame_bytes,
    encode_frame,
)


def test_encode_and_decode_preserve_header_fields_and_payload():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=123,
        payload={"request_id": "req_001", "item_id": "supply_001"},
    )

    encoded = encode_frame(frame)
    decoded = decode_frame_bytes(encoded)

    assert decoded.magic == MAGIC
    assert decoded.version == VERSION
    assert decoded.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK
    assert decoded.sequence_no == 123
    assert decoded.payload == {"request_id": "req_001", "item_id": "supply_001"}
    assert decoded.is_response is False
    assert decoded.is_error is False
