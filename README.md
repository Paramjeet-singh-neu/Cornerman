# Cornerman 🥊

> A boxing tutor that **doesn't give answers.** It surfaces the gap between
> *intent* and *attempt* — as a **question.**
>
> The model isn't the product. The loop is.

**Live demo:** https://cornerman.streamlit.app

---

## The thesis

Most AI tutors are **answer machines.** They watch a learner and tell them
what to fix. Cornerman is **feedback architecture**: a learning loop where
the AI's job is to make the learner *notice the gap*, not close it for them.

The product isn't the model. The product is the loop:

1. **Intent first** — the learner declares what they're trying to do.
2. **Attempt** — they record a clip.
3. **Predict** — before seeing the AI, they articulate what they think it will flag.
4. **Question** — the AI cites one timestamp, makes one observation, ends with a question. Never a correction.
5. **Transfer check (round 2+)** — a separate measurement: did this round actually address the focus flagged last round?

The UI shows two AI responses side-by-side: an *answer machine* baseline (a
generic-coach paragraph) on the right, the *feedback architecture* (the loop)
on the left. **The contrast IS the pitch.**

---

## How it works

```
   clips/round*.mp4              prebake.py               responses/*.json + manifest.json
   ┌────────────────┐    cv2 @ 1 fps      ┌───────────────────────────┐   ┌───────────────┐
   │ user-recorded  │ ─────────────────→  │  GPT-4o vision, 3 calls:  │ → │ feedback_*.json│
   │ training clip  │    frames/round*/   │  feedback architecture    │   │ answer_*.txt   │
   │                │    t000.jpg etc.    │  answer machine           │   │ transfer_*.json│
   └────────────────┘                     │  transfer check (rd 2+)   │   └───────────────┘
                                          └───────────────────────────┘            │
                                                                                   ▼
                                                       ┌────────────────────────────────┐
                                                       │           manifest.json        │
                                                       │ { clips: [ { intent, video,    │
                                                       │   feedback_architecture,       │
                                                       │   answer_machine,              │
                                                       │   transfer_check }, ... ] }    │
                                                       └────────────────────────────────┘
                                                                                   │
                                                                                   ▼
                                                       ┌────────────────────────────────┐
                                                       │             app.py             │
                                                       │  Streamlit. Reads manifest.    │
                                                       │  ZERO API calls at runtime.    │
                                                       └────────────────────────────────┘
```

**Two pieces of code, one shared schema.**

- `prebake.py` runs once, hits OpenAI three times per round, writes everything to disk.
- `app.py` reads `manifest.json` and renders the loop. **No network calls** — the demo cannot fail because OpenAI is slow.

---

## The six principles, mapped to code

Cornerman implements all six principles of the *Builder Playbook for
AI-enhanced learning.* Each one is enforced by code, not by claim:

| Principle | Where it lives in the build |
|---|---|
| **1. Start from a complete artifact** | The athlete's own 20-second clip is the artifact — `clips/round*.mp4`. |
| **2. Make the learner attempt or predict first** | The intent box gates the round (`render_round`); the *Predict first* text box (`render_predict_first_gate`) blocks the AI columns until the learner types or skips. |
| **3. Prefer questions and hints before answers** | `FEEDBACK_ARCHITECTURE_SYSTEM` in `prompts.py` is hard-bound: *never state the correction; end with a question.* A CI test fails if those rules ever drift. |
| **4. Expose evidence, diffs, tests, or citations** | Every observation cites a timestamp; `frame_for_timestamp` looks up the cached still and renders it inline as visible evidence. |
| **5. Fade assistance and test transfer** | Round 2's *Progress check* (`render_progress_check`) measures whether the focus from round 1 was actually addressed. |
| **6. Measure learning, not just output quality** | `TRANSFER_CHECK_SYSTEM` is a separate API call with its own JSON schema. Measurement is structurally separate from feedback. |

---

## Project layout

```
.
├── app.py                          # Streamlit app. Reads manifest. Zero API.
├── prebake.py                      # One-time prebake; 3 OpenAI calls per round.
├── prompts.py                      # All three system prompts + builders.
├── manifest.json                   # The contract between prebake and app.
├── meta.json                       # Submission metadata (see schema below).
├── clips/round1.mp4 round2.mp4     # User-recorded training clips.
├── frames/round*/                  # Auto-extracted at 1 fps by prebake.
├── responses/                      # Cached JSON + text per round.
├── .streamlit/config.toml          # Brand theme, hide Streamlit chrome.
├── .github/workflows/ci.yml        # Smoke tests on every push + PR.
└── tests/test_smoke.py             # Import, prompt-rule, helper, manifest tests.
```

---

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 1. Drop round1.mp4 + round2.mp4 in clips/
# 2. Set your key
export OPENAI_API_KEY=sk-...
# 3. Pre-bake (hits the API once per round per prompt; idempotent)
python prebake.py
# 4. Run the demo (no network needed after prebake)
streamlit run app.py
```

`prebake.py` is idempotent — it skips clips whose responses already exist
in `responses/`. To force a re-call for one round, delete that round's
JSON and re-run.

---

## Deploy

Streamlit Community Cloud. Point at `app.py`. **No secrets needed** — the
running app makes no API calls, the pre-baked responses are committed to
the repo. Live URL: https://cornerman.streamlit.app

---

## Design decisions worth flagging

- **Pre-bake everything to disk.** The Streamlit app is read-only at runtime. The demo cannot fail because the OpenAI API is slow, rate-limited, or unreachable.
- **The fundamentals chips read text, not video.** They highlight what the *loop* engaged with this round — not a grading rubric of the whole clip. Deliberate: if a coach says "we're working on head movement today," they don't critique the jab. The loop is athlete-directed.
- **Three API calls per round, two prompts.** Feedback architecture (the product), answer machine (the baseline), transfer check (the measurement). The third only runs from round 2 onward. Total cost: ~$0.03 per round at `gpt-4o` with `detail="low"`.
- **Tests enforce prompt content, not just imports.** The hard rules of the feedback-architecture prompt ("NEVER state the correction", "you said you'd", "end with a QUESTION") are asserted in CI. If the prompt ever drifts away from the thesis, the build fails.

---

## What's missing — honest v1 roadmap

This is a 90-minute hackathon build. It's a demo of an architecture, not
evidence that the architecture teaches better. Here is what v1 looks like:

| Gap | Why it matters | What v1 would do |
|---|---|---|
| **n = 1** (one athlete, one session) | The thesis is unfalsified. The architecture works for me; maybe not for someone else. | Pilot with 5 athletes × 3 weeks. Transfer-check delta as the primary metric. |
| **Single-sport demo** | *"Generalizes to any skill sport"* is hand-waved. | Mock the same UI on a tennis serve to prove the architecture survives. |
| **No coach signal** | A real boxing trainer has not signed off. | One coach on camera reacting to Cornerman's output. |
| **Single-session memory** | Cross-round state lives in `st.session_state`; dies when the tab closes. | Persistent per-athlete history across sessions. |
| **No eval harness** | "Question-first feedback is better" is a hypothesis. | Comparative eval: same clips through both prompts; coaches rank outputs blind. |
| **Strawman baseline** | The answer machine is `gpt-4o` asked to be generic. | Compare against curated baselines (real coaching apps). |
| **Prompts are the IP** | Prompts are easy to copy. | A motion-tagged reference library + coach-curated intent templates. |

---

## Built for

**Boston Tech Week Sports Hack — 2026-05-26** (Cursor Boston × Hult Sports).
Category: **Athletes and Team Performance** — help athletes use data from
practice to make better performance decisions.
