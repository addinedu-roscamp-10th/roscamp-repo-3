#!/usr/bin/env python3

from pathlib import Path


RESOLUTION = 0.05
WIDTH = 400
HEIGHT = 280
ORIGIN_X = -10.0
ORIGIN_Y = -7.0

FREE = 254
OCCUPIED = 0


def world_to_pixel(x: float, y: float) -> tuple[int, int]:
    px = int(round((x - ORIGIN_X) / RESOLUTION))
    py = int(round((y - ORIGIN_Y) / RESOLUTION))
    return px, py


def draw_rect(grid, cx, cy, sx, sy):
    half_x = sx / 2.0
    half_y = sy / 2.0
    min_x, min_y = world_to_pixel(cx - half_x, cy - half_y)
    max_x, max_y = world_to_pixel(cx + half_x, cy + half_y)

    min_x = max(0, min_x)
    max_x = min(WIDTH - 1, max_x)
    min_y = max(0, min_y)
    max_y = min(HEIGHT - 1, max_y)

    for py in range(min_y, max_y + 1):
        row = HEIGHT - 1 - py
        for px in range(min_x, max_x + 1):
            grid[row][px] = OCCUPIED


def main():
    package_dir = Path(__file__).resolve().parents[1]
    output_path = package_dir / "maps" / "fleet_practice_large.pgm"

    grid = [[FREE for _ in range(WIDTH)] for _ in range(HEIGHT)]

    obstacles = [
        (0.0, 5.925, 18.0, 0.15),
        (0.0, -5.925, 18.0, 0.15),
        (-8.925, 0.0, 0.15, 12.0),
        (8.925, 0.0, 0.15, 12.0),
        (-3.45, 5.15, 0.18, 0.12),
        (-2.25, 5.15, 0.18, 0.12),
        (-7.4, -0.6, 0.7, 0.9),
        (-7.4, 0.5, 0.7, 0.9),
        (-7.4, -4.3, 0.8, 1.0),
        (-7.4, -3.2, 0.8, 1.0),
        (-2.4, 2.7, 1.5, 0.35),
        (0.0, 2.7, 1.5, 0.35),
        (2.4, 2.7, 1.5, 0.35),
        (-2.4, 1.0, 1.5, 0.35),
        (0.0, 1.0, 1.5, 0.35),
        (2.4, 1.0, 1.5, 0.35),
        (7.0, 2.35, 2.3, 0.08),
        (7.0, -0.35, 2.3, 0.08),
        (8.15, 1.0, 0.08, 2.78),
        (7.2, 1.55, 1.0, 0.7),
        (6.75, 0.8, 0.35, 0.35),
        (7.0, -2.05, 2.3, 0.08),
        (7.0, -4.75, 2.3, 0.08),
        (8.15, -3.4, 0.08, 2.78),
        (7.2, -2.85, 1.0, 0.7),
        (6.75, -3.6, 0.35, 0.35),
    ]

    for obstacle in obstacles:
        draw_rect(grid, *obstacle)

    with output_path.open("wb") as output:
        output.write(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode("ascii"))
        for row in grid:
            output.write(bytes(row))

    print(output_path)


if __name__ == "__main__":
    main()
