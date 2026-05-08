#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import socket
import struct
import sys
import threading
import time
import zlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np
from ultralytics import YOLO

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from server.ropi_main_service.transport.tcp_protocol import (
    TCPFrameError,
    build_frame,
    encode_frame,
    read_frame_from_socket,
)


UDP_HOST = "0.0.0.0"
UDP_PORT = 5005
UDP_RECV_BUFFER_SIZE = 8 * 1024 * 1024
ASSEMBLY_TIMEOUT_SEC = 0.7

TCP_HOST = "0.0.0.0"
TCP_PORT = 6000
TCP_SUBSCRIBE_TIMEOUT_SEC = 5.0
MESSAGE_CODE_FALL_RESULT_SUBSCRIBE = 0x5001

MODEL_PATH = "/home/addinedu/Documents/fallen_detection/models/yolo26x_gen_v1_weights/best.pt"

FALL_CLASS_ID = 1

# 시각화 여부
SHOW_WINDOW = True

# subscribe 재접속 직후 last_seq 이후 결과를 replay하기 위한 작은 메모리 버퍼.
RESULT_BUFFER_SIZE = 256

# MVP에서는 stream_name이 Pinky 한 대의 단일 순찰 카메라를 대표한다고 본다.
# 팀 naming이 확정되면 이 매핑을 설정 파일/env로 분리하는 편이 좋다.
STREAM_TO_PINKY_ID = {
    "pinky03_cam": "pinky3",
    "pinky3_cam": "pinky3",
}
FALL_ALERT_THRESHOLD_MS = 1000


@dataclass
class FrameAssembly:
    """
    하나의 (stream_name, session_id, frame_id)에 대한 chunk 조립 상태.
    """
    session_id: int
    frame_id: int
    ts_us: int
    chunk_count: int
    frame_len: int
    crc32: int
    created_at: float
    chunks: dict[int, bytes] = field(default_factory=dict)


@dataclass
class StreamState:
    """
    stream_name별 latest-wins 상태.
    """
    session_id: int | None = None
    latest_frame_id: int = -1
    assemblies: dict[int, FrameAssembly] = field(default_factory=dict)


@dataclass
class FallResultSubscriber:
    """
    IF-PAT-005 구독 세션 상태.
    """
    sock: socket.socket
    consumer_id: str
    pinky_id: str | None
    next_push_sequence_no: int = 1


class FallenDetectionServer:
    RUDP_MAGIC = b"RUDP"
    RUDP_VERSION = 1
    RUDP_PACKET_TYPE_FRAME_CHUNK = 1
    RUDP_STREAM_NAME_SIZE = 24
    RUDP_HEADER_FORMAT = "!4sBBH24sIIQHHII"
    RUDP_HEADER_SIZE = struct.calcsize(RUDP_HEADER_FORMAT)

    def __init__(self):
        self.model = YOLO(MODEL_PATH)

        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RECV_BUFFER_SIZE)
        self.udp_sock.bind((UDP_HOST, UDP_PORT))

        self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_sock.bind((TCP_HOST, TCP_PORT))
        self.tcp_server_sock.listen(1)

        self.subscriber = None
        self.tcp_lock = threading.Lock()

        self.stop_event = threading.Event()

        self.result_seq = 0
        self.result_buffer = deque(maxlen=RESULT_BUFFER_SIZE)
        self.fall_streak_start_monotonic = {}
        self.stream_states = {}

        self.accept_thread = threading.Thread(target=self.accept_tcp_client_loop, daemon=True)
        self.accept_thread.start()

        print(f"[SERVER] UDP image receive: {UDP_HOST}:{UDP_PORT}")
        print(f"[SERVER] TCP fall result subscribe server: {TCP_HOST}:{TCP_PORT}")
        print(f"[SERVER] Model loaded: {MODEL_PATH}")

    @staticmethod
    def _decode_stream_name(raw_stream_name):
        return raw_stream_name.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

    def parse_rudp_packet(self, data):
        """
        IF-COM-008 RUDP datagram header를 파싱한다.
        """
        if len(data) < self.RUDP_HEADER_SIZE:
            return None

        (
            magic,
            version,
            packet_type,
            _reserved,
            raw_stream_name,
            session_id,
            frame_id,
            ts_us,
            chunk_idx,
            chunk_count,
            frame_len,
            frame_crc32,
        ) = struct.unpack(self.RUDP_HEADER_FORMAT, data[:self.RUDP_HEADER_SIZE])

        if (
            magic != self.RUDP_MAGIC
            or version != self.RUDP_VERSION
            or packet_type != self.RUDP_PACKET_TYPE_FRAME_CHUNK
            or chunk_count == 0
            or chunk_idx >= chunk_count
        ):
            return None

        payload = data[self.RUDP_HEADER_SIZE:]
        stream_name = self._decode_stream_name(raw_stream_name)

        return {
            "stream_name": stream_name,
            "session_id": session_id,
            "frame_id": frame_id,
            "ts_us": ts_us,
            "chunk_idx": chunk_idx,
            "chunk_count": chunk_count,
            "frame_len": frame_len,
            "frame_crc32": frame_crc32,
            "payload": payload,
        }

    def _drop_expired_assemblies(self, now):
        for stream_name, state in list(self.stream_states.items()):
            expired_frame_ids = [
                frame_id
                for frame_id, assembly in state.assemblies.items()
                if now - assembly.created_at > ASSEMBLY_TIMEOUT_SEC
            ]

            for frame_id in expired_frame_ids:
                del state.assemblies[frame_id]

            if state.session_id is None and not state.assemblies and state.latest_frame_id < 0:
                del self.stream_states[stream_name]

    def _assemble_frame(self, packet):
        """
        chunk packet을 latest-wins 규칙으로 조립한다.
        """
        stream_name = packet["stream_name"]
        session_id = packet["session_id"]
        frame_id = packet["frame_id"]
        now = time.time()

        self._drop_expired_assemblies(now)

        state = self.stream_states.setdefault(stream_name, StreamState())

        # 세션이 바뀌면 이전 incomplete frame들을 모두 버리고 새 세션으로 전환한다.
        if state.session_id is None or state.session_id != session_id:
            state.session_id = session_id
            state.latest_frame_id = -1
            state.assemblies.clear()

        # latest-wins stream이므로 이미 처리 완료된 frame 이하의 chunk는 버린다.
        if frame_id <= state.latest_frame_id:
            return None, stream_name

        assembly = state.assemblies.get(frame_id)
        if assembly is None:
            assembly = FrameAssembly(
                session_id=session_id,
                frame_id=frame_id,
                ts_us=packet["ts_us"],
                chunk_count=packet["chunk_count"],
                frame_len=packet["frame_len"],
                crc32=packet["frame_crc32"],
                created_at=now,
            )
            state.assemblies[frame_id] = assembly

        # 중복 chunk는 무시한다.
        if packet["chunk_idx"] in assembly.chunks:
            return None, stream_name

        # 동일 frame_id 내에서 메타데이터가 달라지면 잘못된 조립이므로 폐기한다.
        if (
            assembly.chunk_count != packet["chunk_count"]
            or assembly.frame_len != packet["frame_len"]
            or assembly.crc32 != packet["frame_crc32"]
        ):
            del state.assemblies[frame_id]
            return None, stream_name

        assembly.chunks[packet["chunk_idx"]] = packet["payload"]

        if len(assembly.chunks) != assembly.chunk_count:
            return None, stream_name

        jpeg_bytes = b"".join(assembly.chunks[idx] for idx in range(assembly.chunk_count))

        if len(jpeg_bytes) != assembly.frame_len:
            del state.assemblies[frame_id]
            return None, stream_name

        if (zlib.crc32(jpeg_bytes) & 0xFFFFFFFF) != assembly.crc32:
            del state.assemblies[frame_id]
            return None, stream_name

        state.latest_frame_id = frame_id
        del state.assemblies[frame_id]

        # 최신 프레임이 완성되었으면 그보다 오래된 incomplete frame은 더 볼 필요가 없다.
        stale_frame_ids = [
            pending_frame_id
            for pending_frame_id in state.assemblies
            if pending_frame_id <= state.latest_frame_id
        ]
        for pending_frame_id in stale_frame_ids:
            del state.assemblies[pending_frame_id]

        frame_meta = {
            "stream_name": stream_name,
            "session_id": session_id,
            "frame_id": frame_id,
            "ts_us": assembly.ts_us,
        }

        return jpeg_bytes, frame_meta

    def accept_tcp_client_loop(self):
        """
        Control Service의 IF-PAT-005 subscribe 연결을 기다린다.

        Control Service는 message_code=0x5001 request를 한 번 보내고,
        이후 AI Service는 같은 persistent session으로 result push를 보낸다.
        """
        while not self.stop_event.is_set():
            try:
                print("[TCP] Waiting for Control Service subscriber...")
                client_sock, addr = self.tcp_server_sock.accept()
                client_sock.settimeout(TCP_SUBSCRIBE_TIMEOUT_SEC)

                print(f"[TCP] Control Service connected: {addr}")
                self.handle_subscribe_session(client_sock)

            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[TCP] Accept error: {e}")
                    time.sleep(1.0)

    def handle_subscribe_session(self, client_sock):
        """
        subscribe request를 검증하고 ack/replay를 처리한다.
        """
        try:
            request_frame = read_frame_from_socket(client_sock)
        except TCPFrameError as e:
            print(f"[TCP] Invalid subscribe frame: {e}")
            try:
                client_sock.close()
            except Exception:
                pass
            return

        if request_frame.message_code != MESSAGE_CODE_FALL_RESULT_SUBSCRIBE:
            self.send_subscribe_ack(
                client_sock,
                request_frame.sequence_no,
                "INVALID_REQUEST",
                f"unsupported message_code: 0x{request_frame.message_code:04x}",
            )
            client_sock.close()
            return

        payload = request_frame.payload or {}
        consumer_id = str(payload.get("consumer_id", "")).strip()
        pinky_id = payload.get("pinky_id")
        pinky_id = str(pinky_id).strip() if pinky_id is not None else None

        try:
            last_seq = int(payload.get("last_seq"))
        except (TypeError, ValueError):
            last_seq = -1

        if not consumer_id or last_seq < 0:
            self.send_subscribe_ack(
                client_sock,
                request_frame.sequence_no,
                "INVALID_REQUEST",
                "consumer_id and last_seq are required.",
            )
            client_sock.close()
            return

        self.send_subscribe_ack(
            client_sock,
            request_frame.sequence_no,
            "ACCEPTED",
            None,
            consumer_id,
            pinky_id,
        )
        print(
            f"[TCP] Subscriber accepted: consumer_id={consumer_id} "
            f"pinky_id={pinky_id} last_seq={last_seq}"
        )

        client_sock.settimeout(None)
        subscriber = FallResultSubscriber(
            sock=client_sock,
            consumer_id=consumer_id,
            pinky_id=pinky_id,
        )

        self.replace_subscriber(subscriber)

        self.replay_buffered_results(subscriber, last_seq)

    def send_subscribe_ack(
        self,
        sock,
        sequence_no,
        result_code,
        result_message=None,
        consumer_id=None,
        pinky_id=None,
    ):
        payload = {
            "result_code": result_code,
            "result_message": result_message,
            "accepted_consumer_id": consumer_id,
            "subscribed_pinky_id": pinky_id,
        }
        frame = build_frame(
            MESSAGE_CODE_FALL_RESULT_SUBSCRIBE,
            sequence_no,
            payload,
            is_response=True,
        )

        try:
            sock.sendall(encode_frame(frame))
        except Exception as e:
            print(f"[TCP] Subscribe ack send error: {e}")

    def replace_subscriber(self, subscriber):
        with self.tcp_lock:
            if self.subscriber is not None:
                self.close_socket(self.subscriber.sock)
            self.subscriber = subscriber

    def replay_buffered_results(self, subscriber, last_seq):
        replay_results = [
            result
            for result in self.result_buffer
            if result["result_seq"] > last_seq and self.result_matches_subscriber(result, subscriber)
        ]

        if replay_results:
            self.send_result_push(subscriber, replay_results)

    def result_matches_subscriber(self, result, subscriber):
        if subscriber.pinky_id is None:
            return True
        return result.get("pinky_id") == subscriber.pinky_id

    def send_result_push(self, subscriber, results):
        if not results:
            return

        push_payload = {
            "batch_end_seq": results[-1]["result_seq"],
            "results": [dict(result) for result in results],
        }
        frame = build_frame(
            MESSAGE_CODE_FALL_RESULT_SUBSCRIBE,
            subscriber.next_push_sequence_no,
            push_payload,
            is_push=True,
        )
        subscriber.next_push_sequence_no += 1

        try:
            subscriber.sock.sendall(encode_frame(frame))
            print(
                f"[TCP] Fall result push sent: consumer_id={subscriber.consumer_id} "
                f"pinky_id={subscriber.pinky_id} count={len(results)} "
                f"batch_end_seq={push_payload['batch_end_seq']}"
            )

        except Exception as e:
            print(f"[TCP] Fall result push error: {e}")
            self.clear_subscriber_if_current(subscriber)

    def clear_subscriber_if_current(self, subscriber):
        with self.tcp_lock:
            if self.subscriber is subscriber:
                self.close_socket(subscriber.sock)
                self.subscriber = None

    def publish_fall_result(self, result):
        self.result_buffer.append(result)

        with self.tcp_lock:
            subscriber = self.subscriber

        if subscriber is None:
            print(
                f"[TCP] No fall result subscriber; dropping result_seq={result.get('result_seq')} "
                f"pinky_id={result.get('pinky_id')}"
            )
            return

        if not self.result_matches_subscriber(result, subscriber):
            print(
                f"[TCP] Fall result subscriber filter mismatch: "
                f"subscriber_pinky_id={subscriber.pinky_id} result_pinky_id={result.get('pinky_id')} "
                f"result_seq={result.get('result_seq')}"
            )
            return
        

        self.send_result_push(subscriber, [result])

    def stream_name_to_pinky_id(self, stream_name):
        if stream_name in STREAM_TO_PINKY_ID:
            return STREAM_TO_PINKY_ID[stream_name]

        if stream_name.startswith("pinky") and stream_name.endswith("_cam"):
            source = stream_name[: -len("_cam")]
            suffix = source[len("pinky"):]
            if suffix.isdigit():
                return f"pinky{int(suffix)}"

        return None

    @staticmethod
    def timestamp_us_to_iso(ts_us):
        dt = datetime.fromtimestamp(ts_us / 1_000_000, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    def build_positive_result(self, frame_meta, confidence):
        stream_name = frame_meta["stream_name"]
        pinky_id = self.stream_name_to_pinky_id(stream_name)
        now = time.monotonic()
        streak_key = pinky_id or stream_name

        self.fall_streak_start_monotonic.setdefault(streak_key, now)

        fall_streak_ms = int((now - self.fall_streak_start_monotonic[streak_key]) * 1000)

        self.result_seq = (self.result_seq + 1) & 0xFFFFFFFF or 1

        return {
            "result_seq": self.result_seq,
            "pinky_id": pinky_id,
            "frame_id": str(frame_meta["frame_id"]),
            "frame_ts": self.timestamp_us_to_iso(frame_meta["ts_us"]),
            "fall_detected": True,
            "confidence": confidence,
            "fall_streak_ms": fall_streak_ms,
            "alert_candidate": fall_streak_ms >= FALL_ALERT_THRESHOLD_MS,
            "evidence_image_id": None,
            "evidence_image_available": False,
        }

    def clear_fall_streak(self, frame_meta):
        stream_name = frame_meta["stream_name"]
        pinky_id = self.stream_name_to_pinky_id(stream_name)
        streak_key = pinky_id or stream_name
        self.fall_streak_start_monotonic.pop(streak_key, None)

    def close_subscriber(self):
        with self.tcp_lock:
            if self.subscriber is not None:
                self.close_socket(self.subscriber.sock)
                self.subscriber = None

    @staticmethod
    def close_socket(sock):
        try:
            sock.close()
        except Exception:
            pass

    @staticmethod
    def decode_udp_image(jpeg_bytes):
        return cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

    def detect_fall(self, frame):
        result = self.model(frame, verbose=False)[0]
        fall_detected = False
        best_confidence = 0.0

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())

                if cls_id == FALL_CLASS_ID:
                    fall_detected = True
                    best_confidence = max(best_confidence, float(box.conf[0].item()))

        return fall_detected, best_confidence, result.plot()

    def run(self):
        """
        UDP 이미지 수신 -> YOLO 추론 -> IF-PAT-005 positive result push
        """
        print("[SERVER] Running...")

        while not self.stop_event.is_set():
            try:
                data, addr = self.udp_sock.recvfrom(65535)
                packet = self.parse_rudp_packet(data)
                if packet is None:
                    continue

                jpeg_bytes, frame_meta = self._assemble_frame(packet)
                if jpeg_bytes is None:
                    continue

                frame = self.decode_udp_image(jpeg_bytes)

                if frame is None:
                    print(f"[UDP] Failed to decode frame: stream={frame_meta['stream_name']}")
                    continue

                fall_detected, confidence, visualized_frame = self.detect_fall(frame)

                if fall_detected:
                    result = self.build_positive_result(frame_meta, confidence)
                    if result["alert_candidate"]:
                        self.publish_fall_result(result)
                else:
                    self.clear_fall_streak(frame_meta)

                if SHOW_WINDOW:
                    display_frame = cv2.resize(
                        visualized_frame,
                        (640, 480),
                        interpolation=cv2.INTER_LINEAR,
                    )
                    cv2.imshow("Fallen Detection Server", display_frame)

                    # q 누르면 서버 종료
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

            except KeyboardInterrupt:
                break

            except Exception as e:
                print(f"[SERVER] Error: {e}")

        self.close()

    def close(self):
        """
        socket, window 자원 반환
        """
        self.stop_event.set()
        self.close_socket(self.udp_sock)
        self.close_socket(self.tcp_server_sock)
        self.close_subscriber()

        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        print("[SERVER] Closed.")


def main():
    server = FallenDetectionServer()

    try:
        server.run()

    except KeyboardInterrupt:
        pass

    finally:
        server.close()


if __name__ == "__main__":
    main()
