"""animation.py - Overlay animations applied on top of the face-tracking pose.

Each animation returns a dict of deltas::

    {
        "roll":     float,          # radians, absolute roll offset
        "pitch":    float,          # radians, additive pitch offset
        "yaw":      float,          # radians, additive yaw offset
        "antennas": (right, left),  # radians, absolute antenna positions
    }

The controller blends these offsets onto the tracking pose so the robot looks
alive whether it is quietly staring or actively talking.
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable, List, Optional, Tuple


class IdleAnimation:
    """Idle overlay - the head stays perfectly locked on the face so the
    stare is pristine; only the antennas "breathe" for a hint of life.

    Any head motion here would fight the P-controller and break the look-at
    behavior, so we zero all three axes (roll/pitch/yaw) on purpose.
    """

    def __init__(self) -> None:
        self.t0 = time.time()

    def offsets(self, now: Optional[float] = None) -> dict:
        now = now if now is not None else time.time()
        t = now - self.t0

        # Slow breath modulation (0.22 Hz) drives the antennas only.
        breath = math.sin(2.0 * math.pi * 0.22 * t)
        ant_base = math.radians(-8.0)
        ant_wiggle = math.radians(3.0) * breath
        right_ant = ant_base + ant_wiggle
        left_ant = ant_base - ant_wiggle

        return {
            "roll":     0.0,
            "pitch":    0.0,
            "yaw":      0.0,
            "antennas": (right_ant, left_ant),
        }


# ---------------------------------------------------------------------------
# Speaking gestures
# ---------------------------------------------------------------------------
# Each gesture is a factory that returns (duration_s, offsets_fn).  The
# factory randomises amplitude / frequency / direction so every invocation
# feels a little different.  All gestures use a half-sine envelope so they
# start and end at the neutral pose – switching between them never snaps.
#
# Only *one* head axis moves per gesture (plus antennas).  Real humans
# don't nod, tilt and sway simultaneously; keeping each gesture simple
# looks far more natural than three superposed sine waves.

_ANT_TALK = math.radians(8.0)


def _env(t: float, dur: float) -> float:
    """Half-sine envelope: smoothly 0 → 1 → 0 over ``[0, dur]``."""
    return math.sin(math.pi * t / dur)


def _make_gentle_nod() -> Tuple[float, Callable[[float], dict]]:
    """Slow affirming nods – the classic 'yes, I hear you' gesture."""
    dur = random.uniform(3.0, 5.0)
    freq = random.uniform(0.5, 0.8)
    amp = math.radians(random.uniform(0.8, 1.4))
    ant_freq = random.uniform(0.9, 1.3)

    def fn(t: float) -> dict:
        e = _env(t, dur)
        pitch = amp * e * math.sin(2 * math.pi * freq * t)
        flick = math.radians(2.0) * e * math.sin(2 * math.pi * ant_freq * t)
        return {"roll": 0.0, "pitch": pitch, "yaw": 0.0,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


def _make_head_tilt() -> Tuple[float, Callable[[float], dict]]:
    """Slow head tilt to one side and back – a listening / curious pose."""
    dur = random.uniform(3.5, 5.5)
    side = random.choice((-1.0, 1.0))
    amp = math.radians(random.uniform(1.0, 2.0))
    ant_freq = random.uniform(0.8, 1.2)

    def fn(t: float) -> dict:
        e = _env(t, dur)
        roll = side * amp * e
        flick = math.radians(2.0) * e * math.sin(2 * math.pi * ant_freq * t)
        return {"roll": roll, "pitch": 0.0, "yaw": 0.0,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


def _make_thoughtful() -> Tuple[float, Callable[[float], dict]]:
    """Subtle upward gaze with minimal movement – the 'thinking' pause."""
    dur = random.uniform(3.0, 5.0)
    amp = math.radians(random.uniform(0.5, 1.0))
    ant_freq = random.uniform(0.6, 0.9)

    def fn(t: float) -> dict:
        e = _env(t, dur)
        pitch = -amp * e
        flick = math.radians(1.5) * e * math.sin(2 * math.pi * ant_freq * t)
        return {"roll": 0.0, "pitch": pitch, "yaw": 0.0,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


def _make_antenna_dance() -> Tuple[float, Callable[[float], dict]]:
    """Lively antenna wiggle with the head held still – expressive but calm."""
    dur = random.uniform(2.5, 4.0)
    freq = random.uniform(1.0, 1.8)
    amp = math.radians(random.uniform(2.5, 4.0))

    def fn(t: float) -> dict:
        e = _env(t, dur)
        flick = amp * e * math.sin(2 * math.pi * freq * t)
        return {"roll": 0.0, "pitch": 0.0, "yaw": 0.0,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


def _make_side_sway() -> Tuple[float, Callable[[float], dict]]:
    """Gentle yaw sway – like glancing side to side while explaining."""
    dur = random.uniform(3.5, 5.5)
    freq = random.uniform(0.3, 0.5)
    amp = math.radians(random.uniform(0.6, 1.2))
    ant_freq = random.uniform(0.9, 1.3)

    def fn(t: float) -> dict:
        e = _env(t, dur)
        yaw = amp * e * math.sin(2 * math.pi * freq * t)
        flick = math.radians(2.0) * e * math.sin(2 * math.pi * ant_freq * t)
        return {"roll": 0.0, "pitch": 0.0, "yaw": yaw,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


def _make_quick_nods() -> Tuple[float, Callable[[float], dict]]:
    """A burst of two or three quick small nods – enthusiastic agreement."""
    dur = random.uniform(2.5, 4.0)
    freq = random.uniform(1.2, 1.8)
    amp = math.radians(random.uniform(0.6, 1.0))
    ant_freq = random.uniform(1.0, 1.5)

    def fn(t: float) -> dict:
        e = _env(t, dur)
        pitch = amp * e * math.sin(2 * math.pi * freq * t)
        flick = math.radians(2.5) * e * math.sin(2 * math.pi * ant_freq * t)
        return {"roll": 0.0, "pitch": pitch, "yaw": 0.0,
                "antennas": (_ANT_TALK + flick, _ANT_TALK - flick)}

    return dur, fn


# Registry of all available gesture factories.
_GESTURE_FACTORIES: List[Callable] = [
    _make_gentle_nod,
    _make_head_tilt,
    _make_thoughtful,
    _make_antenna_dance,
    _make_side_sway,
    _make_quick_nods,
]


class TalkingAnimation:
    """Natural speaking overlay that cycles through random conversational
    gestures (nod, tilt, sway, …) so the robot looks alive without
    repeating a single mechanical loop.

    Each gesture runs for a few seconds with a smooth fade-in / fade-out
    envelope, then a new random gesture is selected.  Because every
    gesture starts and ends at the neutral pose, switching is seamless.

    The public API (``offsets(now)``) is unchanged from the previous
    single-loop version, so ``robot_control.py`` needs no modifications.
    """

    def __init__(self) -> None:
        self._gesture_start = time.time()
        self._dur: float = 0.0
        self._fn: Optional[Callable[[float], dict]] = None
        self._pick_new(self._gesture_start)

    def _pick_new(self, now: float) -> None:
        self._gesture_start = now
        self._dur, self._fn = random.choice(_GESTURE_FACTORIES)()

    def offsets(self, now: Optional[float] = None) -> dict:
        now = now if now is not None else time.time()
        t = now - self._gesture_start
        if t >= self._dur:
            self._pick_new(now)
            t = 0.0
        return self._fn(t)


def blend_offsets(a: dict, b: dict, alpha: float) -> dict:
    """Crossfade between two animations so transitions don't snap.

    ``alpha == 0`` returns ``a``, ``alpha == 1`` returns ``b``.
    """
    inv = 1.0 - alpha
    ar, al = a["antennas"]
    br, bl = b["antennas"]
    return {
        "roll":     inv * a["roll"]  + alpha * b["roll"],
        "pitch":    inv * a["pitch"] + alpha * b["pitch"],
        "yaw":      inv * a["yaw"]   + alpha * b["yaw"],
        "antennas": (inv * ar + alpha * br, inv * al + alpha * bl),
    }
