#!/usr/bin/env python3
"""test_idle_animations.py — Preview idle animations on the robot.

5 animations with BIG, SLOW, NOTICEABLE head movements.

Usage:
    python test_idle_animations.py

Controls (typed + Enter after each animation):
    y = approve   n = reject   s = skip   r = replay   q = quit
"""
from __future__ import annotations

import math
import time
import random
from typing import Callable, List, Tuple

from reachy_mini.utils import create_head_pose


def _send(reachy, pose, antennas):
    reachy.set_target_head_pose(pose)
    reachy.set_target_antenna_joint_positions(antennas)


def _ease_inout(t: float) -> float:
    """Smooth ease 0 -> 1 using cosine. Stays at endpoints."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _env(t: float, dur: float) -> float:
    return math.sin(math.pi * t / dur)


def _smooth_to_neutral(reachy, duration=0.8, hz=30):
    steps = int(duration * hz)
    dt = 1.0 / hz
    for i in range(steps + 1):
        alpha = i / steps
        alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)
        pose = create_head_pose(z=0, pitch=0, yaw=0, roll=0, degrees=True, mm=True)
        _send(reachy, pose, [0.0, 0.0])
        time.sleep(dt)


# ============================================================================
# 5 BIG, SLOW, NOTICEABLE idle animations
# ============================================================================

def idle_look_far_left_right(reachy, duration=4.0, hz=30):
    """Look far left, hold, sweep far right, hold, return — searching."""
    t0 = time.time()
    dur = duration
    while True:
        t = time.time() - t0
        if t >= dur:
            break
        p = t / dur
        if p < 0.30:
            yaw = -25.0 * _ease_inout(p / 0.30)
        elif p < 0.45:
            yaw = -25.0
        elif p < 0.75:
            yaw = -25.0 + 50.0 * _ease_inout((p - 0.45) / 0.30)
        elif p < 0.90:
            yaw = 25.0
        else:
            yaw = 25.0 * (1.0 - _ease_inout((p - 0.90) / 0.10))
        pitch = 2.0 * math.sin(math.pi * p)
        z = 1.0 * math.sin(2 * math.pi * t * 0.2)
        ant_r = 0.15 * math.sin(2 * math.pi * t / 6.0)
        ant_l = 0.15 * math.sin(2 * math.pi * t / 6.5 + 0.8)
        pose = create_head_pose(z=z, pitch=pitch, yaw=yaw, roll=0, degrees=True, mm=True)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def idle_big_tilt_hold(reachy, duration=4.0, hz=30):
    """Tilt head far to one side, hold, tilt to other side, hold — curious."""
    t0 = time.time()
    dur = duration
    side = random.choice((-1.0, 1.0))
    while True:
        t = time.time() - t0
        if t >= dur:
            break
        p = t / dur
        if p < 0.25:
            roll = side * 12.0 * _ease_inout(p / 0.25)
        elif p < 0.45:
            roll = side * 12.0
        elif p < 0.70:
            roll = side * 12.0 - side * 24.0 * _ease_inout((p - 0.45) / 0.25)
        elif p < 0.85:
            roll = -side * 12.0
        else:
            roll = -side * 12.0 * (1.0 - _ease_inout((p - 0.85) / 0.15))
        pitch = -2.0 * math.sin(math.pi * p)
        z = 1.5 * math.sin(2 * math.pi * t * 0.15)
        ant_r = 0.20 * math.sin(2 * math.pi * t / 5.0)
        ant_l = 0.20 * math.sin(2 * math.pi * t / 5.5 + 0.8)
        pose = create_head_pose(z=z, pitch=pitch, yaw=0, roll=roll, degrees=True, mm=True)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def idle_look_up_wonder(reachy, duration=4.0, hz=30):
    """Slowly look up and around — wondering / thinking."""
    t0 = time.time()
    dur = duration
    while True:
        t = time.time() - t0
        if t >= dur:
            break
        p = t / dur
        if p < 0.20:
            pitch = -15.0 * _ease_inout(p / 0.20)
        elif p < 0.80:
            pitch = -15.0
        else:
            pitch = -15.0 * (1.0 - _ease_inout((p - 0.80) / 0.20))
        yaw = 10.0 * math.sin(2 * math.pi * t * 0.12)
        roll = 2.0 * math.sin(2 * math.pi * t / 10.0)
        z = 2.0 * math.sin(2 * math.pi * t * 0.15)
        ant_r = 0.20 * math.sin(2 * math.pi * 0.4 * t)
        ant_l = 0.20 * math.sin(2 * math.pi * 0.4 * t + math.pi * 0.7)
        pose = create_head_pose(z=z, pitch=pitch, yaw=yaw, roll=roll, degrees=True, mm=True)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def idle_boredom_droop(reachy, duration=4.0, hz=30):
    """Head droops far down, holds, then slowly looks up — bored/tired."""
    t0 = time.time()
    dur = duration
    while True:
        t = time.time() - t0
        if t >= dur:
            break
        p = t / dur
        if p < 0.30:
            pitch = 12.0 * _ease_inout(p / 0.30)
            ant_r = -0.20 * _ease_inout(p / 0.30)
            ant_l = -0.20 * _ease_inout(p / 0.30)
        elif p < 0.60:
            pitch = 12.0
            ant_r = -0.20
            ant_l = -0.20
        else:
            lt = (p - 0.60) / 0.40
            pitch = 12.0 - 20.0 * _ease_inout(lt)
            ant_r = -0.20 + 0.35 * _ease_inout(lt) * math.sin(2 * math.pi * lt * 0.8)
            ant_l = -0.20 + 0.35 * _ease_inout(lt) * math.sin(2 * math.pi * lt * 0.8 + math.pi * 0.7)
        z = 1.0 * math.sin(2 * math.pi * t * 0.15)
        roll = 1.0 * math.sin(2 * math.pi * t / 12.0)
        pose = create_head_pose(z=z, pitch=pitch, yaw=0, roll=roll, degrees=True, mm=True)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def idle_slow_scan(reachy, duration=4.0, hz=30):
    """Slow continuous scan — yaw sweeps far left to right with pitch variation."""
    t0 = time.time()
    dur = duration
    while True:
        t = time.time() - t0
        if t >= dur:
            break
        p = t / dur
        # Smooth sweep using ease_inout: 0->1 across full duration
        e = _ease_inout(p)
        yaw = -20.0 + 40.0 * e  # -20 to +20 smoothly
        pitch = 5.0 * math.sin(math.pi * p)  # down in middle, level at ends
        roll = 1.5 * math.sin(2 * math.pi * t / 10.0)
        z = 1.5 * math.sin(2 * math.pi * t * 0.15)
        ant_r = 0.15 * math.sin(2 * math.pi * t / 5.0)
        ant_l = 0.15 * math.sin(2 * math.pi * t / 5.5 + 0.8)
        pose = create_head_pose(z=z, pitch=pitch, yaw=yaw, roll=roll, degrees=True, mm=True)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


# ============================================================================
# Registry — 5 animations only
# ============================================================================
ANIMATIONS: List[Tuple[str, str, Callable]] = [
    ("look_far_left_right", "Look far left, hold, sweep far right, hold — searching",  idle_look_far_left_right),
    ("big_tilt_hold",       "Tilt far to one side, hold, tilt other side, hold — curious", idle_big_tilt_hold),
    ("look_up_wonder",      "Slowly look far up and drift — wondering/thinking",       idle_look_up_wonder),
    ("boredom_droop",       "Head droops far down, holds, then looks up — bored/tired", idle_boredom_droop),
    ("slow_scan",           "Slow continuous scan left to right with pitch variation",  idle_slow_scan),
]


def main():
    from reachy_mini import ReachyMini

    print("=" * 60)
    print("  Idle Animation Preview Tool")
    print("  5 animations — BIG, SLOW, NOTICEABLE")
    print("  10 seconds each, 30 Hz")
    print("=" * 60)

    approved: List[str] = []
    rejected: List[str] = []

    with ReachyMini(automatic_body_yaw=False) as reachy:
        print("\nRobot connected. Starting in 2 seconds...\n")
        time.sleep(2.0)

        idx = 0
        while idx < len(ANIMATIONS):
            name, desc, fn = ANIMATIONS[idx]
            print(f"\n{'='*60}")
            print(f"  [{idx+1}/{len(ANIMATIONS)}] {name}")
            print(f"  {desc}")
            print(f"{'='*60}")
            print(f"  Playing for 4 seconds... watch the robot!\n")

            fn(reachy, duration=4.0, hz=30)

            _smooth_to_neutral(reachy, duration=0.8)

            print(f"  Done. Rate this animation:")
            print(f"    y = approve   n = reject   s = skip   r = replay   q = quit")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice == "y":
                approved.append(name)
                print(f"  + Approved: {name}")
                idx += 1
            elif choice == "n":
                rejected.append(name)
                print(f"  - Rejected: {name}")
                idx += 1
            elif choice == "r":
                print(f"  ~ Replaying: {name}")
                continue
            elif choice == "q":
                print("\n  Quitting early.")
                break
            else:
                print(f"  (skipped without rating)")
                idx += 1

        _smooth_to_neutral(reachy, duration=1.0)

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    if approved:
        print(f"\n  + APPROVED ({len(approved)}):")
        for a in approved:
            print(f"    - {a}")
    else:
        print("\n  No animations approved.")

    if rejected:
        print(f"\n  - REJECTED ({len(rejected)}):")
        for r in rejected:
            print(f"    - {r}")

    unrated = [a for a, _, _ in ANIMATIONS if a not in approved and a not in rejected]
    if unrated:
        print(f"\n  o UNRATED ({len(unrated)}):")
        for u in unrated:
            print(f"    - {u}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
