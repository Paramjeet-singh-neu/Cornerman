"""
Cornerman prebake.

Run this ONCE before the demo:

    python prebake.py

For each clip in CLIPS it will:
  1. Extract 1 frame/sec with OpenCV into frames/<name>/tNNN.jpg
  2. Call GPT-4o with the feedback-architecture prompt
  3. Call GPT-4o with the answer-machine prompt
  4. Cache both responses under responses/
  5. Carry round N's moment forward as prior_round for round N+1
  6. Write manifest.json

The Streamlit app reads manifest.json and makes ZERO API calls at runtime,
so the live demo cannot be blocked by network latency or OpenAI hiccups.

Already-cached work is skipped, so re-runs are cheap. Delete the relevant
file under responses/ to force a re-call for that round.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import cv2
from openai import OpenAI

from prompts import (
    ANSWER_MACHINE_SYSTEM,
    FEEDBACK_ARCHITECTURE_SYSTEM,
    TRANSFER_CHECK_SYSTEM,
    build_answer_machine_user_prompt,
    build_feedback_architecture_user_prompt,
    build_transfer_check_user_prompt,
)

ROOT = Path(__file__).parent
CLIPS_DIR = ROOT / "clips"
FRAMES_DIR = ROOT / "frames"
RESPONSES_DIR = ROOT / "responses"
MANIFEST_PATH = ROOT / "manifest.json"

MODEL = "gpt-4o"

# Edit these intents to match the actual clips you record.
CLIPS = [
    {
        "name": "round1",
        "file": "clips/round1.mp4",
        "intent": "Keep both hands up between every punch in my jab–cross–uppercut combo.",
    },
    {
        "name": "round2",
        "file": "clips/round2.mp4",
        "intent": "Move my head off the centerline after every combo before I reset.",
    },
]


def extract_frames(video_path: Path, out_dir: Path) -> list[Path]:
    """Sample one frame per second of the video into out_dir as tNNN.jpg.

    Returns the list of frame paths in time order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("t*.jpg"))
    if existing:
        print(f"  frames: {len(existing)} already cached in {out_dir.name}/")
        return existing

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps else 0

    out_paths: list[Path] = []
    for sec in range(int(duration) + 1):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        path = out_dir / f"t{sec:03d}.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        out_paths.append(path)
    cap.release()
    print(f"  frames: extracted {len(out_paths)} @ 1fps from {video_path.name}")
    return out_paths


def frame_to_data_uri(frame_path: Path) -> str:
    b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def build_image_parts(frame_paths: list[Path]) -> list[dict]:
    return [
        {
            "type": "image_url",
            "image_url": {"url": frame_to_data_uri(p), "detail": "low"},
        }
        for p in frame_paths
    ]


def call_feedback_architecture(
    client: OpenAI,
    intent: str,
    prior_round: dict | None,
    frame_paths: list[Path],
) -> dict:
    user_text = build_feedback_architecture_user_prompt(intent, prior_round)
    content = [{"type": "text", "text": user_text}] + build_image_parts(frame_paths)
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": FEEDBACK_ARCHITECTURE_SYSTEM},
            {"role": "user", "content": content},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


def call_answer_machine(
    client: OpenAI, intent: str, frame_paths: list[Path]
) -> str:
    user_text = build_answer_machine_user_prompt(intent)
    content = [{"type": "text", "text": user_text}] + build_image_parts(frame_paths)
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.7,
        messages=[
            {"role": "system", "content": ANSWER_MACHINE_SYSTEM},
            {"role": "user", "content": content},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def call_transfer_check(
    client: OpenAI, prior_round: dict, frame_paths: list[Path]
) -> dict:
    user_text = build_transfer_check_user_prompt(
        prior_focus=prior_round.get("next_round_focus", ""),
        prior_observation=prior_round.get("observation", ""),
    )
    content = [{"type": "text", "text": user_text}] + build_image_parts(frame_paths)
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TRANSFER_CHECK_SYSTEM},
            {"role": "user", "content": content},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


def cached_or_call_json(path: Path, fn) -> dict:
    if path.exists():
        print(f"  cached: {path.name}")
        return json.loads(path.read_text())
    result = fn()
    path.write_text(json.dumps(result, indent=2))
    print(f"  wrote:  {path.name}")
    return result


def cached_or_call_text(path: Path, fn) -> str:
    if path.exists():
        print(f"  cached: {path.name}")
        return path.read_text()
    result = fn()
    path.write_text(result)
    print(f"  wrote:  {path.name}")
    return result


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: set OPENAI_API_KEY before running prebake.py", file=sys.stderr)
        return 1

    RESPONSES_DIR.mkdir(exist_ok=True)
    FRAMES_DIR.mkdir(exist_ok=True)
    client = OpenAI()

    manifest_clips: list[dict] = []
    prior_round: dict | None = None

    for clip in CLIPS:
        name = clip["name"]
        video_path = ROOT / clip["file"]
        intent = clip["intent"]
        print(f"\n=== {name} ===")

        if not video_path.exists():
            print(
                f"  SKIP: {video_path} not found. Drop your mp4 in clips/ and re-run."
            )
            continue

        frames_out = FRAMES_DIR / name
        frame_paths = extract_frames(video_path, frames_out)
        if not frame_paths:
            print("  SKIP: no frames extracted")
            continue

        fa_path = RESPONSES_DIR / f"{name}_feedback_architecture.json"
        am_path = RESPONSES_DIR / f"{name}_answer_machine.txt"
        tc_path = RESPONSES_DIR / f"{name}_transfer_check.json"

        fa = cached_or_call_json(
            fa_path,
            lambda: call_feedback_architecture(client, intent, prior_round, frame_paths),
        )
        am = cached_or_call_text(
            am_path, lambda: call_answer_machine(client, intent, frame_paths)
        )

        # Principle 6: learning measurement. Only meaningful from round 2 on,
        # since round 1 has no prior focus to measure transfer against.
        transfer_check: dict | None = None
        if prior_round:
            captured_prior = prior_round
            transfer_check = cached_or_call_json(
                tc_path,
                lambda: call_transfer_check(client, captured_prior, frame_paths),
            )

        manifest_clips.append(
            {
                "name": name,
                "video": clip["file"],
                "intent": intent,
                "feedback_architecture": fa,
                "answer_machine": am,
                "transfer_check": transfer_check,
            }
        )

        moment = fa.get("moment") or {}
        prior_round = {
            "timestamp": moment.get("timestamp", ""),
            "observation": moment.get("observation", ""),
            "next_round_focus": fa.get("next_round_focus", ""),
        }

    manifest = {"clips": manifest_clips}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {MANIFEST_PATH.name} ({len(manifest_clips)} clip(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
