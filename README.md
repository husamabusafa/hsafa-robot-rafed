# Hsafa Robot

Reachy Mini robot agent with Gemini Live voice + Haseef brain integration.

## Features

- **Voice**: Gemini Live real-time streaming (mic + speaker via Reachy Mini)
- **Vision**: Camera feed streamed to Gemini Live (~1 FPS)
- **Movement**: Head motion (yaw/pitch), idle + speaking animations, antenna wiggle
- **Emotions**: HuggingFace emotion clips (60+ expressions with motion + sound)
- **Haseef integration**: Bidirectional bridge with Haseef SDK (memory, scheduling, tool calls)
- **Person tracking**: YOLOv8-Pose + ByteTrack cascade tracker (head/body/motion)

## Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your GEMINI_API_KEY, HSAFA_CORE_KEY, and HASEEF_ID

# 4. Start the Reachy Mini daemon
./scripts/daemon.sh start

# 5. Run the robot
python main.py
```

## Architecture

```
hsafa_robot/
  animation.py       - Idle + talking overlay animations
  audio_vad.py       - Silero VAD (voice activity detection)
  emotion_player.py  - HuggingFace emotion clips for Reachy Mini
  events.py          - In-process pub/sub event bus
  gemini_live.py     - Gemini Live API session wrapper
  robot_control.py   - P-controller + animations for face/person tracking
  scheduler_skill.py - In-memory schedule runner
  tracker.py         - YOLOv8-Pose + ByteTrack + Kalman cascade tracker
  world_state.py     - Thread-safe shared state
hsafa_voice_vision.py - Camera + RobotController wrapper
main.py              - Entry point: Gemini Live + Haseef bridge
scripts/daemon.sh    - Reachy Mini daemon manager
```

## Haseef Tools

The robot exposes these tools to Haseef:
- `look_around(yaw_deg, pitch_deg)` — Move head + capture image
- `set_head_pose(yaw_deg, pitch_deg)` — Move head without capturing
- `say_this(text)` — Make the robot speak
- `capture_image(quality?)` — Capture camera image
- `show_expression(emotion)` — Play emotion clip
- `create_schedule` / `list_schedules` / `cancel_schedule` — Task scheduling
