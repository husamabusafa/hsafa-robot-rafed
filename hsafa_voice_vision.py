"""hsafa_voice_vision.py — Minimal camera + robot controller.

Exports:
    Camera          — OpenCV camera wrapper
    RobotController — Thin wrapper around ReachyMini for head + emotion control
"""
from __future__ import annotations

import asyncio
import base64
import logging
import math
import random
import threading
import time
from typing import Callable, List, Optional, Tuple

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
# Speaking gesture factories
# ---------------------------------------------------------------------------
# Each factory returns (duration_s, offsets_fn) where offsets_fn(t, amp)
# returns (z_mm, pitch_deg, yaw_deg, roll_deg, ant_r, ant_l).
#
# Amplitudes are strong and slow (user-approved from live robot testing).
# amp scales motion with audio volume (floor 0.5 so it's always visible).
# A half-sine envelope fades each gesture in/out so switching never snaps.

def _env(t: float, dur: float) -> float:
    """Half-sine envelope: 0 -> 1 -> 0 over [0, dur]."""
    return math.sin(math.pi * t / dur)


def _make_gentle_bob() -> Tuple[float, Callable]:
    dur = random.uniform(3.0, 5.0)
    freq = random.uniform(1.2, 1.8)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        phase = 2 * math.pi * t * freq
        z = amp * 5.0 * math.sin(phase)
        pitch = amp * 3.5 * math.sin(phase + 0.4)
        roll = amp * 1.5 * math.sin(2 * math.pi * t / 11.0)
        ap = 2 * math.pi * t * 1.2
        ant_r = (0.10 + 0.35 * amp) * math.sin(ap)
        ant_l = (0.10 + 0.35 * amp) * math.sin(ap + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_nodding() -> Tuple[float, Callable]:
    dur = random.uniform(3.0, 5.0)
    freq = random.uniform(0.6, 0.9)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        pitch = amp * 6.0 * e * math.sin(2 * math.pi * freq * t)
        z = amp * 3.0 * e * math.sin(2 * math.pi * freq * t)
        roll = amp * 1.0 * math.sin(2 * math.pi * t / 10.0)
        ant_r = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.9 * t)
        ant_l = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.9 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_head_tilt() -> Tuple[float, Callable]:
    dur = random.uniform(3.5, 5.5)
    side = random.choice((-1.0, 1.0))

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        roll = side * amp * 7.0 * e
        z = amp * 2.5 * math.sin(2 * math.pi * t * 1.2)
        pitch = amp * 1.5 * math.sin(2 * math.pi * t * 1.2 + 0.4)
        ant_r = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.8 * t)
        ant_l = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.8 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_side_sway() -> Tuple[float, Callable]:
    dur = random.uniform(3.5, 5.5)
    freq = random.uniform(0.20, 0.30)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        yaw = amp * 8.0 * e * math.sin(2 * math.pi * freq * t)
        z = amp * 3.0 * math.sin(2 * math.pi * t * 1.5)
        roll = amp * 1.2 * math.sin(2 * math.pi * t / 9.0)
        ant_r = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.8 * t)
        ant_l = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.8 * t + math.pi * 0.7)
        return z, 0.0, yaw, roll, ant_r, ant_l

    return dur, fn


def _make_thoughtful() -> Tuple[float, Callable]:
    dur = random.uniform(3.0, 5.0)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        pitch = -amp * 4.0 * e
        z = amp * 2.0 * math.sin(2 * math.pi * t * 0.8)
        roll = amp * 1.0 * math.sin(2 * math.pi * t / 12.0)
        ant_r = (0.10 + 0.20 * amp) * e * math.sin(2 * math.pi * 0.5 * t)
        ant_l = (0.10 + 0.20 * amp) * e * math.sin(2 * math.pi * 0.5 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_quick_nods() -> Tuple[float, Callable]:
    dur = random.uniform(2.5, 4.0)
    freq = random.uniform(0.8, 1.2)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        pitch = amp * 5.0 * e * math.sin(2 * math.pi * freq * t)
        z = amp * 3.0 * e * math.sin(2 * math.pi * freq * t)
        roll = amp * 1.5 * e * math.sin(2 * math.pi * t / 7.0)
        ant_r = (0.10 + 0.40 * amp) * e * math.sin(2 * math.pi * 1.2 * t)
        ant_l = (0.10 + 0.40 * amp) * e * math.sin(2 * math.pi * 1.2 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_bob_and_sway() -> Tuple[float, Callable]:
    dur = random.uniform(3.5, 5.5)
    freq = random.uniform(1.2, 1.8)
    sway_freq = random.uniform(0.18, 0.25)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        phase = 2 * math.pi * t * freq
        z = amp * 5.0 * e * math.sin(phase)
        pitch = amp * 3.0 * e * math.sin(phase + 0.4)
        yaw = amp * 6.0 * e * math.sin(2 * math.pi * sway_freq * t)
        roll = amp * 1.5 * e * math.sin(2 * math.pi * t / 9.0)
        ap = 2 * math.pi * t * 1.2
        ant_r = (0.10 + 0.35 * amp) * e * math.sin(ap)
        ant_l = (0.10 + 0.35 * amp) * e * math.sin(ap + math.pi * 0.7)
        return z, pitch, yaw, roll, ant_r, ant_l

    return dur, fn


def _make_wobble() -> Tuple[float, Callable]:
    dur = random.uniform(3.0, 5.0)
    freq = random.uniform(0.5, 0.7)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        roll = amp * 7.0 * e * math.sin(2 * math.pi * freq * t)
        z = amp * 3.5 * math.sin(2 * math.pi * t * 1.5)
        pitch = amp * 2.0 * math.sin(2 * math.pi * t * 1.5 + 0.4)
        ant_r = (0.10 + 0.40 * amp) * e * math.sin(2 * math.pi * 0.9 * t)
        ant_l = (0.10 + 0.40 * amp) * e * math.sin(2 * math.pi * 0.9 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_big_tilt() -> Tuple[float, Callable]:
    """Extra: big slow tilt to one side and hold — emotional leaning."""
    dur = random.uniform(3.0, 4.5)
    side = random.choice((-1.0, 1.0))
    amp_roll = random.uniform(7.0, 10.0)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        roll = side * amp * amp_roll * e
        z = amp * 2.0 * math.sin(2 * math.pi * t * 1.0)
        pitch = amp * 1.0 * math.sin(2 * math.pi * t * 1.0 + 0.4)
        ant_r = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.7 * t)
        ant_l = (0.10 + 0.30 * amp) * e * math.sin(2 * math.pi * 0.7 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


def _make_tilt_and_nod() -> Tuple[float, Callable]:
    """Extra: combined tilt + nod — expressive and characterful."""
    dur = random.uniform(3.5, 5.0)
    side = random.choice((-1.0, 1.0))
    tilt_freq = random.uniform(0.4, 0.6)
    nod_freq = random.uniform(0.8, 1.2)

    def fn(t: float, amp: float) -> tuple:
        e = _env(t, dur)
        roll = side * amp * 5.0 * e * math.sin(2 * math.pi * tilt_freq * t)
        pitch = amp * 3.0 * e * math.sin(2 * math.pi * nod_freq * t)
        z = amp * 2.0 * math.sin(2 * math.pi * t * 1.0)
        ant_r = (0.10 + 0.35 * amp) * e * math.sin(2 * math.pi * 0.9 * t)
        ant_l = (0.10 + 0.35 * amp) * e * math.sin(2 * math.pi * 0.9 * t + math.pi * 0.7)
        return z, pitch, 0.0, roll, ant_r, ant_l

    return dur, fn


_SPEAKING_GESTURES: List[Callable] = [
    _make_gentle_bob,
    _make_nodding,
    _make_head_tilt,
    _make_side_sway,
    _make_thoughtful,
    _make_quick_nods,
    _make_bob_and_sway,
    _make_wobble,
    _make_big_tilt,
    _make_tilt_and_nod,
]


# ---------------------------------------------------------------------------
# Idle emotion clips — played randomly when not speaking
# ---------------------------------------------------------------------------
# These are recorded Reachy Mini emotion animations (motion + sound).
# Played every ~7s during idle. show_expression handles smooth transitions
# (initial_goto_duration + _smooth_return_to_tracking).

_IDLE_EMOTIONS = [
    "boredom1", "boredom2", "tired1", "exhausted1", "sleep1",
    "curious1", "attentive1", "attentive2",
    "thoughtful1", "thoughtful2", "inquiring1", "inquiring2",
    "lonely1", "lost1", "downcast1", "resigned1",
    "cheerful1", "enthusiastic1", "enthusiastic2",
    "impatient1", "impatient2", "indifferent1",
    "uncertain1", "shy1", "serenity1", "calming1",
    "understanding1", "understanding2", "helpful1",
    "proud1", "proud2", "relief1",
]

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

    Priority (highest first): expression > speaking > idle
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

    # ---- safe command wrappers ---------------------------------------------
    # These check _expression_active right before sending so the idle loop
    # never fights with a playing expression clip, even if the flag was set
    # mid-cycle (after the top-of-loop check but before the send).
    def _send_head_pose(self, pose) -> None:
        if self._expression_active.is_set():
            return
        self.reachy.set_target_head_pose(pose)

    def _send_antennas(self, positions) -> None:
        if self._expression_active.is_set():
            return
        self.reachy.set_target_antenna_joint_positions(positions)

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

    # ---- face tracking -----------------------------------------------------
    def _track_face(self) -> tuple:
        """Run one tick of face tracking. Updates _track_yaw/_track_pitch
        and returns (face_yaw, face_pitch) in radians, or (None, None)
        if no face is currently detected."""
        face_yaw = None
        face_pitch = None

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

        return face_yaw, face_pitch

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
        """Continuous loop: idle sway or audio-reactive speaking.

        Face tracking runs in both states. Expression clips take full
        priority via _expression_active — the loop just sleeps while
        a clip plays.
        """
        from reachy_mini.utils import create_head_pose

        t0 = time.time()

        # Speaking gesture cycling state
        gesture_start = time.time()
        gesture_dur = 0.0
        gesture_fn: Optional[Callable] = None

        # Idle emotion clip timer — play a random emotion every ~7s
        last_emotion_clip = time.time()
        next_emotion_delay = random.uniform(5.0, 10.0)

        while not self._stop_idle.is_set():
            # Expression has full control — just sleep.
            if self._expression_active.is_set():
                time.sleep(0.05)
                continue

            speaking = (
                self._speaking_event is not None
                and self._speaking_event.is_set()
            )
            if not speaking:
                self._speech_amp *= 0.85
                gesture_dur = 0.0  # force fresh gesture on next speak

            t = time.time() - t0

            # Face tracking — shared between speaking and idle.
            face_yaw_ret, face_pitch_ret = self._track_face()
            has_face = face_yaw_ret is not None

            has_tracker = (
                self._tracker is not None
                and (self._frame_source is not None or self._camera is not None)
            )

            if speaking:
                amp = max(self._speech_amp, 0.50)

                # Gesture cycling: pick a new random gesture when the
                # current one expires. Each gesture fades in/out via a
                # half-sine envelope so switching is seamless.
                now_rt = time.time()
                gt = now_rt - gesture_start
                if gt >= gesture_dur or gesture_fn is None:
                    gesture_start = now_rt
                    gesture_dur, gesture_fn = random.choice(_SPEAKING_GESTURES)()
                    gt = 0.0

                gz, gpitch, gyaw, groll, gant_r, gant_l = gesture_fn(gt, amp)

                if has_tracker:
                    pose = create_head_pose(
                        z=gz,
                        pitch=math.degrees(self._track_pitch) + gpitch,
                        yaw=math.degrees(self._track_yaw) + gyaw,
                        roll=groll,
                        degrees=True,
                        mm=True,
                    )
                else:
                    pose = create_head_pose(
                        z=gz,
                        pitch=gpitch,
                        yaw=gyaw,
                        roll=groll,
                        degrees=True,
                        mm=True,
                    )
                self._send_head_pose(pose)
                self._send_antennas([gant_r, gant_l])
            else:
                # Idle — face tracking + periodic random emotion clips.
                # Only play clips when nobody is talking (robot nor human).
                # _speech_amp is raised by notify_audio when the mic picks
                # up audio; if it's above 0.15, someone is likely speaking.
                now_rt = time.time()
                human_speaking = self._speech_amp > 0.15

                # Reset timer while anyone is speaking so we get a fresh
                # 5-10s quiet window before the next clip.
                if human_speaking:
                    last_emotion_clip = now_rt

                # Play a random emotion clip every 5-10s of silence.
                if not human_speaking and (now_rt - last_emotion_clip) > next_emotion_delay:
                    last_emotion_clip = now_rt
                    next_emotion_delay = random.uniform(5.0, 10.0)
                    emotion = random.choice(_IDLE_EMOTIONS)
                    log.info("[Idle] Emotion clip: %s", emotion)
                    self.show_expression(emotion)
                    # show_expression blocks during clip + smooth return.
                    continue

                # Between emotion clips: simple face tracking + gentle sway.
                if has_tracker:
                    roll = 0.5 * math.sin(2 * math.pi * t / 9.0)
                    pose = create_head_pose(
                        roll=roll,
                        pitch=math.degrees(self._track_pitch),
                        yaw=math.degrees(self._track_yaw),
                        degrees=True,
                        mm=True,
                    )
                    self._send_head_pose(pose)
                    ant_r = 0.12 * math.sin(2 * math.pi * t / 6.5)
                    ant_l = 0.12 * math.sin(2 * math.pi * t / 7.1 + 0.8)
                    self._send_antennas([ant_r, ant_l])
                else:
                    roll = 0.7 * math.sin(2 * math.pi * t / 9.0)
                    drift_yaw = 2.0 * math.sin(2 * math.pi * t / 7.0)
                    pose = create_head_pose(
                        roll=roll,
                        pitch=0,
                        yaw=drift_yaw,
                        degrees=True,
                        mm=True,
                    )
                    self._send_head_pose(pose)
                    ant_r = 0.12 * math.sin(2 * math.pi * t / 6.5)
                    ant_l = 0.12 * math.sin(2 * math.pi * t / 7.1 + 0.8)
                    self._send_antennas([ant_r, ant_l])

            time.sleep(0.02)  # ~50 Hz

    # ---- emotions ----------------------------------------------------------
    def _load_emotions(self):
        if self._emotions is None:
            from reachy_mini.motion.recorded_move import RecordedMoves
            self._emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        return self._emotions

    def show_expression(self, name: str) -> bool:
        """Play a recorded emotion clip (motion + sound) with smooth transitions.

        Pauses the idle/animation loop, smoothly transitions to the clip's
        starting pose, plays the full clip with sound, then smoothly
        transitions back to the face-tracking pose.
        """
        try:
            self._expression_active.set()
            # Give the idle loop one cycle to see the flag and yield so
            # it doesn't send a conflicting head pose mid-expression.
            time.sleep(0.08)

            moves = self._load_emotions()
            move = moves.get(name)
            if move is None:
                self._expression_active.clear()
                log.warning("Expression '%s' not found in library", name)
                return False

            log.info("Playing emotion '%s' (%.2fs) with sound...", name, move.duration)

            # Use asyncio.run to call async_play_move directly instead of
            # the async_to_sync wrapper (asgiref). This avoids potential
            # event-loop conflicts when called from asyncio.to_thread.
            # initial_goto_duration smoothly moves to the clip's start pose.
            asyncio.run(self.reachy.async_play_move(
                move, sound=True, initial_goto_duration=0.3,
            ))

            log.info("Emotion '%s' finished.", name)

            # Smooth transition back to the current tracking pose so the
            # head doesn't snap from the clip's final pose to the tracking
            # pose.
            self._smooth_return_to_tracking()

            self._expression_active.clear()
            return True
        except Exception as e:
            self._expression_active.clear()
            log.warning("Expression '%s' failed: %s", name, e)
            return False

    def _smooth_return_to_tracking(self, duration: float = 0.4) -> None:
        """Smoothly move the head back to the current tracking pose."""
        try:
            self.reachy.goto_target(
                head=head_pose(
                    roll=0.0,
                    pitch=self._track_pitch,
                    yaw=self._track_yaw,
                ),
                duration=duration,
            )
        except Exception:
            pass

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
        time.sleep(0.08)
        self.reachy.goto_target(
            head=head_pose(
                roll=0.0,
                pitch=math.radians(pitch_deg),
                yaw=math.radians(yaw_deg),
            ),
            duration=duration,
        )
        # Smooth transition back to tracking pose
        self._smooth_return_to_tracking()
        self._expression_active.clear()
        log.info("Head moved to yaw=%.1f pitch=%.1f (dur=%.2fs)", yaw_deg, pitch_deg, duration)

    def center_head(self, duration: float = 0.5) -> None:
        self.move_head(0, 0, duration=duration)
