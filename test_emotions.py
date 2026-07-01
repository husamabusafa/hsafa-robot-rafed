#!/usr/bin/env python3
"""test_emotions.py — Play a single emotion clip on the robot.

Usage:
    python test_emotions.py <emotion_name>
    python test_emotions.py bored1
    python test_emotions.py curious1

Run without args to list all available emotions:
    python test_emotions.py
"""
import sys


def main():
    if len(sys.argv) < 2:
        from reachy_mini.motion.recorded_move import RecordedMoves
        m = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        print("Available emotions:")
        for name in sorted(m.list_moves()):
            print(f"  {name}")
        print(f"\nUsage: python {sys.argv[0]} <emotion_name>")
        return

    name = sys.argv[1]

    from reachy_mini import ReachyMini
    from reachy_mini.motion.recorded_move import RecordedMoves

    moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
    available = moves.list_moves()
    if name not in available:
        print(f"Error: '{name}' not found.")
        print(f"Available: {', '.join(sorted(available))}")
        return

    move = moves.get(name)
    print(f"Playing '{name}' ({move.duration:.2f}s) with sound...")

    with ReachyMini(automatic_body_yaw=False) as reachy:
        import asyncio
        asyncio.run(reachy.async_play_move(move, sound=True, initial_goto_duration=0.3))

    print("Done.")


if __name__ == "__main__":
    main()
