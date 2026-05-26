"""Offline structural eval — compare the two voices side by side.

This does NOT measure learning gain (that's v1 with real athletes).
What it does measure: are the feedback-architecture outputs *structurally*
different from the answer-machine outputs in the ways the thesis predicts?

For each round in manifest.json it computes:

  - word count
  - sentence count
  - whether the response asks a question (presence of "?")
  - whether the response cites a timestamp ("0:" pattern)
  - whether the response uses the "you said you'd" verbatim contract
  - count of prescriptive imperative verbs ("keep", "try", "ensure",
    "focus", "make sure", "rotate") — the answer-machine signal

The thesis predicts:
  Feedback architecture → terse, asks a question, cites a timestamp,
                          uses "you said you'd", few imperative verbs.
  Answer machine        → verbose, no question, no timestamp,
                          no verbatim contract, many imperative verbs.

If a future prompt edit silently weakens the contrast, this eval makes it
visible. Run via `make eval` or `python -m eval.compare`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"

IMPERATIVE_PATTERNS = [
    r"\bkeep\b",
    r"\btry\b",
    r"\bensure\b",
    r"\bfocus\b",
    r"\bmake sure\b",
    r"\brotate\b",
    r"\bpractice\b",
    r"\bmaintain\b",
    r"\bavoid\b",
]
TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
SENTENCE_RE = re.compile(r"[.!?]+\s+")


def metrics_for_text(text: str) -> dict:
    text = text.strip()
    words = re.findall(r"\b\w+\b", text)
    sentences = [s for s in SENTENCE_RE.split(text) if s.strip()]
    imperatives = sum(len(re.findall(p, text, re.IGNORECASE)) for p in IMPERATIVE_PATTERNS)
    return {
        "words": len(words),
        "sentences": max(1, len(sentences)),
        "asks_question": "?" in text,
        "cites_timestamp": bool(TIMESTAMP_RE.search(text)),
        "uses_verbatim_contract": "you said you'd" in text.lower(),
        "imperative_count": imperatives,
    }


def feedback_arch_blob(fa: dict) -> str:
    """Flatten the feedback-architecture JSON to a single comparable string."""
    moment = fa.get("moment") or {}
    parts = [
        fa.get("intent_restated", ""),
        f"Watch {moment.get('timestamp', '')}.",
        moment.get("observation", ""),
        fa.get("question", ""),
        fa.get("next_round_focus", ""),
    ]
    return " ".join(p for p in parts if p)


def render_row(label: str, m: dict) -> str:
    return (
        f"| {label} | {m['words']} | {m['sentences']} | "
        f"{'✓' if m['asks_question'] else '·'} | "
        f"{'✓' if m['cites_timestamp'] else '·'} | "
        f"{'✓' if m['uses_verbatim_contract'] else '·'} | "
        f"{m['imperative_count']} |"
    )


def main() -> int:
    if not MANIFEST.exists():
        print(f"no manifest at {MANIFEST}. run `make prebake` first.")
        return 1

    data = json.loads(MANIFEST.read_text())
    clips = data.get("clips", [])
    if not clips:
        print("manifest has no clips.")
        return 1

    print("# Cornerman structural eval\n")
    print(
        "_The thesis predicts: feedback-architecture is short, asks a question, "
        "cites a timestamp, uses the verbatim contract, and uses few imperatives. "
        "Answer-machine is the opposite. If a prompt edit ever silently breaks "
        "the contrast, the cells below stop matching this prediction._\n"
    )
    print("| clip | words | sentences | ? | timestamp | verbatim | imperative-verbs |")
    print("|---|---:|---:|:-:|:-:|:-:|---:|")

    aggregate_pass = True
    for clip in clips:
        name = clip.get("name", "?")
        fa = clip.get("feedback_architecture") or {}
        am = clip.get("answer_machine") or ""

        fa_metrics = metrics_for_text(feedback_arch_blob(fa))
        am_metrics = metrics_for_text(am)

        print(render_row(f"{name} — feedback architecture", fa_metrics))
        print(render_row(f"{name} — answer machine", am_metrics))

        thesis_ok = (
            fa_metrics["asks_question"]
            and fa_metrics["cites_timestamp"]
            and fa_metrics["uses_verbatim_contract"]
            and fa_metrics["words"] < am_metrics["words"]
            and not am_metrics["asks_question"]
            and am_metrics["imperative_count"] > fa_metrics["imperative_count"]
        )
        if not thesis_ok:
            aggregate_pass = False
            print(f"\n> ⚠ **{name}**: prompts no longer produce the predicted contrast.\n")

    print()
    if aggregate_pass:
        print("**Result:** ✅ The two voices remain structurally distinct on every clip.")
        return 0
    print("**Result:** ⚠ At least one clip no longer matches the thesis prediction.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
