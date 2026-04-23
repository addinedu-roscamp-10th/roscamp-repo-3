import unittest

from server.ropi_main_service.tcp_protocol import (
    MAGIC,
    VERSION,
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    TCPFrame,
    decode_frame_bytes,
    encode_frame,
)


class TCPFrameProtocolTest(unittest.TestCase):
    def test_encode_and_decode_preserve_header_fields_and_payload(self):
        frame = TCPFrame(
            message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
            sequence_no=123,
            payload={"request_id": "req_001", "item_id": "supply_001"},
        )

        encoded = encode_frame(frame)
        decoded = decode_frame_bytes(encoded)

        self.assertEqual(decoded.magic, MAGIC)
        self.assertEqual(decoded.version, VERSION)
        self.assertEqual(decoded.message_code, MESSAGE_CODE_DELIVERY_CREATE_TASK)
        self.assertEqual(decoded.sequence_no, 123)
        self.assertEqual(
            decoded.payload,
            {"request_id": "req_001", "item_id": "supply_001"},
        )
        self.assertFalse(decoded.is_response)
        self.assertFalse(decoded.is_error)


if __name__ == "__main__":
    unittest.main()
