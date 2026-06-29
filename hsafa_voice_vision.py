"""hsafa_voice_vision.py — Minimal camera + robot controller.

Exports:
    Camera          — OpenCV camera wrapper
    RobotController — Thin wrapper around ReachyMini for head + emotion control
"""
from __future__ import annotations

import base64
import logging
import math
import threading
import time
from typing import Callable, List, Optional

import cv2
import numpy as np

from hsafa_robot.robot_control import head_pose

# Face-tracking geometry (mirrors robot_control.py constants)
_HALF_HFOV = math.radians(30.0)
_HALF_VFOV = math.radians(22.5)
_YAW_SIGN = -1.0
_PITCH_SIGN = +1.0
_YAW_LIMIT = math.radians(45)
_PITCH_LIMIT = math.radians(25)
_TRACK_ALPHA = 0.08
_TRACK_DEADZONE = 0.08
_TRACK_LEAD_GAIN = 0.70
_TRACK_COAST_S = 0.5
_TRACK_RECENTER_AFTER_S = 3.0
_TRACK_RECENTER_DECAY = 0.97

log = logging.getLogger("robot_controller")

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
JPEG_QUALITY = 80


class Camera:
    """OpenCV camera wrapper."""

    def __init__(self, index: int = 0, width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT):
        self.index = index
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest: Optional[np.ndarray] = None

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.index, getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY))
        if not self._cap.isOpened():
            self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            log.warning("Could not open camera index %s", self.index)
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        ok, frame = self._cap.read()
        if not ok:
            self._cap.release()
            self._cap = None
            return False
        self._latest = frame
        log.info("Camera opened at %sx%s", self.width, self.height)
        return True

    def grab(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if ok:
            self._latest = frame
        return self._latest

    def get_jpeg(self, quality: int = JPEG_QUALITY, mirror: bool = True) -> Optional[bytes]:
        frame = self.grab()
        if frame is None:
            return None
        if mirror:
            frame = cv2.flip(frame, 1)
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buf.tobytes() if ok else None

    def get_base64_jpeg(self, quality: int = JPEG_QUALITY, mirror: bool = True) -> Optional[str]:
        jpeg = self.get_jpeg(quality, mirror)
        return base64.b64encode(jpeg).decode("ascii") if jpeg else None

    def close(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Robot Controller
# ---------------------------------------------------------------------------
class RobotController:
    """Minimal wrapper around ReachyMini.

    Priority (highest first): expression > speaking > haseef_working > idle
    """

    def __init__(self, reachy, tracker=None, camera=None) -> None:
        self.reachy = reachy
        self._emotions = None  # lazy-loaded RecordedMoves
        # Expression animation lock (highest priority).
        self._expression_active = threading.Event()
        # External speaking signal — bind gemini.is_speaking via
        # bind_speaking_event(). When set, speaking animation runs.
        self._speaking_event: Optional[threading.Event] = None
        self._speech_amp = 0.0
        self._stop_idle = threading.Event()
        self._idle_thread: Optional[threading.Thread] = None
        # Haseef working state — when set, antennas do a radar-sweep
        # rotation to signal the robot is "thinking".
        self._haseef_working = threading.Event()
        self._haseef_working_since: float = 0.0
        # Safety: auto-clear after this many seconds to avoid stuck animation.
        self._haseef_working_timeout_s: float = 120.0
        # Face tracking
        self._tracker = tracker
        self._camera = camera
        # Thread-safe frame source — set this to a callable that returns
        # the latest frame from the capture thread, instead of calling
        # camera.grab() directly (which is NOT thread-safe when the capture
        # thread is also calling it).
        self._frame_source: Optional[Callable[[], Optional[np.ndarray]]] = None
        self._track_yaw = 0.0
        self._track_pitch = 0.0
        self._track_last_seen = 0.0
        self._track_smooth_ex = 0.0
        self._track_smooth_ey = 0.0

    # ---- speaking detection ------------------------------------------------
    def bind_speaking_event(self, event: threading.Event) -> None:
        """Drive the speaking animation directly from a threading.Event.

        Pass ``gemini.is_speaking`` so the animation matches Gemini's
        turn boundaries exactly — no audio-silence timeouts.
        """
        self._speaking_event = event

    def notify_audio(self, samples) -> None:
        """Update the live speech amplitude used to scale motion.

        State (speaking vs idle) is driven by the bound is_speaking
        event — this method only adjusts how *big* the bob is.
        """
        try:
            if samples is not None and len(samples) > 0:
                raw = float(np.abs(samples).mean())
                scaled = min(raw * 20.0, 1.0)
                self._speech_amp = 0.85 * self._speech_amp + 0.15 * scaled
        except Exception as e:
            log.error("notify_audio failed: %s", e)

    # ---- haseef working state ---------------------------------------------
    def set_haseef_working(self, active: bool) -> None:
        """Signal that Haseef is actively working (thinking/processing).

        When active, the idle loop plays a radar-sweep antenna rotation
        so the robot visibly shows it's busy. When cleared, antennas
        return to normal idle/speaking behaviour.
        """
        if active:
            self._haseef_working_since = time.time()
            self._haseef_working.set()
            log.info("[Animation] haseef_working ON")
        else:
            self._haseef_working.clear()
            log.info("[Animation] haseef_working OFF")

    # ---- idle / animation loop ---------------------------------------------
    def start_idle(self) -> None:
        """Start the background animation thread."""
        self._stop_idle.clear()
        self._idle_thread = threading.Thread(target=self._idle_loop_safe, daemon=True, name="idle")
        self._idle_thread.start()
        log.info("Animation loop started.")

    def stop_idle(self) -> None:
        """Stop the background animation thread."""
        self._stop_idle.set()
        if self._idle_thread:
            self._idle_thread.join(timeout=1.0)
        log.info("Animation loop stopped.")

    def _idle_loop_safe(self) -> None:
        """Wrapper that catches exceptions so the thread doesn't die silently."""
        try:
            self._idle_loop()
        except Exception as e:
            log.error("[Animation] idle loop crashed: %s", e, exc_info=True)

    def _idle_loop(self) -> None:
        """Continuous loop: idle sway, audio-reactive speaking, or sleep during expression."""
        import random
        import time

        from reachy_mini.utils import create_head_pose

        t0 = time.time()

        # Idle drift state: smoothly interpolate toward a target yaw that
        # changes every few seconds. No pitch breathing.
        next_drift = 0.0
        yaw_off = 0.0
        target_yaw = 0.0

        # Speaking emphasis state
        next_emphasis = 0.0
        emphasis_yaw = 0.0
        emphasis_decay = 0.0

        while not self._stop_idle.is_set():
            # Expression has full control — just sleep.
            if self._expression_active.is_set():
                time.sleep(0.05)
                continue

            # Safety: auto-clear haseef_working if it's been on too long
            # (protects against a missing run.completed event).
            if self._haseef_working.is_set():
                elapsed = time.time() - self._haseef_working_since
                if elapsed > self._haseef_working_timeout_s:
                    log.warning(
                        "[Animation] haseef_working auto-cleared after %.0fs (no run.completed)",
                        elapsed,
                    )
                    self._haseef_working.clear()

            # Speaking is driven directly by the bound event
            # (gemini.is_speaking). No timers, no jitter.
            # Priority: speaking > haseef_working so the robot looks alive
            # when Gemini talks, even if Haseef is still processing.
            speaking = (
                self._speaking_event is not None
                and self._speaking_event.is_set()
            )
            if not speaking:
                # Bleed amplitude so the next speaking turn starts fresh.
                self._speech_amp *= 0.85
                emphasis_decay = 0.0

            t = time.time() - t0

            # Face tracking state — shared across speaking and idle branches.
            face_yaw = None
            face_pitch = None

            # Haseef working AND not speaking — radar-sweep antennas.
            if self._haseef_working.is_set() and not speaking:
                # Smooth radar sweep: antennas rotate side to side
                sweep = math.sin(2 * math.pi * t * 0.8)
                ant_amp = math.radians(25.0)
                ant_r = ant_amp * sweep
                ant_l = -ant_amp * sweep
                self.reachy.set_target_antenna_joint_positions([ant_r, ant_l])

                pose = create_head_pose(
                    roll=0,
                    pitch=0,
                    yaw=0,
                    degrees=True,
                    mm=True,
                )
                self.reachy.set_target_head_pose(pose)
                time.sleep(0.02)
                continue

            if speaking:
                amp = self._speech_amp
                # Floor: keep a minimum bob so the animation never looks frozen.
                amp = max(amp, 0.20)

                # --- Keep tracking the face even while speaking ---
                # The head stays pointed at the person (track_yaw/track_pitch)
                # and we add a subtle bob on top so it looks alive.
                if self._tracker is not None and (self._frame_source is not None or self._camera is not None):
                    frame = self._frame_source() if self._frame_source is not None else self._camera.grab()
                    if frame is not None:
                        self._tracker.submit(frame)
                    det = self._tracker.get()
                    now_ts = time.time()
                    if det is not None and (now_ts - det.timestamp) < _TRACK_COAST_S:
                        ex = det.err_x
                        ey = det.err_y
                        self._track_smooth_ex += 0.5 * (ex - self._track_smooth_ex)
                        self._track_smooth_ey += 0.5 * (ey - self._track_smooth_ey)
                        sx = self._track_smooth_ex
                        sy = self._track_smooth_ey
                        if abs(sx) > _TRACK_DEADZONE:
                            face_yaw = self._track_yaw + _YAW_SIGN * sx * _HALF_HFOV * _TRACK_LEAD_GAIN
                        if abs(sy) > _TRACK_DEADZONE:
                            face_pitch = self._track_pitch + _PITCH_SIGN * sy * _HALF_VFOV * _TRACK_LEAD_GAIN
                        self._track_last_seen = now_ts

                if face_yaw is not None:
                    face_yaw = max(-_YAW_LIMIT, min(_YAW_LIMIT, face_yaw))
                    self._track_yaw += _TRACK_ALPHA * (face_yaw - self._track_yaw)
                if face_pitch is not None:
                    face_pitch = max(-_PITCH_LIMIT, min(_PITCH_LIMIT, face_pitch))
                    self._track_pitch += _TRACK_ALPHA * (face_pitch - self._track_pitch)

                # Subtle speech bob — added ON TOP of face-tracking yaw/pitch
                phase = 2 * math.pi * t * 2.8
                bob_z = amp * 2.0 * math.sin(phase)
                bob_pitch = amp * 1.2 * math.sin(phase + 0.4)
                drift_roll = 0.6 * math.sin(2 * math.pi * t / 9.0)

                # Occasional small emphasis tilt
                if t > next_emphasis and amp > 0.15:
                    emphasis_yaw = random.uniform(-3.0, 3.0)
                    emphasis_decay = 1.0
                    next_emphasis = t + random.uniform(3.5, 7.0)
                if emphasis_decay > 0.01:
                    emphasis_decay *= 0.96

                if self._tracker is not None and (self._frame_source is not None or self._camera is not None):
                    # Face-tracking + speaking: head follows face, subtle bob
                    pose = create_head_pose(
                        z=bob_z,
                        pitch=math.degrees(self._track_pitch) + bob_pitch,
                        yaw=math.degrees(self._track_yaw) + emphasis_yaw * emphasis_decay,
                        roll=drift_roll,
                        degrees=True,
                        mm=True,
                    )
                else:
                    # No tracker — original speaking animation
                    drift_yaw = 1.5 * math.sin(2 * math.pi * t / 7.0)
                    pose = create_head_pose(
                        z=bob_z,
                        pitch=bob_pitch,
                        yaw=drift_yaw + emphasis_yaw * emphasis_decay,
                        roll=drift_roll,
                        degrees=True,
                        mm=True,
                    )
                self.reachy.set_target_head_pose(pose)

                # Talking antennas: speech-rhythm sway, amplitude follows
                # audio level so quiet speech = small movement, loud = bigger.
                ant_amp = 0.10 + 0.35 * amp  # radians
                ant_phase = 2 * math.pi * t * 2.2
                ant_r = ant_amp * math.sin(ant_phase)
                ant_l = ant_amp * math.sin(ant_phase + math.pi * 0.7)
                self.reachy.set_target_antenna_joint_positions([ant_r, ant_l])
            else:
                # Idle: face tracking if tracker+camera available, else drift.

                if self._tracker is not None and (self._frame_source is not None or self._camera is not None):
                    frame = self._frame_source() if self._frame_source is not None else self._camera.grab()
                    if frame is not None:
                        self._tracker.submit(frame)
                    det = self._tracker.get()
                    now_ts = time.time()
                    if det is not None and (now_ts - det.timestamp) < _TRACK_COAST_S:
                        ex = det.err_x
                        ey = det.err_y
                        self._track_smooth_ex += 0.5 * (ex - self._track_smooth_ex)
                        self._track_smooth_ey += 0.5 * (ey - self._track_smooth_ey)
                        sx = self._track_smooth_ex
                        sy = self._track_smooth_ey
                        if abs(sx) > _TRACK_DEADZONE:
                            face_yaw = self._track_yaw + _YAW_SIGN * sx * _HALF_HFOV * _TRACK_LEAD_GAIN
                        if abs(sy) > _TRACK_DEADZONE:
                            face_pitch = self._track_pitch + _PITCH_SIGN * sy * _HALF_VFOV * _TRACK_LEAD_GAIN
                        self._track_last_seen = now_ts

                if face_yaw is not None:
                    face_yaw = max(-_YAW_LIMIT, min(_YAW_LIMIT, face_yaw))
                    self._track_yaw += _TRACK_ALPHA * (face_yaw - self._track_yaw)
                else:
                    if (time.time() - self._track_last_seen) > _TRACK_RECENTER_AFTER_S:
                        self._track_yaw *= _TRACK_RECENTER_DECAY

                if face_pitch is not None:
                    face_pitch = max(-_PITCH_LIMIT, min(_PITCH_LIMIT, face_pitch))
                    self._track_pitch += _TRACK_ALPHA * (face_pitch - self._track_pitch)
                else:
                    if (time.time() - self._track_last_seen) > _TRACK_RECENTER_AFTER_S:
                        self._track_pitch *= _TRACK_RECENTER_DECAY

                if self._tracker is not None and (self._frame_source is not None or self._camera is not None):
                    # Face-tracking mode: head follows face, antennas breathe
                    roll = 0.5 * math.sin(2 * math.pi * t / 9.0)
                    pose = create_head_pose(
                        roll=roll,
                        pitch=math.degrees(self._track_pitch),
                        yaw=math.degrees(self._track_yaw),
                        degrees=True,
                        mm=True,
                    )
                    self.reachy.set_target_head_pose(pose)
                    ant_r = 0.12 * math.sin(2 * math.pi * t / 6.5)
                    ant_l = 0.12 * math.sin(2 * math.pi * t / 7.1 + 0.8)
                    self.reachy.set_target_antenna_joint_positions([ant_r, ant_l])
                else:
                    # No tracker — original drift behavior
                    if t > next_drift:
                        target_yaw = random.uniform(-2.5, 2.5)
                        next_drift = t + random.uniform(5.0, 9.0)
                    yaw_off += (target_yaw - yaw_off) * 0.015
                    roll = 0.7 * math.sin(2 * math.pi * t / 9.0)
                    pose = create_head_pose(
                        roll=roll,
                        pitch=0,
                        yaw=yaw_off,
                        degrees=True,
                        mm=True,
                    )
                    self.reachy.set_target_head_pose(pose)
                    ant_r = 0.12 * math.sin(2 * math.pi * t / 6.5)
                    ant_l = 0.12 * math.sin(2 * math.pi * t / 7.1 + 0.8)
                    self.reachy.set_target_antenna_joint_positions([ant_r, ant_l])

            time.sleep(0.02)  # ~50 Hz

    # ---- emotions ----------------------------------------------------------
    def _load_emotions(self):
        if self._emotions is None:
            from reachy_mini.motion.recorded_move import RecordedMoves
            self._emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        return self._emotions

    def show_expression(self, name: str) -> bool:
        """Play a recorded emotion clip (motion + sound).

        Pauses the animation loop, plays the clip, then smoothly returns to neutral.
        """
        try:
            from reachy_mini.utils import create_head_pose

            self._expression_active.set()
            moves = self._load_emotions()
            move = moves.get(name)
            self.reachy.play_move(move, initial_goto_duration=0.5, sound=True)
            log.info("Played emotion '%s' (%.2fs)", name, move.duration)

            # Smoothly return to neutral before resuming idle/speaking
            self.reachy.goto_target(
                head=create_head_pose(roll=0, pitch=0, yaw=0, degrees=True, mm=True),
                duration=1.5,
            )
            self._expression_active.clear()
            return True
        except Exception as e:
            self._expression_active.clear()
            log.warning("Expression '%s' failed: %s", name, e)
            return False

    def list_expressions(self) -> List[str]:
        try:
            return self._load_emotions().list_moves()
        except Exception:
            return []

    def cancel_expression(self) -> None:
        self.reachy.cancel_move()

    # ---- head movement -----------------------------------------------------
    def move_head(self, yaw_deg: float, pitch_deg: float, duration: float = 0.3) -> None:
        """Smoothly move the head to a yaw/pitch angle (degrees)."""
        self._expression_active.set()
        self.reachy.goto_target(
            head=head_pose(
                roll=0.0,
                pitch=math.radians(pitch_deg),
                yaw=math.radians(yaw_deg),
            ),
            duration=duration,
        )
        self._expression_active.clear()
        log.info("Head moved to yaw=%.1f pitch=%.1f (dur=%.2fs)", yaw_deg, pitch_deg, duration)

    def center_head(self, duration: float = 0.5) -> None:
        self.move_head(0, 0, duration=duration)
