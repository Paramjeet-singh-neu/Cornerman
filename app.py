"""
Cornerman — Streamlit demo.

Reads manifest.json (produced by prebake.py) and shows, for each round:

    Intent  →  Fundamentals in scope  →  Attempt (video)  →
    Progress check (round 2+)  →  Predict first  →
    Two ways an AI could respond

Both responses are pre-cached on disk. This app makes ZERO API calls.
The contrast between the two columns IS the pitch.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "manifest.json"
FRAMES_ROOT = ROOT / "frames"

THESIS = "The model isn't the product. The loop is."

# Boxing fundamentals → substrings we'll look for in intent/observation/question
# text to decide which fundamentals are "in scope" each round. Descriptive,
# not evaluative — no scoring. This reinforces principle 4 (expose evidence)
# without becoming an answer machine.
BOXING_FUNDAMENTALS: dict[str, list[str]] = {
    "Jab": ["jab"],
    "Cross": ["cross"],
    "Hook": ["hook"],
    "Uppercut": ["uppercut"],
    "Hand position": ["hand", "glove", "guard", "chin"],
    "Head movement": ["head", "slip", "roll", "centerline"],
    "Footwork": ["feet", "foot", "step", "stance", "pivot"],
    "Defense": ["block", "parry", "defense", "defend"],
}


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"clips": []}
    return json.loads(MANIFEST_PATH.read_text())


def frame_for_timestamp(round_name: str, timestamp: str) -> Path | None:
    """'0:01' -> frames/<round_name>/t001.jpg if it exists."""
    if not timestamp or ":" not in timestamp:
        return None
    try:
        minutes, seconds = timestamp.split(":")
        total = int(minutes) * 60 + int(seconds)
    except ValueError:
        return None
    candidate = FRAMES_ROOT / round_name / f"t{total:03d}.jpg"
    return candidate if candidate.exists() else None


def collect_clip_text(clip: dict) -> list[str]:
    fa = clip.get("feedback_architecture") or {}
    moment = fa.get("moment") or {}
    return [
        clip.get("intent", "") or "",
        fa.get("intent_restated", "") or "",
        moment.get("observation", "") or "",
        fa.get("question", "") or "",
        fa.get("next_round_focus", "") or "",
    ]


def detect_fundamentals(*texts: str) -> set[str]:
    blob = " ".join(t for t in texts if t).lower()
    return {
        name
        for name, kws in BOXING_FUNDAMENTALS.items()
        if any(k in blob for k in kws)
    }


def render_about_panel() -> None:
    """Sells the thesis in playbook language for judges who skim."""
    with st.expander("About Cornerman — the thesis and the playbook", expanded=False):
        st.markdown(
            """
**Most AI tutors are answer machines.** They watch an athlete and tell them what to fix.
**Cornerman is feedback architecture.** It makes the athlete declare intent, attempt,
predict, and *only then* surfaces the gap as a **question** — never a correction.
The model isn't the product. The loop is.

**Built against the Builder Playbook for AI-enhanced learning:**

1. **Start from a complete artifact** — the athlete's own 20-second clip.
2. **Make the learner attempt or predict first** — the intent box gates the video;
   the *Predict first* text box gates the AI's responses.
3. **Prefer questions and hints before answers** — the feedback-architecture prompt
   is hard-bound to *never state the correction; end with a question.*
4. **Expose evidence, diffs, tests, or citations** — every observation cites a
   timestamp; the cited frame is rendered inline as a still image.
5. **Fade assistance and test transfer** — round 2's *Progress check* measures
   whether the focus from round 1 was actually addressed.
6. **Measure learning, not just output quality** — the transfer-check JSON is the
   measurement, separate from the feedback itself.

**Beyond boxing:** the architecture generalizes to any skill sport where a single
attempt can be filmed — tennis serves, golf swings, climbing moves, dance reps.
            """
        )


def render_fundamentals_chips(clip: dict) -> None:
    """Per-round chip strip. Descriptive, not evaluative."""
    active = detect_fundamentals(*collect_clip_text(clip))
    parts: list[str] = []
    for name in BOXING_FUNDAMENTALS:
        if name in active:
            parts.append(f":green-background[**✓ {name}**]")
        else:
            parts.append(f":gray[· {name}]")
    st.markdown("**Fundamentals in scope this round**")
    st.markdown(" &nbsp; ".join(parts))


def render_session_fundamentals(clips: list) -> None:
    """Footer summary across all rounds in the session."""
    all_texts: list[str] = []
    for c in clips:
        all_texts.extend(collect_clip_text(c))
    active = detect_fundamentals(*all_texts)
    if not active:
        return
    ordered = [n for n in BOXING_FUNDAMENTALS if n in active]
    pretty = ", ".join(ordered)
    st.markdown(f"_This session has touched:_ **{pretty}**")


def render_feedback_architecture(fa: dict, round_name: str) -> None:
    st.markdown("### 🥊 Feedback architecture")
    st.caption("States intent. Points to one moment. Asks a question.")

    intent_restated = fa.get("intent_restated", "")
    moment = fa.get("moment", {}) or {}
    timestamp = moment.get("timestamp", "")
    observation = moment.get("observation", "")
    question = fa.get("question", "")
    next_focus = fa.get("next_round_focus", "")

    if intent_restated:
        capitalized = intent_restated[:1].upper() + intent_restated[1:]
        st.markdown(f"**{capitalized}**")
    if timestamp or observation:
        st.markdown(f"**Watch {timestamp}.** {observation}")
        frame_path = frame_for_timestamp(round_name, timestamp)
        if frame_path is not None:
            st.image(
                str(frame_path),
                caption=f"Evidence — frame at {timestamp}",
                use_container_width=True,
            )
    if question:
        st.markdown(f"👉 **{question}**")
        audio_path = ROOT / "responses" / f"{round_name}_question.mp3"
        if audio_path.exists():
            st.audio(str(audio_path), format="audio/mp3")
            st.caption("🎙 The corner-coach voice.")
    if next_focus:
        st.markdown(f"_Next round, watch for:_ {next_focus}")


def render_answer_machine(text: str) -> None:
    st.markdown("### 🤖 Answer machine")
    st.caption("Tells the learner what to fix. Generic coach voice.")
    st.write(text)


def render_progress_check(
    tc: dict | None, round_name: str, prev_clip: dict | None
) -> None:
    """Principle 6: measure learning. Only renders if a transfer check exists.

    Also stitches in the prediction the learner typed in the prior round
    so the loop is literal: their words → AI's question → next-round measurement.
    """
    if not tc:
        return
    addressed = (tc.get("addressed") or "").lower()
    ts = tc.get("evidence_timestamp", "")
    sentence = tc.get("one_sentence", "")

    st.subheader("Progress check")
    st.caption(
        "Did this round actually address what we flagged last round? "
        "The AI is measuring transfer — not output quality."
    )

    label = f"**{sentence}** _(see {ts})_" if ts else f"**{sentence}**"
    if addressed == "yes":
        st.success(f"✓ Addressed — {label}")
    elif addressed == "partial":
        st.warning(f"~ Partial — {label}")
    elif addressed == "no":
        st.error(f"✗ Not yet — {label}")
    else:
        st.info(label)

    frame_path = frame_for_timestamp(round_name, ts)
    if frame_path is not None:
        st.image(
            str(frame_path),
            caption=f"Transfer evidence — frame at {ts}",
            use_container_width=True,
        )

    if prev_clip:
        prev_name = prev_clip.get("name", "")
        prev_pred = (st.session_state.get(f"pred_{prev_name}", "") or "").strip()
        prev_q = (
            (prev_clip.get("feedback_architecture") or {}).get("question") or ""
        ).strip()
        if prev_pred or prev_q:
            st.markdown("---")
            st.markdown("**Last round**")
            if prev_pred:
                st.markdown(f"- You predicted: _\"{prev_pred}\"_")
            if prev_q:
                st.markdown(f"- Cornerman asked: _\"{prev_q}\"_")


def render_predict_first_gate(round_name: str) -> bool:
    """Principle 5 + principle 2 recursively at the feedback stage.

    Returns True iff the learner has chosen to reveal the AI responses.
    Their prediction stays visible on the page after reveal so they can
    compare it to what the AI saw — and it persists into the next round's
    progress check as 'the loop so far'.
    """
    reveal_key = f"reveal_{round_name}"
    pred_key = f"pred_{round_name}"
    revealed = bool(st.session_state.get(reveal_key, False))

    st.subheader("Your read")
    st.caption("Note what you'd flag in this attempt before revealing the AI's view.")
    st.text_area(
        "Your prediction",
        key=pred_key,
        height=80,
        placeholder="e.g. 'my right hand drops after the cross at about 0:02'",
        disabled=revealed,
        label_visibility="collapsed",
    )

    if not revealed:
        if st.button(
            "Show me what the AI saw", key=f"btn_{round_name}", type="primary"
        ):
            st.session_state[reveal_key] = True
            st.rerun()
        return False
    return True


def render_round(clip: dict, prev_clip: dict | None = None) -> None:
    round_name = clip.get("name", "")

    st.subheader("Intent")
    st.info(clip.get("intent", ""))

    render_fundamentals_chips(clip)

    st.subheader("Attempt")
    video_path = ROOT / clip.get("video", "")
    if video_path.exists():
        st.video(str(video_path))
    else:
        st.warning(
            f"Video not found at `{clip.get('video')}`. "
            "Drop the mp4 there and re-run prebake."
        )

    render_progress_check(clip.get("transfer_check"), round_name, prev_clip)

    if not render_predict_first_gate(round_name):
        return

    st.subheader("Two ways an AI could respond")
    left, right = st.columns(2, gap="large")
    with left:
        render_feedback_architecture(
            clip.get("feedback_architecture", {}) or {},
            round_name,
        )
    with right:
        render_answer_machine(clip.get("answer_machine", "") or "")


HERO_HTML = """
<div style="padding: 1.25rem 0 0.25rem 0;">
  <div style="display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
              background: #FFE9EC; color: #C8102E; font-size: 0.78rem;
              font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;">
    Feedback architecture · v0.1
  </div>
  <h1 style="margin: 0.6rem 0 0.4rem 0; font-size: 3rem; font-weight: 700;
             letter-spacing: -0.02em; line-height: 1.05;">
    Cornerman <span style="color: #E63946;">🥊</span>
  </h1>
  <p style="margin: 0; font-size: 1.15rem; color: #444; max-width: 56rem; line-height: 1.5;">
    A boxing tutor that doesn't give answers. It surfaces the gap between
    <em>intent</em> and <em>attempt</em> — as a <strong>question</strong>.
  </p>
</div>
"""


def main() -> None:
    st.set_page_config(page_title="Cornerman", page_icon="🥊", layout="wide")
    st.markdown(HERO_HTML, unsafe_allow_html=True)

    render_about_panel()
    st.markdown("")  # breathing room

    manifest = load_manifest()
    clips = manifest.get("clips", [])

    if not clips:
        st.error(
            "No clips found in manifest.json. "
            "Drop your mp4s in `clips/`, set OPENAI_API_KEY, then run "
            "`python prebake.py`."
        )
        return

    tab_labels = [f"Round {i + 1}" for i in range(len(clips))]
    tabs = st.tabs(tab_labels)
    for i, tab in enumerate(tabs):
        with tab:
            prev_clip = clips[i - 1] if i > 0 else None
            render_round(clips[i], prev_clip)

    st.divider()
    render_session_fundamentals(clips)
    st.caption(THESIS)


if __name__ == "__main__":
    main()
