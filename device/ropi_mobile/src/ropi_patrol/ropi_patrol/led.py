#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import signal
import threading
import time


RED = (255, 0, 0)
OFF = (0, 0, 0)

stop_event = threading.Event()


def handle_signal(signum, frame):
    stop_event.set()


def create_led():
    # pinkylib import를 실행 시점까지 늦춰 ROS 패키지 메타데이터 생성 중
    # 이 파일이 import되어도 하드웨어 라이브러리를 물지 않게 한다.
    from pinkylib import LED

    return LED()


def fill_safely(leds, color):
    leds.fill(color)


def blink_red(interval):
    leds = create_led()

    try:
        is_on = False
        while not stop_event.is_set():
            is_on = not is_on
            fill_safely(leds, RED if is_on else OFF)
            stop_event.wait(interval)

    finally:
        try:
            fill_safely(leds, OFF)
        finally:
            leds.close()


def turn_off():
    leds = create_led()

    try:
        fill_safely(leds, OFF)
    finally:
        leds.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="LED blink interval in seconds.",
    )
    parser.add_argument(
        "--off",
        action="store_true",
        help="Turn LED off once and exit.",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.off:
        turn_off()
        return

    blink_red(args.interval)


if __name__ == "__main__":
    main()
