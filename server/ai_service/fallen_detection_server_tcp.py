#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import socket
import threading
import time

import cv2
import numpy as np
from ultralytics import YOLO


UDP_HOST = "0.0.0.0"
UDP_PORT = 5005

TCP_HOST = "0.0.0.0"
TCP_PORT = 6000

MODEL_PATH = "/home/addinedu/Documents/fallen_detection/models/yolo26x_gen_v1_weights/best.pt"

# class id
NORMAL_CLASS_ID = 0
FALL_CLASS_ID = 1

# 1초 이상 낙상 감지 시 alarm=True
FALL_HOLD_SEC = 1.0

# 3초 이상 낙상 미감지 시 alarm=False
NO_FALL_RELEASE_SEC = 3.0

# 시각화 여부
SHOW_WINDOW = True


class FallenDetectionServer:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)

        # UDP socket: 클라이언트 이미지 수신
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((UDP_HOST, UDP_PORT))

        # TCP socket: 클라이언트에 alarm 전송
        self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_sock.bind((TCP_HOST, TCP_PORT))
        self.tcp_server_sock.listen(1)

        self.tcp_client_sock = None
        self.tcp_lock = threading.Lock()

        self.stop_event = threading.Event()

        # 낙상 상태 관리
        self.alarm_active = False
        self.fall_start_time = None
        self.last_fall_time = None

        # TCP client accept thread
        self.accept_thread = threading.Thread(
            target=self.accept_tcp_client_loop,
            daemon=True,
        )
        self.accept_thread.start()

        print(f"[SERVER] UDP image receive: {UDP_HOST}:{UDP_PORT}")
        print(f"[SERVER] TCP alarm server: {TCP_HOST}:{TCP_PORT}")
        print(f"[SERVER] Model loaded: {MODEL_PATH}")

    def accept_tcp_client_loop(self):
        """
        클라이언트 TCP 연결을 기다림.
        클라이언트가 연결되면 self.tcp_client_sock에 저장.
        """
        while not self.stop_event.is_set():
            try:
                print("[TCP] Waiting for client...")
                client_sock, addr = self.tcp_server_sock.accept()

                with self.tcp_lock:
                    if self.tcp_client_sock is not None:
                        try:
                            self.tcp_client_sock.close()
                        except Exception:
                            pass

                    self.tcp_client_sock = client_sock

                print(f"[TCP] Client connected: {addr}")

                # 연결 직후 현재 alarm 상태 전송
                self.send_alarm(self.alarm_active)

            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[TCP] Accept error: {e}")
                    time.sleep(1.0)

    def send_alarm(self, alarm):
        """
        TCP로 클라이언트에 alarm 상태 전송
        """
        msg = {
            "alarm": bool(alarm),
            "time": time.time(),
        }

        data = json.dumps(msg) + "\n"

        with self.tcp_lock:
            if self.tcp_client_sock is None:
                return

            try:
                self.tcp_client_sock.sendall(data.encode("utf-8"))

            except Exception as e:
                print(f"[TCP] Send error: {e}")

                try:
                    self.tcp_client_sock.close()
                except Exception:
                    pass

                self.tcp_client_sock = None

    def decode_udp_image(self, data):
        """
        UDP로 받은 JPEG bytes를 OpenCV image로 변환
        """
        np_data = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        return frame

    def detect_fall(self, frame):
        """
        YOLO 추론 후 낙상 class가 있는지 확인

        return:
            fall_detected: bool
            visualized_frame: bbox가 그려진 frame
        """
        results = self.model(frame, verbose=False)

        result = results[0]
        fall_detected = False

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())

                if cls_id == FALL_CLASS_ID:
                    fall_detected = True
                    break

        # Ultralytics plot: bounding box가 그려진 이미지 반환
        visualized_frame = result.plot()

        return fall_detected, visualized_frame

    def update_alarm_state(self, fall_detected):
        """
        낙상 감지 결과를 기반으로 alarm 상태 갱신

        - 낙상이 1초 이상 지속되면 True 전송
        - 낙상이 3초 이상 없으면 False 전송
        """
        now = time.time()

        if fall_detected:
            self.last_fall_time = now

            if self.fall_start_time is None:
                self.fall_start_time = now

            fall_duration = now - self.fall_start_time

            if not self.alarm_active and fall_duration >= FALL_HOLD_SEC:
                self.alarm_active = True
                print("[ALARM] ON")
                self.send_alarm(True)

        else:
            self.fall_start_time = None

            if self.alarm_active:
                if self.last_fall_time is None:
                    no_fall_duration = 0.0
                else:
                    no_fall_duration = now - self.last_fall_time

                if no_fall_duration >= NO_FALL_RELEASE_SEC:
                    self.alarm_active = False
                    print("[ALARM] OFF")
                    self.send_alarm(False)

    def run(self):
        """
        UDP 이미지 수신 -> YOLO 추론 -> alarm 상태 TCP 전송
        """
        print("[SERVER] Running...")

        while not self.stop_event.is_set():
            try:
                data, addr = self.udp_sock.recvfrom(65535)

                frame = self.decode_udp_image(data)

                if frame is None:
                    print("[UDP] Failed to decode frame.")
                    continue

                fall_detected, visualized_frame = self.detect_fall(frame)

                self.update_alarm_state(fall_detected)

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

        try:
            self.udp_sock.close()
        except Exception:
            pass

        try:
            self.tcp_server_sock.close()
        except Exception:
            pass

        with self.tcp_lock:
            if self.tcp_client_sock is not None:
                try:
                    self.tcp_client_sock.close()
                except Exception:
                    pass

                self.tcp_client_sock = None

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