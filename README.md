# Cornerman 🥊

A boxing tutor demo built around one idea:

> **Most AI tutors are answer machines. Cornerman is feedback architecture.**
> The learner states an intent *before* attempting, attempts on video, and
> the AI surfaces the gap as a **question**, not a correction.
> The UI shows both responses side-by-side so the contrast is the pitch.

The model isn't the product. The loop is.

---

## How it works

Each round is the same loop:

1. **Intent** — the learner declares what they're trying to do.
2. **Attempt** — they record a short clip.
3. **Two responses, side-by-side** —
   - 🥊 **Feedback architecture** — names one moment, asks one question, never tells them what to fix.
   - 🤖 **Answer machine** — a generic coach paragraph telling them what's wrong and what to do. (Baseline for contrast.)

Round N's observation is carried into the prompt for round N+1 so the
feedback can build on what came before.

## Project layout

| Path | What it is |
| --- | --- |
| `app.py` | Streamlit app. Reads `manifest.json`. **Zero API calls at runtime.** |
| `prebake.py` | Run once before the demo. Extracts frames, calls OpenAI, caches everything. |
| `prompts.py` | The two prompts. |
| `clips/` | Drop `round1.mp4`, `round2.mp4`, `round3.mp4` here. |
| `frames/` | Auto-populated by `prebake.py` (1 frame/sec). |
| `responses/` | Auto-populated cached JSON + text responses. |
| `manifest.json` | Auto-generated. App reads this. |

## Run locally

```bash
pip install -r requirements.txt

# 1. Drop round1.mp4, round2.mp4, round3.mp4 into clips/
# 2. Pre-bake (one-time, hits the OpenAI API)
export OPENAI_API_KEY=sk-...
python prebake.py

# 3. Run the demo (no network needed)
streamlit run app.py
```

`prebake.py` is idempotent — it skips clips whose responses already exist
under `responses/`. To force a re-call, delete the relevant file in
`responses/` and re-run.

## Deploy to Streamlit Community Cloud

1. Commit this repo (including `manifest.json`, `responses/`, and the
   `clips/*.mp4` files) to GitHub.
2. Point Streamlit Community Cloud at `app.py`.
3. No secrets needed — the app makes no API calls.

The pre-baked responses are what get demoed. The demo cannot fail because
OpenAI is slow or unreachable.

## Why this design

The whole product thesis is that the *shape* of the feedback loop —
intent → attempt → question — is more useful than the smartest possible
answer. The side-by-side UI exists to make that visible in one screen.
