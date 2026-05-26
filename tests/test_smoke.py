"""Smoke tests for Cornerman.

These tests do NOT call OpenAI or run cv2 on real video. They verify the
static surface of the project — module imports, prompt content, helper
behavior, and manifest shape. If anything load-bearing drifts, CI fails.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_all_modules_import() -> None:
    """All three top-level modules must import cleanly."""
    import app  # noqa: F401
    import prebake  # noqa: F401
    import prompts  # noqa: F401


def test_prompts_have_required_constants() -> None:
    from prompts import (
        ANSWER_MACHINE_SYSTEM,
        FEEDBACK_ARCHITECTURE_SYSTEM,
        TRANSFER_CHECK_SYSTEM,
    )
    for name, value in [
        ("answer_machine", ANSWER_MACHINE_SYSTEM),
        ("feedback_architecture", FEEDBACK_ARCHITECTURE_SYSTEM),
        ("transfer_check", TRANSFER_CHECK_SYSTEM),
    ]:
        assert len(value) > 100, f"{name} prompt is suspiciously short"


def test_feedback_architecture_hard_rules_present() -> None:
    """The non-negotiable rules in the feedback-architecture prompt must persist.

    These rules ARE the product. If they drift silently, CI must fail.
    """
    from prompts import FEEDBACK_ARCHITECTURE_SYSTEM
    for required in [
        "NEVER state the correction",
        "you said you'd",
        "ONE observation",
        "QUESTION",
    ]:
        assert required in FEEDBACK_ARCHITECTURE_SYSTEM, (
            f"feedback-architecture prompt has lost the rule: {required!r}"
        )


def test_frame_timestamp_parser_handles_garbage() -> None:
    """frame_for_timestamp must never raise on malformed input."""
    import app
    assert app.frame_for_timestamp("anything", "") is None
    assert app.frame_for_timestamp("anything", "not a timestamp") is None
    assert app.frame_for_timestamp("anything", "x:y") is None
    assert app.frame_for_timestamp("nonexistent_round", "0:00") is None


def test_fundamentals_detection() -> None:
    """The keyword detector must light up the right chips and only those."""
    import app

    found = app.detect_fundamentals("Throw a clean jab-cross combo with hands up")
    assert {"Jab", "Cross", "Hand position"} <= found
    assert "Footwork" not in found

    found_head = app.detect_fundamentals(
        "Move my head off the centerline after every combo before I reset"
    )
    assert "Head movement" in found_head


def test_manifest_schema_when_present() -> None:
    """If a manifest.json has been baked, it must have the expected shape."""
    p = ROOT / "manifest.json"
    if not p.exists():
        return  # No prebake yet; nothing to check.
    data = json.loads(p.read_text())
    assert "clips" in data
    for clip in data["clips"]:
        for field in ("name", "intent", "feedback_architecture", "answer_machine"):
            assert field in clip, f"manifest clip missing field: {field}"
        # transfer_check may be None (round 1 has no prior round)
        assert "transfer_check" in clip
