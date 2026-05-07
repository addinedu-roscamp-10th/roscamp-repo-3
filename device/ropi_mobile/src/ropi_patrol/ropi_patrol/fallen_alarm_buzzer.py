#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

# 실제 Buzzer 위치에 맞게 import 경로가 다르면 여기만 수정하면 됨
from ropi_patrol.buzzer import Buzzer


ALARM_TOPIC = "/fall_alarm"


class FallenAlarm(Node):
    def __init__(self):
        super().__init__("fallen_alarm")

        self.alarm_active = False
        self.stop_event = threading.Event()
        self.led_process = None

        self.buzzer = Buzzer()

        self.sub = self.create_subscription(
            Bool,
            ALARM_TOPIC,
            self.alarm_callback,
            10,
        )

        # 부저를 ROS callback 안에서 직접 오래 울리면 callback이 막힐 수 있으므로
        # 부저 동작만 별도 thread에서 처리
        self.buzzer_thread = threading.Thread(
            target=self.buzzer_loop,
            daemon=True,
        )
        self.buzzer_thread.start()

        self.get_logger().info("Fallen alarm node started.")

    def alarm_callback(self, msg):
        """
        /fall_alarm 토픽 수신

        True  -> 부저 ON
        False -> 부저 OFF
        """
        next_alarm_active = bool(msg.data)
        if self.alarm_active == next_alarm_active:
            if self.alarm_active:
                self.start_led_blink()
            return

        self.alarm_active = next_alarm_active
        self.get_logger().info(f"Alarm state: {self.alarm_active}")

        if self.alarm_active:
            self.start_led_blink()
        else:
            self.stop_led_blink()

    def start_led_blink(self):
        """
        LED 제어는 pinkylib import 문제를 피하기 위해 별도 프로세스로 실행한다.
        """
        if self.led_process and self.led_process.poll() is None:
            return

        led_script = Path(__file__).with_name("led.py")
        led_command = self.make_led_command(led_script, "--interval", "1.0")

        try:
            self.led_process = subprocess.Popen(
                led_command,
                start_new_session=True,
            )
            self.get_logger().info("LED blink process started.")

        except Exception as e:
            self.led_process = None
            self.get_logger().error(f"Failed to start LED blink process: {e}")

    def turn_led_off_once(self):
        led_script = Path(__file__).with_name("led.py")
        led_command = self.make_led_command(led_script, "--off")

        try:
            subprocess.run(
                led_command,
                timeout=3.0,
                check=False,
            )

        except Exception as e:
            self.get_logger().error(f"Failed to turn LED off: {e}")

    def make_led_command(self, led_script, *args):
        command = [sys.executable, str(led_script), *args]

        if os.geteuid() == 0:
            return command

        # pinkylib는 일반 사용자 import 시 sudo 재실행을 수행하므로,
        # 처음부터 root python으로 led.py를 실행해 중간 shell/sudo 프로세스를 줄인다.
        return ["sudo", *command]

    def stop_led_blink(self):
        """
        LED 깜빡임 프로세스를 종료하면 led.py의 finally에서 LED를 끈다.
        """
        if not self.led_process:
            return

        process = self.led_process
        self.led_process = None

        if process.poll() is not None:
            return

        force_stopped = False

        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2.0)

        except subprocess.TimeoutExpired:
            force_stopped = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1.0)

        except Exception as e:
            self.get_logger().error(f"Failed to stop LED blink process: {e}")

        if force_stopped:
            self.turn_led_off_once()

    def buzzer_loop(self):
        """
        alarm_active가 True인 동안 부저를 반복해서 울림
        False가 되면 부저 정지
        """
        buzzer_started = False

        while not self.stop_event.is_set():
            try:
                if self.alarm_active:
                    if not buzzer_started:
                        self.buzzer.buzzer_start()
                        buzzer_started = True

                    # 2초 동안 부저 울림
                    self.buzzer.buzzer(2)

                else:
                    if buzzer_started:
                        self.buzzer.buzzer_stop()
                        buzzer_started = False

                    time.sleep(0.1)

            except Exception as e:
                self.get_logger().error(f"Buzzer error: {e}")
                time.sleep(0.5)

        # 종료 시 부저 정지
        try:
            self.buzzer.buzzer_stop()
        except Exception:
            pass

        self.stop_led_blink()

    def close(self):
        """
        부저 자원 반환
        """
        self.stop_event.set()
        self.stop_led_blink()

        try:
            self.buzzer.buzzer_stop()
        except Exception:
            pass

        try:
            self.buzzer.close()
        except Exception:
            pass

        self.get_logger().info("Fallen alarm node closed.")


def main(args=None):
    rclpy.init(args=args)

    node = FallenAlarm()

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
