#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import socket
import struct
import time
import zlib

import cv2
import rclpy
from rclpy.node import Node

from ropi_patrol.camera import Camera


class RopiCamera(Node):
    # IF-COM-008 RUDP header:
    # magic(4), version(1), packet_type(1), reserved(2), stream_name(24),
    # session_id(4), frame_id(4), ts_us(8), chunk_idx(2), chunk_count(2),
    # frame_len(4), crc32(4)
    RUDP_MAGIC = b"RUDP"
    RUDP_VERSION = 1
    RUDP_PACKET_TYPE_FRAME_CHUNK = 1
    RUDP_RESERVED = 0
    RUDP_STREAM_NAME_SIZE = 24
    RUDP_HEADER_FORMAT = "!4sBBH24sIIQHHII"
    RUDP_HEADER_SIZE = struct.calcsize(RUDP_HEADER_FORMAT)

    def __init__(self):
        super().__init__("ropi_camera")

        self._declare_and_load_parameters()

        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.udp_send_buffer_size)

        self.camera = Camera()
        self.camera.start(width=self.camera_width, height=self.camera_height)

        # session_id는 노드가 살아있는 동안 유지되고 frame_id는 JPEG frame마다 증가한다.
        self.frame_id = 0

        self.timer = self.create_timer(1.0 / self.send_fps, self.send_frame_udp)

        self.get_logger().info(f"Ropi camera started: target={self.server_ip}:{self.udp_port}")
        self.get_logger().info(
            f"RUDP stream: name={self.stream_name}, session_id={self.session_id}, "
            f"packet_size={self.udp_packet_size}, payload_size={self.udp_payload_size}"
        )

    def _declare_and_load_parameters(self):
        self.declare_parameter("server_ip", "")
        self.declare_parameter("udp_port", 0)
        self.declare_parameter("stream_name", "pinky03_cam")
        self.declare_parameter("udp_packet_size", 1200)
        self.declare_parameter("udp_send_buffer_size", 4 * 1024 * 1024)
        self.declare_parameter("session_id", 0)
        self.declare_parameter("send_fps", 10.0)
        self.declare_parameter("camera_width", 320)
        self.declare_parameter("camera_height", 240)
        self.declare_parameter("jpeg_quality", 70)

        self.server_ip = str(self.get_parameter("server_ip").value).strip()
        self.udp_port = int(self.get_parameter("udp_port").value)
        self.stream_name = str(self.get_parameter("stream_name").value).strip()
        self.udp_packet_size = int(self.get_parameter("udp_packet_size").value)
        self.udp_send_buffer_size = int(self.get_parameter("udp_send_buffer_size").value)
        configured_session_id = int(self.get_parameter("session_id").value)
        self.send_fps = float(self.get_parameter("send_fps").value)
        self.camera_width = int(self.get_parameter("camera_width").value)
        self.camera_height = int(self.get_parameter("camera_height").value)
        self.jpeg_quality = int(self.get_parameter("jpeg_quality").value)

        if not self.server_ip:
            raise ValueError("server_ip parameter is required.")
        if self.udp_port <= 0:
            raise ValueError("udp_port must be greater than 0.")
        if not self.stream_name:
            raise ValueError("stream_name parameter is required.")
        if len(self.stream_name.encode("utf-8")) > self.RUDP_STREAM_NAME_SIZE:
            raise ValueError("stream_name must be 24 bytes or less in UTF-8.")
        if self.udp_packet_size <= self.RUDP_HEADER_SIZE:
            raise ValueError(
                f"udp_packet_size must be greater than RUDP header size {self.RUDP_HEADER_SIZE}."
            )
        if self.udp_send_buffer_size <= 0:
            raise ValueError("udp_send_buffer_size must be greater than 0.")
        if self.send_fps <= 0:
            raise ValueError("send_fps must be greater than 0.")

        self.stream_name_bytes = self._encode_stream_name(self.stream_name)
        self.udp_payload_size = self.udp_packet_size - self.RUDP_HEADER_SIZE
        self.session_id = configured_session_id & 0xFFFFFFFF
        if self.session_id == 0:
            # session_id=0은 "자동 생성" 의미로 사용하고, 실제 wire에는
            # 노드 시작 시점 기반의 32-bit session id를 넣는다.
            self.session_id = int(time.time() * 1_000_000) & 0xFFFFFFFF

    def _encode_stream_name(self, stream_name):
        encoded = stream_name.encode("utf-8")
        if len(encoded) > self.RUDP_STREAM_NAME_SIZE:
            raise ValueError("stream_name must be 24 bytes or less in UTF-8.")
        return encoded.ljust(self.RUDP_STREAM_NAME_SIZE, b"\x00")

    def _build_rudp_header(
        self,
        frame_id,
        ts_us,
        chunk_idx,
        chunk_count,
        frame_len,
        frame_crc32,
    ):
        """
        IF-COM-008 RUDP header를 network byte order로 직렬화한다.

        receiver는 이 header를 기준으로
        (stream_name, session_id, frame_id)별 frame assembly를 수행한다.
        """
        return struct.pack(
            self.RUDP_HEADER_FORMAT,
            self.RUDP_MAGIC,
            self.RUDP_VERSION,
            self.RUDP_PACKET_TYPE_FRAME_CHUNK,
            self.RUDP_RESERVED,
            self.stream_name_bytes,
            self.session_id,
            frame_id,
            ts_us,
            chunk_idx,
            chunk_count,
            frame_len,
            frame_crc32,
        )

    def send_frame_udp(self):
        """
        카메라 프레임을 JPEG로 압축한 뒤 IF-COM-008 RUDP chunk로 분할 전송한다.
        """
        try:
            frame = self.camera.get_frame()
            if frame is None:
                return

            frame = cv2.resize(frame, (self.camera_width, self.camera_height))
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
            )
            if not ok:
                self.get_logger().warn("Failed to encode frame.")
                return

            jpeg_bytes = encoded.tobytes()
            frame_len = len(jpeg_bytes)
            frame_crc32 = zlib.crc32(jpeg_bytes) & 0xFFFFFFFF
            ts_us = time.time_ns() // 1_000
            frame_id = self.frame_id & 0xFFFFFFFF
            self.frame_id = (self.frame_id + 1) & 0xFFFFFFFF
            chunk_count = max(1, math.ceil(frame_len / self.udp_payload_size))

            for chunk_idx in range(chunk_count):
                offset = chunk_idx * self.udp_payload_size
                payload = jpeg_bytes[offset:offset + self.udp_payload_size]
                packet = self._build_rudp_header(
                    frame_id,
                    ts_us,
                    chunk_idx,
                    chunk_count,
                    frame_len,
                    frame_crc32,
                ) + payload
                self.udp_sock.sendto(packet, (self.server_ip, self.udp_port))

        except Exception as e:
            self.get_logger().error(f"UDP frame send error: {e}")

    def close(self):
        try:
            self.timer.cancel()
        except Exception:
            pass

        try:
            self.udp_sock.close()
        except Exception:
            pass

        try:
            self.camera.close()
        except Exception:
            pass

        self.get_logger().info("Ropi camera closed.")


def main(args=None):
    rclpy.init(args=args)
    node = RopiCamera()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
