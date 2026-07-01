#!/usr/bin/env python3
"""test_speaking_animations.py — Preview candidate speaking animations on the robot.

Connects to Reachy Mini and plays each candidate speaking animation for a few
seconds so you can watch and decide which ones look best.

Usage:
    python test_speaking_animations.py

Controls (typed + Enter during the pause between animations):
    y  = approve this animation
    n  = reject
    s  = skip to next without rating
    r  = replay this animation
    q  = quit immediately

At the end you get a summary of approved animations.
"""
from __future__ import annotations

import math
import time
import sys
from typing import Callable, List, Tuple

from reachy_mini.utils import create_head_pose


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _send(reachy, pose, antennas):
    """Send head pose + antennas to the robot."""
    reachy.set_target_head_pose(pose)
    reachy.set_target_antenna_joint_positions(antennas)


def _neutral_pose():
    return create_head_pose(z=0, pitch=0, yaw=0, roll=0, degrees=True, mm=True)


def _smooth_to_neutral(reachy, duration=0.5, hz=50):
    """Smoothly return to neutral pose."""
    steps = int(duration * hz)
    dt = 1.0 / hz
    for i in range(steps + 1):
        alpha = i / steps
        # ease-in-out
        alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)
        pose = create_head_pose(
            z=0,
            pitch=0,
            yaw=0,
            roll=0,
            degrees=True,
            mm=True,
        )
        _send(reachy, pose, [0.0, 0.0])
        time.sleep(dt)


# ---------------------------------------------------------------------------
# Candidate speaking animations
# ---------------------------------------------------------------------------
# Each animation is a function(reachy, duration, hz) that drives the robot
# for `duration` seconds at `hz` Hz.
#
# Parameters are in degrees / mm to match create_head_pose conventions.

def anim_gentle_bob(reachy, duration=6.0, hz=50):
    """Classic vertical bob with clear pitch — strong and slow."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        phase = 2 * math.pi * t * 1.5
        bob_z = 5.0 * math.sin(phase)
        bob_pitch = 3.5 * math.sin(phase + 0.4)
        roll = 1.5 * math.sin(2 * math.pi * t / 11.0)
        pose = create_head_pose(
            z=bob_z, pitch=bob_pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_phase = 2 * math.pi * t * 1.2
        ant_r = 0.45 * math.sin(ant_phase)
        ant_l = 0.45 * math.sin(ant_phase + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_nodding(reachy, duration=6.0, hz=50):
    """Affirming nods — big clear pitch oscillations like 'yes yes yes'."""
    t0 = time.time()
    freq = 0.7
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        pitch = 6.0 * env * math.sin(2 * math.pi * freq * t)
        bob_z = 3.0 * env * math.sin(2 * math.pi * freq * t)
        roll = 1.0 * math.sin(2 * math.pi * t / 10.0)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.40 * env * math.sin(2 * math.pi * 0.9 * t)
        ant_l = 0.40 * env * math.sin(2 * math.pi * 0.9 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_head_tilt(reachy, duration=6.0, hz=50):
    """Big slow head tilt to one side and back — curious / listening pose."""
    t0 = time.time()
    side = 1.0
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        roll = side * 7.0 * env
        bob_z = 2.5 * math.sin(2 * math.pi * t * 1.2)
        pitch = 1.5 * math.sin(2 * math.pi * t * 1.2 + 0.4)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.40 * env * math.sin(2 * math.pi * 0.8 * t)
        ant_l = 0.40 * env * math.sin(2 * math.pi * 0.8 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_side_sway(reachy, duration=6.0, hz=50):
    """Big slow yaw sway — clear side-to-side glancing while explaining."""
    t0 = time.time()
    freq = 0.25
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        yaw = 8.0 * env * math.sin(2 * math.pi * freq * t)
        bob_z = 3.0 * math.sin(2 * math.pi * t * 1.5)
        roll = 1.2 * math.sin(2 * math.pi * t / 9.0)
        pose = create_head_pose(
            z=bob_z, pitch=0, yaw=yaw, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.40 * env * math.sin(2 * math.pi * 0.8 * t)
        ant_l = 0.40 * env * math.sin(2 * math.pi * 0.8 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_energetic_bob(reachy, duration=6.0, hz=50):
    """Strong bob with clear emphasis — excited / passionate speaking."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        phase = 2 * math.pi * t * 2.0
        bob_z = 6.0 * env * math.sin(phase)
        bob_pitch = 4.0 * env * math.sin(phase + 0.4)
        roll = 2.0 * env * math.sin(2 * math.pi * t / 7.0)
        emph = 0.0
        if int(t * 2) % 3 == 0:
            emph = 4.0 * env * math.sin(2 * math.pi * t * 0.5)
        pose = create_head_pose(
            z=bob_z, pitch=bob_pitch, yaw=emph, roll=roll,
            degrees=True, mm=True,
        )
        ant_phase = 2 * math.pi * t * 1.8
        ant_r = 0.55 * env * math.sin(ant_phase)
        ant_l = 0.55 * env * math.sin(ant_phase + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_thoughtful_pause(reachy, duration=6.0, hz=50):
    """Clear upward gaze with slow movement — the 'thinking' speaking style."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        pitch = -4.0 * env  # look clearly up
        bob_z = 2.0 * math.sin(2 * math.pi * t * 0.8)
        roll = 1.0 * math.sin(2 * math.pi * t / 12.0)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.30 * env * math.sin(2 * math.pi * 0.5 * t)
        ant_l = 0.30 * env * math.sin(2 * math.pi * 0.5 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_antenna_dance(reachy, duration=6.0, hz=50):
    """Big antenna swings with clear head motion — expressive and visible."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        bob_z = 2.0 * math.sin(2 * math.pi * t * 1.2)
        pitch = 1.5 * math.sin(2 * math.pi * t * 1.2 + 0.4)
        roll = 1.0 * math.sin(2 * math.pi * t / 10.0)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        freq = 1.0
        ant_r = 0.65 * env * math.sin(2 * math.pi * freq * t)
        ant_l = 0.65 * env * math.sin(2 * math.pi * freq * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_quick_nods(reachy, duration=6.0, hz=50):
    """Burst of big clear nods — enthusiastic agreement."""
    t0 = time.time()
    freq = 1.0
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        pitch = 5.0 * env * math.sin(2 * math.pi * freq * t)
        bob_z = 3.0 * env * math.sin(2 * math.pi * freq * t)
        roll = 1.5 * env * math.sin(2 * math.pi * t / 7.0)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.50 * env * math.sin(2 * math.pi * 1.2 * t)
        ant_l = 0.50 * env * math.sin(2 * math.pi * 1.2 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_bob_and_sway(reachy, duration=6.0, hz=50):
    """Combined strong bob + clear yaw sway — conversational and lively."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        phase = 2 * math.pi * t * 1.5
        bob_z = 5.0 * env * math.sin(phase)
        bob_pitch = 3.0 * env * math.sin(phase + 0.4)
        yaw = 6.0 * env * math.sin(2 * math.pi * t * 0.22)
        roll = 1.5 * env * math.sin(2 * math.pi * t / 9.0)
        pose = create_head_pose(
            z=bob_z, pitch=bob_pitch, yaw=yaw, roll=roll,
            degrees=True, mm=True,
        )
        ant_phase = 2 * math.pi * t * 1.2
        ant_r = 0.45 * env * math.sin(ant_phase)
        ant_l = 0.45 * env * math.sin(ant_phase + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


def anim_wobble(reachy, duration=6.0, hz=50):
    """Big playful roll wobble — head rocks clearly side to side, fun and characterful."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        if t >= duration:
            break
        env = math.sin(math.pi * t / duration)
        roll = 7.0 * env * math.sin(2 * math.pi * t * 0.6)
        bob_z = 3.5 * math.sin(2 * math.pi * t * 1.5)
        pitch = 2.0 * math.sin(2 * math.pi * t * 1.5 + 0.4)
        pose = create_head_pose(
            z=bob_z, pitch=pitch, yaw=0, roll=roll,
            degrees=True, mm=True,
        )
        ant_r = 0.50 * env * math.sin(2 * math.pi * 0.9 * t)
        ant_l = 0.50 * env * math.sin(2 * math.pi * 0.9 * t + math.pi * 0.7)
        _send(reachy, pose, [ant_r, ant_l])
        time.sleep(1.0 / hz)


# ---------------------------------------------------------------------------
# Animation registry
# ---------------------------------------------------------------------------
ANIMATIONS: List[Tuple[str, str, Callable]] = [
    ("gentle_bob",       "Classic gentle vertical bob (current baseline)",      anim_gentle_bob),
    ("nodding",          "Affirming nods — 'yes yes yes'",                      anim_nodding),
    ("head_tilt",        "Slow head tilt side to side — curious/listening",     anim_head_tilt),
    ("side_sway",        "Gentle yaw sway — glancing while explaining",         anim_side_sway),
    ("energetic_bob",    "Bigger faster bob with emphasis — excited",           anim_energetic_bob),
    ("thoughtful_pause", "Subtle upward gaze — thinking style",                 anim_thoughtful_pause),
    ("antenna_dance",    "Lively antennas, head calm — expressive",             anim_antenna_dance),
    ("quick_nods",       "Burst of quick small nods — enthusiastic",            anim_quick_nods),
    ("bob_and_sway",     "Combined bob + yaw sway — conversational",            anim_bob_and_sway),
    ("wobble",           "Playful roll wobble — fun and characterful",          anim_wobble),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    from reachy_mini import ReachyMini

    print("=" * 60)
    print("  Speaking Animation Preview Tool")
    print("  Watch each animation, then rate it.")
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
            print("  Playing for 6 seconds... watch the robot!\n")

            fn(reachy, duration=6.0, hz=50)

            _smooth_to_neutral(reachy, duration=0.4)

            print(f"  Done. Rate this animation:")
            print(f"    y = approve   n = reject   s = skip   r = replay   q = quit")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice == "y":
                approved.append(name)
                print(f"  ✓ Approved: {name}")
                idx += 1
            elif choice == "n":
                rejected.append(name)
                print(f"  ✗ Rejected: {name}")
                idx += 1
            elif choice == "r":
                print(f"  ↻ Replaying: {name}")
                continue
            elif choice == "q":
                print("\n  Quitting early.")
                break
            else:
                print(f"  (skipped without rating)")
                idx += 1

        _smooth_to_neutral(reachy, duration=0.5)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    if approved:
        print(f"\n  ✓ APPROVED ({len(approved)}):")
        for a in approved:
            print(f"    - {a}")
    else:
        print("\n  No animations approved.")

    if rejected:
        print(f"\n  ✗ REJECTED ({len(rejected)}):")
        for r in rejected:
            print(f"    - {r}")

    unrated = [a for a, _, _ in ANIMATIONS if a not in approved and a not in rejected]
    if unrated:
        print(f"\n  ○ UNRATED ({len(unrated)}):")
        for u in unrated:
            print(f"    - {u}")

    print(f"\n{'='*60}")
    if approved:
        print("  Next step: tell me which ones you approved and I'll")
        print("  integrate them into the robot's speaking animation system.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
