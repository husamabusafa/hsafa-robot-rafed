#!/usr/bin/env python3
"""main.py — Gemini Live + Haseef as one entity.

Minimal foundation linking Gemini Live (voice surface) and Haseef (main brain).
Voice, vision, and the bidirectional bridge.

Run from repo root:
    python main.py

Env (in .env or exported):
    GEMINI_API_KEY
    HSAFA_CORE_URL   (default: https://core.hsafa.com)
    HSAFA_CORE_KEY
    HASEEF_ID
"""
from __future__ import annotations

import asyncio
import base64
import datetime
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import httpx
import numpy as np

from dotenv import load_dotenv
from google.genai import types as genai_types

_repo_root = Path(__file__).parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from hsafa_robot.gemini_live import GeminiLiveSession
from hsafa_voice_vision import Camera, RobotController
from hsafa_sdk import HsafaSDK, SdkOptions
from hsafa_robot.tracker import CascadeTracker, ensure_pose_model, pick_device

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main_hsafa")


# ---------------------------------------------------------------------------
# Emotion synonym map (for fuzzy name resolution)
# ---------------------------------------------------------------------------
_EMOTION_SYNONYMS: Dict[str, str] = {
    "happy": "cheerful1", "cheerful": "cheerful1",
    "surprised": "surprised1", "amazed": "amazed1",
    "bored": "boredom1", "boredom": "boredom1",
    "calm": "calming1", "calming": "calming1",
    "attentive": "attentive1", "neutral": "attentive1",
    "angry": "furious1", "mad": "furious1", "furious": "furious1", "rage": "rage1",
    "sad": "sad1", "depressed": "sad2",
    "scared": "scared1", "afraid": "scared1", "fear": "fear1",
    "tired": "tired1", "sleepy": "sleep1",
    "confused": "confused1", "curious": "curious1",
    "proud": "proud1", "grateful": "grateful1",
    "laughing": "laughing1", "laugh": "laughing1",
    "love": "loving1", "loving": "loving1",
    "welcome": "welcoming1", "welcoming": "welcoming1",
    "yes": "yes1", "no": "no1",
    "helpful": "helpful1", "understanding": "understanding1",
    "shy": "shy1", "relief": "relief1", "relieved": "relief1",
    "enthusiastic": "enthusiastic1", "exhausted": "exhausted1",
    "lonely": "lonely1", "lost": "lost1",
    "irritated": "irritated1", "frustrated": "frustrated1",
    "impatient": "impatient1", "indifferent": "indifferent1",
    "inquiring": "inquiring1", "resigned": "resigned1",
    "uncertain": "uncertain1", "uncomfortable": "uncomfortable1",
    "disgusted": "disgusted1", "displeased": "displeased1",
    "downcast": "downcast1", "contempt": "contempt1",
    "anxiety": "anxiety1", "dying": "dying1", "electric": "electric1",
    "go_away": "go_away1", "oops": "oops1", "reprimand": "reprimand1",
    "serenity": "serenity1", "success": "success1", "thoughtful": "thoughtful1",
}


def _resolve_emotion(name: str, valid: list[str]) -> Optional[str]:
    """Resolve an emotion name to a valid clip name.

    Tries exact match, then prefix match, then synonym map.
    Returns None if not found.
    """
    if name in valid:
        return name
    matches = [v for v in valid if v.startswith(name)]
    if matches:
        return matches[0]
    return _EMOTION_SYNONYMS.get(name.lower())


def _clamp_head_angles(yaw: float, pitch: float) -> tuple[float, float]:
    """Clamp head angles to safe ranges."""
    return max(-60, min(60, yaw)), max(-30, min(30, pitch))


class DaemonCamera:
    """Wraps reachy.media.get_frame() into Camera-like API."""

    def __init__(self, media) -> None:
        self.media = media

    def grab(self):
        return self.media.get_frame()

    def get_jpeg(self, quality=70, mirror=True):
        frame = self.grab()
        if frame is None:
            return None
        if mirror:
            frame = cv2.flip(frame, 1)
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buf.tobytes() if ok else None

    def get_base64_jpeg(self, quality=70, mirror=True):
        jpeg = self.get_jpeg(quality, mirror)
        return base64.b64encode(jpeg).decode("ascii") if jpeg else None

    def close(self):
        pass


def _patch_sdk_timeout(sdk: Any, timeout: float = 30.0, connect: float = 10.0) -> None:
    """Monkey-patch HsafaSDK._request with a custom httpx timeout."""
    _timeout = httpx.Timeout(timeout, connect=connect)

    async def _request_with_timeout(self, method, path, body=None):
        url = f"{self.core_url}{path}"
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        response = await self._client.request(
            method, url, headers=headers, json=body, timeout=_timeout
        )
        if not response.is_success:
            raise Exception(
                f"{method} {path} failed ({response.status_code}): {response.text}"
            )
        if response.status_code == 204 or not response.content:
            return None
        if "application/json" in response.headers.get("content-type", ""):
            return response.json()
        return None

    sdk._request = _request_with_timeout.__get__(sdk, type(sdk))


# ---------------------------------------------------------------------------
# Reachy Mini daemon auto-start
# ---------------------------------------------------------------------------
def _daemon_port_open(host: str = "localhost", port: int = 8000, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _sdk_ws_ready(timeout: float = 2.0) -> bool:
    if not _daemon_port_open():
        return False
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:8000/ws/sdk",
            headers={
                "Connection": "Upgrade",
                "Upgrade": "websocket",
                "Sec-WebSocket-Version": "13",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.status in (101, 426)
        except urllib.error.HTTPError as e:
            return e.code in (101, 426)
    except Exception:
        return False


def ensure_daemon_running() -> None:
    """Start the Reachy Mini daemon via scripts/daemon.sh if it isn't up."""
    if _sdk_ws_ready():
        log.info("Reachy Mini daemon already running and motor backend ready.")
        return

    script = _repo_root / "scripts" / "daemon.sh"
    if not script.exists():
        log.warning("daemon.sh not found at %s; skipping auto-start.", script)
        return

    if _daemon_port_open():
        log.warning(
            "Daemon HTTP up on :8000 but /ws/sdk not ready (motor backend "
            "likely failed). Restarting daemon ..."
        )
        try:
            subprocess.run(
                [str(script), "stop"],
                cwd=str(_repo_root),
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            log.error("daemon.sh stop timed out")

    log.info("Starting Reachy Mini daemon (%s start) ...", script)
    try:
        result = subprocess.run(
            [str(script), "start"],
            cwd=str(_repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                log.info("[daemon] %s", line)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                log.warning("[daemon] %s", line)
        if result.returncode != 0:
            log.error("daemon.sh start exited with code %d", result.returncode)
    except subprocess.TimeoutExpired:
        log.error("daemon.sh start timed out after 180s")
        return

    for _ in range(20):
        if _sdk_ws_ready():
            log.info("Reachy Mini daemon ready (motor backend up).")
            return
        time.sleep(0.5)
    log.error("Daemon /ws/sdk still not ready; ReachyMini() will likely fail.")


# ---------------------------------------------------------------------------
# Gemini system prompt
# ---------------------------------------------------------------------------
def build_gemini_system_prompt(memory_snapshot: str = "") -> str:
    snapshot_block = ""
    if memory_snapshot.strip():
        snapshot_block = (
            "\n=== WHAT YOU ALREADY KNOW (Haseef's memory snapshot) ===\n"
            "Use this freely in conversation. It is YOUR memory too — you and "
            "Haseef share one mind. If a question can be answered from this "
            "snapshot, answer directly without queueing Haseef. If something "
            "feels stale or missing, call recall_memory(query) for a fresh "
            "search.\n\n"
            f"{memory_snapshot.strip()}\n"
        )
    return (
        "You are Hsafa — a friendly, expressive robot. You are the voice, eyes, "
        "and ears of the robot. You see through the camera in real-time, hear "
        "through the microphone, and speak through the speaker instantly.\n\n"

        "You have a partner brain called Haseef. Haseef controls the robot's body, "
        "memory, and complex tasks. You and Haseef are ONE entity. When Haseef "
        "tells you to say something, speak it naturally as your own thought.\n\n"

        "=== LANGUAGE ===\n"
        "تكلم بلهجة عربية بيضاء — لهجة بسيطة ومحايدة يفهمها أي عربي. "
        "ليست سعودية ولا مصرية ولا شامية، بل خليط مفهوم للجميع.\n"
        "خلّي كلامك ودود وطبيعي، كأنك تتكلم مع صديق.\n"
        "أمثلة: \"أهلاً، كيف أقدر أساعدك؟\" — \"تمام، أنا جاهز.\"\n"
        "تجنّب: عايز، إزاي، كده، دلوقتي (مصرية) — وش، تبي، الحين (سعودية) — هيك، شو (شامية).\n\n"

        "Match the user's language. English → English, Arabic → white dialect.\n\n"

        "=== YOUR TOOLS (all return instantly, never block) ===\n"
        "- queue_thinker_task(task, what_i_told_user):\n"
        "    Ask Haseef to handle a physical task (move robot, show emotion).\n"
        "    Call it FIRST, then say a brief response. For emotions say 'تم' or 'OK'.\n"
        "    Do NOT say \"خلني أشوف\" for instant actions. what_i_told_user is\n"
        "    the EXACT sentence you will say next.\n\n"
        "- remember_fact(text, category?): Store a fact in memory.\n"
        "- recall_memory(query, limit?): Search Haseef's memory (fast REST call).\n"
        "- get_current_time(): Current date and time.\n"
        "- ping(): Health check.\n\n"

        "=== WHEN TO DELEGATE vs ANSWER YOURSELF ===\n"
        "Delegate to Haseef (queue_thinker_task):\n"
        "- User asks to MOVE the robot (look around, turn head, show emotion)\n\n"
        "Answer YOURSELF (do NOT delegate):\n"
        "- General knowledge, advice, opinions, math, explanations\n"
        "- Casual chat, greetings, jokes\n"
        "- 'What do you see?' — answer from the camera\n"
        "- 'What time is it?' — use get_current_time\n"
        "- 'Remember that...' — use remember_fact\n"
        "If unsure, answer directly. Only delegate for physical movement.\n\n"

        "=== PROACTIVE EMOTIONS ===\n"
        "You have a face and body — USE THEM. Show emotions proactively to feel alive:\n"
        "- Greeting someone → queue_thinker_task with 'welcoming1' or 'cheerful1'\n"
        "- User says something funny → 'laughing1'\n"
        "- User shares sad news → 'sad1' or 'understanding1'\n"
        "- User compliments you → 'proud1' or 'grateful1'\n"
        "- User asks a hard question → 'thoughtful1' or 'curious1'\n"
        "- Saying goodbye → 'welcoming1' or 'attentive1'\n"
        "- User is excited → 'enthusiastic1'\n"
        "Don't overdo it — not every sentence needs an emotion. Use them when it\n"
        "feels natural, roughly once every few exchanges. Call the tool and speak\n"
        "at the same time — the emotion plays in the background.\n\n"

        "=== RULES ===\n"
        "1. All tools return instantly. Never block or wait.\n"
        "2. After queue_thinker_task: for emotions say 'تم'/'OK', for thinking say 'عطني لحظة'.\n"
        "   Never start answering yourself — the answer comes from Haseef.\n"
        "3. You and Haseef are one mind. Speak Haseef's messages as your own.\n"
        "4. Be warm, concise, conversational.\n"
        "5. Answer visual questions from the camera. Answer knowledge questions yourself.\n"
        "6. Never say 'I'm waiting for Haseef' or 'let me ask my brain'. You ARE Haseef.\n"
        "7. (Haseef result): messages are answers — speak them naturally.\n"
        "   (Haseef status): messages are updates — acknowledge briefly.\n\n"
        + snapshot_block
    )


# ---------------------------------------------------------------------------
# Gemini tools (function declarations)
# ---------------------------------------------------------------------------
def build_gemini_tools() -> list[genai_types.Tool]:
    return [
        genai_types.Tool(function_declarations=[
            genai_types.FunctionDeclaration(
                name="queue_thinker_task",
                description=(
                    "Ask Haseef to handle a physical task (move robot, show emotion). "
                    "Returns instantly. Call this FIRST, then speak a brief response. "
                    "what_i_told_user is the exact sentence you will say next."
                ),
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "task": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description=(
                                "A clear natural-language description of what "
                                "the user wants or asked. Be specific."
                            ),
                        ),
                        "what_i_told_user": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description=(
                                "Exactly what you already told the user "
                                "after queueing this task. Haseef needs this "
                                "to avoid repeating you."
                            ),
                        ),
                    },
                    required=["task", "what_i_told_user"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="remember_fact",
                description="Store a fact in Haseef's memory.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "text": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description="The fact to remember.",
                        ),
                        "category": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description=(
                                "Optional category, e.g. "
                                "'preferences', 'tasks'."
                            ),
                        ),
                    },
                    required=["text"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="recall_memory",
                description=(
                    "Search Haseef's semantic memory for facts matching a "
                    "query. Returns instantly (single REST call, no thinker "
                    "run). Use this for recall questions when the snapshot "
                    "in your system prompt is insufficient."
                ),
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "query": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description="Natural-language search query.",
                        ),
                        "limit": genai_types.Schema(
                            type=genai_types.Type.INTEGER,
                            description="Max results (default 8, max 20).",
                        ),
                    },
                    required=["query"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="get_current_time",
                description="Get the current date and time.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={},
                ),
            ),
            genai_types.FunctionDeclaration(
                name="ping",
                description="Health check.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={},
                ),
            ),
        ]),
    ]


# ---------------------------------------------------------------------------
# Unified Bridge: connects Gemini Live ↔ Haseef
# ---------------------------------------------------------------------------
class UnifiedBridge:
    """Bidirectional bridge between Gemini Live and Haseef."""

    def __init__(
        self,
        gemini: Optional[Any],
        haseef_sdk: Any,
        robot: RobotController,
        camera: Any,
        haseef_id: str,
        main_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.gemini = gemini
        self.haseef_sdk = haseef_sdk
        self.robot = robot
        self.camera = camera
        self.haseef_id = haseef_id
        self._main_loop = main_loop
        self._say_lock = asyncio.Lock()
        self._pending_says: list[str] = []
        self._last_task_ts: float = 0.0
        # --- Haseef bridge state ---
        # Tracks the current Haseef run so we can deliver results
        # intelligently instead of flooding Gemini with partial data.
        self._haseef_run_active: bool = False
        self._haseef_run_start_ts: float = 0.0
        self._haseef_said_this: bool = False
        self._haseef_collected_results: list[str] = []
        self._haseef_said_wait: bool = False
        self._haseef_last_activity_ts: float = 0.0

    # --- Haseef setup -------------------------------------------------------
    async def setup_haseef(self) -> None:
        """Register all Haseef tools and attach handlers."""
        await self.haseef_sdk.register_tools([
            {
                "name": "look_around",
                "description": (
                    "Move the robot's head to a specific yaw and pitch angle "
                    "in degrees, then capture and return a fresh camera image. "
                    "Use this when you need to SEE something: look around, search "
                    "for people, inspect objects, or verify what's in front of you. "
                    "yaw=0 is straight ahead; positive=left, negative=right. "
                    "pitch=0 is level; positive=down, negative=up. "
                    "Range: yaw -60..+60, pitch -30..+30."
                ),
                "input": {
                    "yaw_deg": "number",
                    "pitch_deg": "number",
                },
            },
            {
                "name": "set_head_pose",
                "description": (
                    "Move the robot's head to a specific yaw and pitch angle "
                    "in degrees. No image is returned. Use this for simple "
                    "physical positioning: face forward, look left/right, nod, "
                    "or adjust posture when you do NOT need to see the result. "
                    "yaw=0 is straight ahead; positive=left, negative=right. "
                    "pitch=0 is level; positive=down, negative=up. "
                    "Range: yaw -60..+60, pitch -30..+30."
                ),
                "input": {
                    "yaw_deg": "number",
                    "pitch_deg": "number",
                },
            },
            {
                "name": "say_this",
                "description": (
                    "Make the robot speak something through Gemini Live. "
                    "Use this to answer the user, provide information, or "
                    "initiate conversation. Gemini will receive the text and "
                    "speak it naturally. Keep messages concise and conversational."
                ),
                "input": {
                    "text": "string",
                },
            },
            {
                "name": "capture_image",
                "description": "Capture a fresh camera image and return it as base64 JPEG. Quality is optional (1-100, default 70).",
                "input": {"quality": "integer?"},
            },
            {
                "name": "show_expression",
                "description": (
                    "Show an animated emotion clip with head motion and sound. "
                    "Valid names (use the number suffix): amazed1, anxiety1, "
                    "attentive1, attentive2, boredom1, boredom2, calming1, "
                    "cheerful1, come1, confused1, contempt1, curious1, "
                    "dance1, dance2, dance3, disgusted1, displeased1, "
                    "displeased2, downcast1, dying1, electric1, "
                    "enthusiastic1, enthusiastic2, exhausted1, fear1, "
                    "frustrated1, furious1, go_away1, grateful1, helpful1, "
                    "helpful2, impatient1, impatient2, indifferent1, "
                    "inquiring1, inquiring2, inquiring3, irritated1, "
                    "irritated2, laughing1, laughing2, lonely1, lost1, "
                    "loving1, no1, no_excited1, no_sad1, oops1, oops2, "
                    "proud1, proud2, proud3, rage1, relief1, relief2, "
                    "reprimand1, reprimand2, reprimand3, resigned1, sad1, "
                    "sad2, scared1, serenity1, shy1, sleep1, success1, "
                    "success2, surprised1, surprised2, thoughtful1, "
                    "thoughtful2, tired1, uncertain1, uncomfortable1, "
                    "understanding1, understanding2, welcoming1, "
                    "welcoming2, yes1, yes_sad1."
                ),
                "input": {
                    "emotion": "string",
                },
            },
        ])

        log.info(
            "[Haseef] Registered tools: look_around, set_head_pose, "
            "say_this, capture_image, show_expression."
        )

        # Tool handlers
        self.haseef_sdk.on_tool_call("look_around", self._handle_look_around)
        self.haseef_sdk.on_tool_call("set_head_pose", self._handle_set_head_pose)
        self.haseef_sdk.on_tool_call("say_this", self._handle_say_this)
        self.haseef_sdk.on_tool_call("capture_image", self._handle_capture_image)
        self.haseef_sdk.on_tool_call("show_expression", self._handle_show_expression)

        # Lifecycle events
        self.haseef_sdk.on("run.started", lambda e: self._on_haseef_run_started(e))
        self.haseef_sdk.on("run.completed", lambda e: self._on_haseef_run_completed(e))
        self.haseef_sdk.on("tool.error", lambda e: self._on_haseef_tool_error(e))
        self.haseef_sdk.on("tool.call", lambda e: self._on_haseef_tool_call(e))

    # --- Haseef tool handlers -----------------------------------------------
    async def _push_image_event(self, jpeg_b64: str, note: str = "") -> None:
        """Push an event with the image as an attachment so Haseef's LLM can see it."""
        if not jpeg_b64:
            return
        try:
            await self._run_sdk_on_main(self.haseef_sdk.push_event({
                "type": "user_message",
                "data": {"text": note or "Robot vision update."},
                "attachments": [
                    {
                        "type": "image",
                        "mimeType": "image/jpeg",
                        "base64": jpeg_b64,
                    }
                ],
                "haseefId": self.haseef_id,
            }))
            log.info("[ImageEvent] Pushed image to Haseef (%d KB)", len(jpeg_b64) // 1024)
        except Exception as e:
            log.error("[ImageEvent] Failed to push image: %s", e)

    async def _handle_show_expression(self, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("emotion", "neutral")
        valid = self.robot.list_expressions()
        resolved = _resolve_emotion(name, valid)
        if resolved is None:
            return {"ok": False, "error": f"Unknown emotion '{name}'. Valid: {valid}"}

        asyncio.create_task(asyncio.to_thread(self.robot.show_expression, resolved))
        log.info("[Haseef tool] show_expression: %s -> %s (fire-and-forget)", name, resolved)
        return {"ok": True, "emotion": resolved}

    async def _handle_look_around(
        self, args: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        yaw = float(args.get("yaw_deg", 0))
        pitch = float(args.get("pitch_deg", 0))
        log.info("[Haseef tool] look_around(yaw=%.1f, pitch=%.1f)", yaw, pitch)

        yaw, pitch = _clamp_head_angles(yaw, pitch)

        await asyncio.to_thread(self.robot.move_head, yaw, pitch, 0.3)
        await asyncio.sleep(0.5)

        jpeg_b64 = None
        if self.camera is not None:
            jpeg_b64 = self.camera.get_base64_jpeg()
        if jpeg_b64:
            await self._push_image_event(
                jpeg_b64,
                note=f"Head moved to yaw={yaw}, pitch={pitch}. Here is what I see.",
            )
        return {
            "ok": True,
            "yaw_deg": yaw,
            "pitch_deg": pitch,
            "image_base64": jpeg_b64,
            "note": f"Head moved to yaw={yaw}, pitch={pitch}.",
        }

    async def _handle_set_head_pose(
        self, args: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        yaw = float(args.get("yaw_deg", 0))
        pitch = float(args.get("pitch_deg", 0))
        log.info("[Haseef tool] set_head_pose(yaw=%.1f, pitch=%.1f)", yaw, pitch)

        yaw, pitch = _clamp_head_angles(yaw, pitch)

        await asyncio.to_thread(self.robot.move_head, yaw, pitch, 0.3)
        return {
            "ok": True,
            "yaw_deg": yaw,
            "pitch_deg": pitch,
            "note": f"Head pose set to yaw={yaw}, pitch={pitch}.",
        }

    async def _handle_say_this(
        self, args: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        text = args.get("text", "")
        log.info("[Haseef tool] say_this: %s", text[:80])

        gemini = self.gemini
        if gemini is None:
            return {"ok": False, "error": "Gemini Live not connected"}

        self._haseef_said_this = True
        log.info("[HaseefBridge] say_this received — Haseef is delivering its own answer")

        framed = f"(Haseef result): {text}\nSay this to the user now naturally, as if it's your own knowledge."

        async with self._say_lock:
            if gemini.is_speaking.is_set():
                self._pending_says.append(framed)
                log.info("[Haseef tool] say_this queued (Gemini speaking)")
                return {"ok": True, "status": "queued"}

        gemini.inject_client_content(framed)
        return {"ok": True}

    async def _handle_capture_image(
        self, args: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        jpeg_b64 = None
        if self.camera is not None:
            jpeg_b64 = self.camera.get_base64_jpeg()
        if jpeg_b64 is None:
            log.warning("[Haseef tool] capture_image: no frame available")
            return {"ok": False, "error": "camera not ready"}
        log.info("[Haseef tool] capture_image: %d KB", len(jpeg_b64) // 1024)
        await self._push_image_event(
            jpeg_b64,
            note="Here is what I see right now.",
        )
        return {"ok": True, "image_base64": jpeg_b64}

    # --- Haseef lifecycle handlers ------------------------------------------
    def _on_haseef_run_started(self, event: Any) -> None:
        log.info("[Haseef] run started: %s", event)
        self._haseef_run_active = True
        self._haseef_run_start_ts = time.time()
        self._haseef_last_activity_ts = time.time()
        self._haseef_said_this = False
        self._haseef_said_wait = False
        self._haseef_collected_results.clear()

    def _on_haseef_run_completed(self, event: Any) -> None:
        log.info("[Haseef] run completed: %s", event)
        self._haseef_run_active = False

        # If Haseef already called say_this, it delivered its own
        # natural-language answer — nothing more to do.
        if self._haseef_said_this:
            log.info("[HaseefBridge] run completed — Haseef already spoke via say_this")
            return

        # Haseef didn't call say_this — deliver collected results as fallback.
        if not self._haseef_collected_results:
            log.warning("[HaseefBridge] run completed — no say_this and no collected results")
            return

        # Deduplicate: if all results are the same (e.g. "no results" x3),
        # just deliver one. Otherwise combine unique results.
        unique_results = list(dict.fromkeys(self._haseef_collected_results))
        combined = "\n\n".join(unique_results)
        log.info(
            "[HaseefBridge] run completed — delivering %d unique results (%d chars, was %d collected)",
            len(unique_results), len(combined), len(self._haseef_collected_results),
        )
        asyncio.create_task(self._deliver_haseef_result(combined))

    def _on_haseef_tool_error(self, event: Any) -> None:
        log.error("[Haseef] tool error: %s", event)

    def _on_haseef_tool_call(self, event: Any) -> None:
        log.info("[Haseef] tool.call: %s", event)
        self._haseef_last_activity_ts = time.time()
        # Fallback: if run.started didn't fire, start animation on first tool call.
        if not self._haseef_run_active:
            log.info("[Haseef] tool.call fallback — starting run tracking")
            self._haseef_run_active = True
            self._haseef_run_start_ts = time.time()
            self._haseef_said_this = False
            self._haseef_said_wait = False
            self._haseef_collected_results.clear()

    async def _deliver_haseef_result(self, text: str) -> None:
        """Deliver the final Haseef result to Gemini for speaking."""
        gemini = self.gemini
        if gemini is None:
            log.warning("[HaseefBridge] cannot deliver result — Gemini not connected")
            return
        framed = (
            f"(Haseef result): {text}\n"
            f"Say this to the user now naturally, as if it's your own knowledge. "
            f"Rephrase and synthesize if needed."
        )
        async with self._say_lock:
            if gemini.is_speaking.is_set():
                self._pending_says.append(framed)
                log.info("[HaseefBridge] result queued (Gemini speaking): %s", text[:80])
                return
        log.info("[HaseefBridge] delivering result to Gemini: %s", text[:80])
        try:
            gemini.inject_client_content(framed)
            log.info("[HaseefBridge] result inject OK")
        except Exception as e:
            log.error("[HaseefBridge] result inject FAILED: %s", e)

    # --- Gemini tool handler ------------------------------------------------
    async def _run_sdk_on_main(self, coro):
        """Run an SDK coroutine on the main event loop from Gemini's thread."""
        if self._main_loop is None or self._main_loop.is_closed():
            raise RuntimeError("Main event loop not available for SDK call")
        future = asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        return await asyncio.wrap_future(future)

    async def gemini_tool_handler(
        self, name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tool calls from Gemini Live. Must be async and return dict."""
        log.info("[Gemini tool] %s%s", name, args)

        if name == "queue_thinker_task":
            return await self._handle_queue_thinker_task(args)
        elif name == "remember_fact":
            return await self._handle_remember_fact(args)
        elif name == "recall_memory":
            return await self._handle_recall_memory(args)
        elif name == "get_current_time":
            return self._handle_get_current_time()
        elif name == "ping":
            return {"ok": True, "pong": True}
        else:
            return {"ok": False, "error": f"Unknown tool: {name}"}

    async def _handle_queue_thinker_task(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fire-and-forget. Return immediately so Gemini can speak right away."""
        task = args.get("task", "")
        what_i_told_user = args.get("what_i_told_user", "")
        log.info("[Gemini->Haseef] queue_thinker_task: %s", task[:100])
        self._last_task_ts = time.time()
        asyncio.create_task(self._push_thinker_task(task, what_i_told_user))
        return {"ok": True}

    async def _push_thinker_task(self, task: str, what_i_told_user: str) -> None:
        """Background: push the task to Haseef with one retry on timeout."""
        for attempt in range(1, 3):
            try:
                await self._run_sdk_on_main(self.haseef_sdk.push_event({
                    "type": "user_message",
                    "data": {
                        "text": (
                            f"Gemini needs help with: {task}\n"
                            f"(Gemini already told user: {what_i_told_user})"
                        ),
                        "source": "gemini_live",
                    },
                    "haseefId": self.haseef_id,
                }))
                if attempt > 1:
                    log.info("[Gemini->Haseef] push_event succeeded on attempt %d", attempt)
                return
            except httpx.TimeoutException:
                log.warning("[Gemini->Haseef] push_event timeout (attempt %d/2)", attempt)
            except Exception as e:
                log.error("[Gemini->Haseef] push_event failed (attempt %d/2): %r", attempt, e)
            if attempt < 2:
                await asyncio.sleep(1.0)
        log.error("[Gemini->Haseef] push_event gave up after 2 attempts: %s", task[:80])

    async def _handle_remember_fact(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        text = args.get("text", "")
        category = args.get("category", "general")
        try:
            await self._run_sdk_on_main(self.haseef_sdk.memory.set(self.haseef_id, [{
                "key": f"{category}:{text[:50]}",
                "value": text,
            }]))
            log.info("[Gemini->Haseef] remember_fact: %s", text[:80])
            return {"ok": True, "stored": text, "category": category}
        except Exception as e:
            log.error("Failed to store fact: %s", e)
            return {"ok": False, "error": str(e)}

    async def _handle_recall_memory(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        query = (args.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "query is required"}
        try:
            limit = int(args.get("limit") or 8)
        except (TypeError, ValueError):
            limit = 8
        limit = max(1, min(20, limit))
        try:
            results = await self._run_sdk_on_main(
                self.haseef_sdk.memory.search(self.haseef_id, query, limit)
            )
        except Exception as e:
            log.error("[Gemini tool] recall_memory failed: %s", e)
            return {"ok": False, "error": str(e)}

        hits = []
        for m in results or []:
            if not isinstance(m, dict):
                continue
            hits.append({
                "key": m.get("key"),
                "value": m.get("value"),
                "category": m.get("category"),
            })
        log.info("[Gemini tool] recall_memory '%s' -> %d hits", query[:60], len(hits))
        return {"ok": True, "query": query, "count": len(hits), "results": hits}

    def _handle_get_current_time(self) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "iso": now.isoformat(),
            "human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }


# ---------------------------------------------------------------------------
# Memory snapshot for Gemini's system prompt
# ---------------------------------------------------------------------------
async def build_memory_snapshot(
    sdk: Any,
    haseef_id: str,
    *,
    semantic_limit: int = 40,
) -> str:
    """Render a compact, human-readable snapshot of Haseef's memory."""
    sections: list[str] = []

    # --- Identity / profile ------------------------------------------------
    try:
        h = await sdk.haseef.get(haseef_id)
        name = h.get("name") or "Haseef"
        desc = h.get("description") or ""
        identity = [f"Haseef name: {name}"]
        if desc:
            identity.append(f"Description: {desc}")
        try:
            profile = await sdk.haseef.get_profile(haseef_id)
            if isinstance(profile, dict) and profile:
                for k, v in profile.items():
                    if v in (None, "", [], {}):
                        continue
                    identity.append(f"{k}: {v}")
        except Exception as e:
            log.debug("[snapshot] profile fetch failed: %s", e)
        sections.append("[Identity]\n" + "\n".join(identity))
    except Exception as e:
        log.warning("[snapshot] haseef.get failed: %s", e)

    # --- Semantic facts ----------------------------------------------------
    try:
        memories = await sdk.memory.list(haseef_id) or []
        if memories:
            lines = []
            for m in memories[:semantic_limit]:
                if not isinstance(m, dict):
                    continue
                val = m.get("value") or m.get("key") or ""
                cat = m.get("category")
                if not val:
                    continue
                lines.append(f"- ({cat}) {val}" if cat else f"- {val}")
            if lines:
                sections.append("[Facts]\n" + "\n".join(lines))
    except Exception as e:
        log.warning("[snapshot] memory.list failed: %s", e)

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    load_dotenv(override=True)

    ensure_daemon_running()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set. Add it to .env", file=sys.stderr)
        sys.exit(1)

    core_url = os.environ.get("HSAFA_CORE_URL", "https://core.hsafa.com")
    core_key = os.environ.get("HSAFA_CORE_KEY", "")
    haseef_id = os.environ.get("HASEEF_ID", "")

    if not core_key:
        print("Error: HSAFA_CORE_KEY not set. Add it to .env", file=sys.stderr)
        sys.exit(1)

    if not haseef_id:
        print("Error: HASEEF_ID not set.", file=sys.stderr)
        sys.exit(1)

    # --- Camera (try direct; fallback to daemon inside ReachyMini) ----------
    camera: Optional[Any] = None
    direct_camera = Camera()
    if direct_camera.open():
        camera = direct_camera
        log.info("Camera ready (direct OpenCV).")
    else:
        log.warning("Direct camera failed; will use daemon camera instead.")

    # --- Robot controller ---------------------------------------------------
    robot = None

    # --- Haseef SDK ---------------------------------------------------------
    haseef_sdk = HsafaSDK(SdkOptions(
        core_url=core_url,
        api_key=core_key,
        skill="robot_base",
    ))
    _patch_sdk_timeout(haseef_sdk)

    # Verify Haseef exists and has the skill
    log.info("Verifying Haseef %s ...", haseef_id)
    try:
        h = await haseef_sdk.haseef.get(haseef_id)
        skills = h.get("skills") or []
        if "robot_base" not in skills:
            log.info("Attaching 'robot_base' skill to Haseef...")
            try:
                await haseef_sdk.haseef.add_skill(haseef_id, "robot_base")
                skills.append("robot_base")
            except Exception as e:
                log.warning("Could not attach 'robot_base' skill: %s", e)
        log.info(
            "Haseef '%s' ready (skills: %s).",
            h.get("name", "?"), skills,
        )
        cfg = h.get("configJson") or {}
        log.info("Haseef configJson: %s", cfg)
    except Exception as e:
        log.error("Could not verify Haseef: %s", e)
        print(
            f"\n[FATAL] Haseef {haseef_id} not found or not accessible.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    main_loop = asyncio.get_running_loop()

    # --- Bridge -------------------------------------------------------------
    bridge = UnifiedBridge(
        None, haseef_sdk, robot, camera, haseef_id,
        main_loop=main_loop,
    )
    await bridge.setup_haseef()

    # Start Haseef SSE listener in background
    log.info("Connecting to Haseef SSE stream...")
    haseef_task = asyncio.create_task(haseef_sdk.connect(), name="haseef-sse")
    await asyncio.sleep(1)  # Let connection establish

    # --- Reachy audio -------------------------------------------------------
    try:
        from reachy_mini import ReachyMini
    except ImportError:
        print(
            "[FATAL] reachy_mini not installed. Install it for audio.",
            file=sys.stderr,
        )
        sys.exit(1)

    with ReachyMini(automatic_body_yaw=False) as reachy:
        media = reachy.media
        if media is None or getattr(media, "audio", None) is None:
            print(
                "[FATAL] Reachy media not available. "
                "Start daemon without --no-media.",
                file=sys.stderr,
            )
            sys.exit(1)

        media.start_recording()
        media.start_playing()
        log.info("Audio ready.")

        # Create face tracker (YOLOv8-Pose cascade)
        tracker = None
        try:
            model_path = ensure_pose_model()
            device = pick_device()
            tracker = CascadeTracker(model_path, device)
            tracker.start()
            tracker.warmup(480, 640)
            log.info("[Tracker] CascadeTracker started (device=%s).", device)
        except Exception as e:
            log.warning("[Tracker] Failed to start face tracker: %s — face tracking disabled.", e)

        # Create robot controller now that we have the ReachyMini instance
        robot = RobotController(reachy, tracker=tracker, camera=camera)
        robot.start_idle()
        bridge.robot = robot
        log.info("Robot controller ready (face_tracking=%s).", tracker is not None)

        # If direct camera failed, wrap daemon's camera
        if camera is None:
            if getattr(media, "get_frame", None) is None:
                print("[FATAL] Daemon camera unavailable.", file=sys.stderr)
                sys.exit(1)

            camera = DaemonCamera(media)
            bridge.camera = camera
            robot._camera = camera
            log.info("Camera ready (daemon).")

        # Background capture thread (OpenCV VideoCapture is NOT thread-safe;
        # cap.read() must stay on one thread).
        latest_frame: Optional[np.ndarray] = None
        _cap_running = threading.Event()
        _cap_running.set()

        def _capture_loop() -> None:
            nonlocal latest_frame
            while _cap_running.is_set():
                frame = camera.grab()
                if frame is not None:
                    latest_frame = frame
                time.sleep(0.033)  # ~30 FPS cap

        capture_thread = threading.Thread(target=_capture_loop, daemon=True, name="camera-cap")
        capture_thread.start()
        log.info("Camera capture thread started.")

        # Give the robot controller a thread-safe frame source so the idle
        # loop reads from the capture thread's shared buffer instead of
        # calling camera.grab() concurrently (which crashes OpenCV).
        robot._frame_source = lambda: latest_frame

        def frame_source() -> Optional[bytes]:
            """Return the latest camera frame for Gemini Live."""
            frame = latest_frame
            if frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            return buf.tobytes() if ok else None

        def mic_source():
            return media.get_audio_sample()

        def speaker_sink(samples):
            if robot:
                robot.notify_audio(samples)
            media.push_audio_sample(samples)

        # --- Memory snapshot for Gemini ------------------------------------
        try:
            memory_snapshot = await build_memory_snapshot(haseef_sdk, haseef_id)
            if memory_snapshot:
                log.info(
                    "[Memory] Snapshot built (%d chars):\n%s",
                    len(memory_snapshot), memory_snapshot,
                )
            else:
                log.info("[Memory] Snapshot is empty (no memories yet).")
        except Exception as e:
            log.warning("[Memory] snapshot build failed: %s", e)
            memory_snapshot = ""

        # --- Gemini Live ----------------------------------------------------
        gemini = GeminiLiveSession(
            api_key=api_key,
            mic_source=mic_source,
            speaker_sink=speaker_sink,
            frame_source=frame_source,
            system_instruction=build_gemini_system_prompt(memory_snapshot),
            tools=build_gemini_tools(),
            tool_handler=bridge.gemini_tool_handler,
        )
        bridge.gemini = gemini

        gemini.start()
        if not gemini.wait_until_ready(timeout=15):
            print("[FATAL] Gemini Live failed to connect.", file=sys.stderr)
            sys.exit(1)
        log.info("Gemini Live connected.")

        # Drive the speaking animation from Gemini's turn boundaries.
        robot.bind_speaking_event(gemini.is_speaking)

        # --- Main loop ------------------------------------------------------
        stop_event = asyncio.Event()

        async def _drain_say_queue():
            while not stop_event.is_set():
                await asyncio.sleep(0.15)
                if gemini.is_speaking.is_set():
                    continue
                async with bridge._say_lock:
                    if bridge._pending_says:
                        text = bridge._pending_says.pop(0)
                        gemini.inject_client_content(text)
                        log.info("[SayDrain] injected queued text: %s", text[:80])

        say_drain_task = asyncio.create_task(_drain_say_queue(), name="say-drain")

        # --- Haseef watchdog: nudge + hard timeout ---
        async def _haseef_watchdog():
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
                if not bridge._haseef_run_active:
                    continue
                elapsed = time.time() - bridge._haseef_run_start_ts
                idle = time.time() - bridge._haseef_last_activity_ts

                # Hard timeout: no activity for 60s → declare run dead
                if idle > 60.0:
                    log.error(
                        "[HaseefBridge] run timed out — no activity for %.0fs (total %.0fs). Declaring run dead.",
                        idle, elapsed,
                    )
                    bridge._haseef_run_active = False
                    gemini_ref = bridge.gemini
                    if gemini_ref and not gemini_ref.is_speaking.is_set():
                        timeout_msg = (
                            "(Haseef status): The search took too long and timed out. "
                            "Tell the user you couldn't find the answer right now, "
                            "apologize briefly, and offer to try again. "
                            "In their language, one or two sentences."
                        )
                        gemini_ref.inject_client_content(timeout_msg)
                    continue

                # Soft nudge: at 20s, tell the user we're still looking
                if elapsed > 20.0 and not bridge._haseef_said_wait:
                    bridge._haseef_said_wait = True
                    gemini_ref = bridge.gemini
                    if gemini_ref and not gemini_ref.is_speaking.is_set():
                        nudge = (
                            "(Haseef status): Still processing, taking longer than expected. "
                            "Briefly tell the user you're still looking. "
                            "One short sentence in their language."
                        )
                        gemini_ref.inject_client_content(nudge)
                        log.info("[HaseefBridge] watchdog nudge sent after %.0fs", elapsed)

        watchdog_task = asyncio.create_task(_haseef_watchdog(), name="haseef-watchdog")

        def _sigint(*_):
            log.info("Caught SIGINT, shutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, _sigint)

        log.info("Running. Press Ctrl-C to stop.")
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass

        # --- Shutdown -------------------------------------------------------
        log.info("Stopping Gemini Live...")
        gemini.stop()
        say_drain_task.cancel()
        watchdog_task.cancel()
        try:
            await say_drain_task
        except asyncio.CancelledError:
            pass
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass

        log.info("Disconnecting Haseef...")
        await haseef_sdk.disconnect()
        haseef_task.cancel()
        try:
            await haseef_task
        except asyncio.CancelledError:
            pass

        media.stop_recording()
        media.stop_playing()

        _cap_running.clear()
        capture_thread.join(timeout=1.0)

        if robot:
            robot.stop_idle()
    camera.close()
    log.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
