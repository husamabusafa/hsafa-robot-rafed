"""world_state.py - Single source of truth for what the robot perceives.

Every sense (YOLO tracker, VAD, ...) writes into one shared
:class:`WorldState`. Every brain (Gemini context, Hsafa bridge)
reads from it under a lock.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple


Bbox = Tuple[int, int, int, int]


# ---- Per-person view ------------------------------------------------------

@dataclass
class HumanView:
    """Everything we currently believe about one visible person."""
    track_id: int
    bbox: Bbox
    center_px: Tuple[int, int]

    # Positional class from frame width: "left" / "center" / "right"
    direction: str = "center"

    # Distance proxy, bucketized from bbox area: "near" / "mid" / "far".
    distance_est: str = "mid"

    # Fractional bbox area in [0, 1] (bbox_area / frame_area).
    proximity: float = 0.0

    # Speech state
    is_speaking: bool = False
    speaking_prob: float = 0.0

    # Timestamps (monotonic seconds)
    first_seen: float = 0.0
    last_seen: float = 0.0

    # ---- helpers ----
    def age_s(self, now: Optional[float] = None) -> float:
        now = now if now is not None else time.monotonic()
        return max(0.0, now - self.first_seen)

    def seen_recency_s(self, now: Optional[float] = None) -> float:
        now = now if now is not None else time.monotonic()
        return max(0.0, now - self.last_seen)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "direction": self.direction,
            "distance_est": self.distance_est,
            "is_speaking": self.is_speaking,
            "speaking_prob": round(self.speaking_prob, 3),
            "first_seen_s_ago": round(time.monotonic() - self.first_seen, 2),
        }


# ---- Robot self-view ------------------------------------------------------

@dataclass
class RobotView:
    """What the robot knows about itself."""
    head_yaw_deg: float = 0.0
    head_pitch_deg: float = 0.0
    head_roll_deg: float = 0.0
    body_yaw_deg: float = 0.0
    is_speaking: bool = False
    current_target_track_id: Optional[int] = None
    gaze_mode: str = "normal"
    gaze_state: str = "idle"


# ---- Environment (reserved) -----------------------------------------------

@dataclass
class EnvView:
    """Room-level signals."""
    audio_speech_active: bool = False
    doa_azimuth_deg: Optional[float] = None
    noise_level: float = 0.0
    lighting: str = "normal"


# ---- The whole state ------------------------------------------------------

@dataclass
class WorldState:
    """One snapshot of what the robot perceives, owned by one holder."""
    humans: List[HumanView] = field(default_factory=list)
    objects: List[Dict[str, Any]] = field(default_factory=list)
    robot: RobotView = field(default_factory=RobotView)
    env: EnvView = field(default_factory=EnvView)
    last_update: float = 0.0

    # ---- helpers ----
    def find_by_track(self, track_id: int) -> Optional[HumanView]:
        for h in self.humans:
            if h.track_id == track_id:
                return h
        return None

    def active_speaker(self) -> Optional[HumanView]:
        best: Optional[HumanView] = None
        best_p = 0.0
        for h in self.humans:
            if h.is_speaking and h.speaking_prob > best_p:
                best_p = h.speaking_prob
                best = h
        if best is not None:
            return best
        for h in self.humans:
            if h.speaking_prob > best_p:
                best_p = h.speaking_prob
                best = h
        return best

    def brief_text(self) -> str:
        """Compact one-line summary suitable for Gemini context injection."""
        if not self.humans:
            crowd = "nobody"
        else:
            parts = []
            for h in self.humans:
                bits = [h.direction]
                if h.is_speaking:
                    bits.append("speaking")
                parts.append(" ".join(bits))
            crowd = ", ".join(parts)
        tgt = (
            f"#{self.robot.current_target_track_id}"
            if self.robot.current_target_track_id is not None else "(none)"
        )
        return (
            f"humans: {crowd}; target: {tgt}; "
            f"state: {self.robot.gaze_state}; mode: {self.robot.gaze_mode}"
        )


# ---- Thread-safe holder ---------------------------------------------------

class WorldStateHolder:
    """Thread-safe container for the single :class:`WorldState` instance."""

    def __init__(self, initial: Optional[WorldState] = None) -> None:
        self._lock = threading.RLock()
        self._state = initial or WorldState()

    def snapshot(self) -> WorldState:
        with self._lock:
            s = self._state
            return WorldState(
                humans=[replace(h) for h in s.humans],
                objects=list(s.objects),
                robot=replace(s.robot),
                env=replace(s.env),
                last_update=s.last_update,
            )

    def update(self, mutator):
        with self._lock:
            mutator(self._state)
            self._state.last_update = time.monotonic()

    # ---- targeted writers ---
    def replace_humans(self, humans: List[HumanView]) -> None:
        with self._lock:
            self._state.humans = list(humans)
            self._state.last_update = time.monotonic()

    def set_human_speech(
        self,
        track_id: int,
        *,
        is_speaking: bool,
        speaking_prob: float,
    ) -> None:
        with self._lock:
            for h in self._state.humans:
                if h.track_id == track_id:
                    h.is_speaking = bool(is_speaking)
                    h.speaking_prob = float(speaking_prob)
                    break

    def set_audio_speech_active(self, active: bool) -> None:
        with self._lock:
            self._state.env.audio_speech_active = bool(active)
            self._state.last_update = time.monotonic()

    def set_robot_target(
        self,
        track_id: Optional[int],
        *,
        gaze_mode: Optional[str] = None,
        gaze_state: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._state.robot.current_target_track_id = track_id
            if gaze_mode is not None:
                self._state.robot.gaze_mode = gaze_mode
            if gaze_state is not None:
                self._state.robot.gaze_state = gaze_state
            self._state.last_update = time.monotonic()

    def set_robot_pose(
        self,
        *,
        head_yaw_deg: float,
        head_pitch_deg: float,
        head_roll_deg: float,
        body_yaw_deg: float,
        is_speaking: bool,
    ) -> None:
        with self._lock:
            r = self._state.robot
            r.head_yaw_deg = float(head_yaw_deg)
            r.head_pitch_deg = float(head_pitch_deg)
            r.head_roll_deg = float(head_roll_deg)
            r.body_yaw_deg = float(body_yaw_deg)
            r.is_speaking = bool(is_speaking)
            self._state.last_update = time.monotonic()
