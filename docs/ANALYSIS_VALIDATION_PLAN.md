# Aim and Movement Analysis Validation Plan

This plan is a gate for computer-vision features. It does not claim that such analysis is implemented.

## Stage 1 — Curated offline clips

- Use user-owned recordings and explicit consent.
- Store clip metadata and annotations locally.
- Let the user label target transitions, visible crosshair placement, movement starts/stops, and relevant outcomes.
- Exclude clips with unreadable UI, unknown sensitivity/zoom, severe compression, or unclear timestamps from quantitative scoring.

## Stage 2 — Reproducible measurements

Each proposed metric needs a written definition, unit, sampling rate, input requirements, known confounders, and a baseline comparison. Prefer measurable observations (for example, time between visible events) over speculative conclusions about intent or skill.

## Stage 3 — Annotation agreement

- Create an annotation guide with positive, negative, and ambiguous examples.
- Have a second reviewer label a subset of clips where feasible.
- Report agreement and disagreement; revise labels before model training.
- Keep training, tuning, and evaluation clips separated by match/session to reduce leakage.

## Stage 4 — Evaluation

- Report precision/recall and false-positive examples for event detection.
- Compare estimates with manual annotations and disclose sample size.
- Test different resolutions, frame rates, HUD settings, scopes, and recording compression.
- Do not present a metric as reliable when evidence is insufficient; show unavailable/low-confidence instead.

## Stage 5 — Coaching quality

- Every coaching suggestion must link to a clip/time range and state its evidence.
- Prefer a small, testable next action over a sweeping diagnosis.
- Separate observation from interpretation and recommendation.
- Never auto-change game settings; run one-variable user-controlled experiments and compare repeated sessions.

## Non-goals

No game-memory reading, anti-cheat bypass, automated gameplay inputs, or covert capture. Any live capture requires separate platform/fair-play and privacy review.


## Implemented first prototype: offline frame sampling

The optional utility at src/siegesense/vision/frame_sampling.py samples a user-selected local recording into a separate, empty output directory and writes a versioned JSON manifest with source SHA-256, source FPS/resolution/duration, sampling range, interval, frame indices, and timestamps. Install the optional dependency with pip install -e ".[vision]". This is a sampling foundation only; it does not detect targets, crosshair position, movement, or skill. Validate it against representative recordings before using outputs for quantitative claims.
