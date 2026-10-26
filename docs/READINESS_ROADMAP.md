# SiegeSense AI — Readiness Roadmap

**Status:** In development — not ready to claim precise, automated coaching yet  
**Last updated:** 2026-10-26  
**Working branch:** `feat/annotated-sequence-metrics`  
**Related review:** [Draft PR #14](https://github.com/IliasK151/siegesense-ai/pull/14)  
**Project goal:** A local-first Windows desktop coach that analyzes recorded Rainbow Six Siege gameplay and helps players understand aim, movement, decisions, and settings through evidence-backed feedback.

This document is the handoff and source of truth for continuing work across multiple chats. Update the status and evidence as each piece is completed. “Implemented” means code exists; it does not mean the feature is validated on real gameplay.

## 1. Work completed so far

The items below describe work present on the current working branch as recorded in the project history. They still need a fresh end-to-end review and a passing CI run at the latest commit before being considered release-verified.

### Session and data foundations
- Session media fingerprinting with chunked SHA-256, stored fingerprint support, and database schema v2 migration.
- Fingerprinting is on-demand rather than an implicit UI-thread operation.
- Recording identity checks help prevent linking annotations to the wrong recording.
- Local-first workflows; no requirement to upload recordings to a cloud service.

### Clip annotation and sampled-frame workflow
- Load a local sampled-frame manifest and browse frames.
- Create, edit, and delete human annotations with labels, annotator identity, and notes.
- Link annotations to a session review observation with timestamps and tags.
- Local video sampling workflow with selectable output folder and interval, plus manifest loading.
- Annotation summary refresh and JSON evaluation report export.
- Sequence summaries for consecutive manually labelled on/off-target runs, movement markers, and timestamp gaps.
- Runs break on missing intervals/gaps; unlabelled frames are not interpolated. Sampled span is not represented as exact event duration.

### Evaluation and experiment integrity
- Dataset label-coverage and recording-fingerprint split-leakage summaries.
- Annotator agreement summaries, including Cohen's kappa where defined.
- Evaluation report records limitations and explicitly sets `model_performance_evaluated: false`.
- Settings Lab test experiments require a valid baseline and test snapshot, shared demo provenance, different snapshots, and exactly one changed setting when a test snapshot is attached.
- Tests cover a range of dataset, reporting, annotation, and settings validation cases.

### Initial visual-motion prototype
- Sparse optical-flow estimates between eligible adjacent sampled frames.
- Per-pair displacement summaries, tracked-feature counts, and a descriptive coherent-feature ratio.
- JSON motion report export from the desktop UI.
- Deterministic pair limit; gaps are skipped; malformed or mismatched image pairs are counted as unusable.
- Path traversal checks for POSIX and Windows manifest paths; report export avoids overwriting the source manifest.
- The metric describes movement of visible image features only. It is not mouse input, true aim direction, reticle-to-target distance, opponent detection, aim accuracy, or player skill. Camera motion, recoil animation, moving objects, effects, scene changes, and compression can confound it.

### Documentation and automated checks
- README, annotation guide, analysis validation plan, and roadmap describe the current limitations.
- CI has previously passed on Python 3.10, 3.11, and 3.12 for earlier commits.
- A missing `pytest` import was found during a later UI-test change and patched. **The latest commit must be rechecked in CI; do not assume the fix passed until the workflow reports success.**

## 2. Not ready yet — release blockers

These are required before we can honestly call the product ready as a usable *automated coach*. Prioritize in the order below.

### P0 — establish a reproducible, working baseline
- [ ] Check latest GitHub Actions run for all supported Python versions; fix every test, lint, packaging, and type-check failure.
- [ ] Review the current branch diff and PR #14 for accidental changes, duplicate code, API inconsistencies, and broken UI paths.
- [ ] Run the app from a clean environment using documented install steps; verify database migration from an existing v1 database.
- [ ] Smoke-test the complete desktop flow: create session, import/sample recording, annotate frames, link review notes, export reports, close/reopen app, and verify persisted data.
- [ ] Verify graceful behavior for missing OpenCV, corrupt manifests, missing frames, unreadable videos, invalid intervals, empty datasets, and cancelled dialogs.
- [ ] Add a clear version number, supported Windows/Python versions, known limitations, and a reproducible issue-report template.

### P1 — actual reticle and opponent detection
- [ ] Define exactly which supported Siege HUD layouts, resolutions, aspect ratios, display modes, and scopes are in scope.
- [ ] Build a representative, permission-safe evaluation set of gameplay clips and frames. Keep a held-out test split separated by recording fingerprint, not random frames from the same recording.
- [ ] Write an annotation guide for reticle center/shape, visible opponent bounding boxes, occlusion, ambiguous frames, scope/HUD state, and unusable frames.
- [ ] Collect independently labelled examples and measure inter-annotator agreement before treating labels as ground truth.
- [ ] Implement a detector or configurable reticle/HUD calibration approach only after the data and evaluation protocol are defined.
- [ ] Report precision, recall, false-positive/false-negative examples, confidence calibration, and per-condition results. Do not present a single accuracy number without its test set and limitations.
- [ ] Detect out-of-scope conditions and abstain clearly instead of guessing.

### P2 — validate overshoot, target switching, and movement
- [ ] Define operational labels for overshoot, undershoot, correction, target acquisition, target switch, recoil/camera movement, and uncertain events.
- [ ] Establish timestamp and frame-rate handling, including dropped frames and variable frame rate.
- [ ] Compare automated event predictions with held-out human labels; publish event-level precision/recall and timing error.
- [ ] Separate observable screen motion from inferred mouse movement. Do not infer mouse input from optical flow alone.
- [ ] Add an uncertainty state and show evidence frames for every coaching claim.
- [ ] Benchmark across several players, weapons/scopes, sensitivities, resolutions, and game situations to check whether the model generalizes.
- [ ] If evidence is insufficient, keep the feature manual/experimental rather than offering confident automated feedback.

### P3 — sensitivity and settings recommendations
- [ ] Capture a player's current DPI, in-game horizontal/vertical sensitivity, ADS multipliers, scope values, FOV, resolution, and relevant input settings with explicit confirmation.
- [ ] Implement correct, documented calculations and unit handling for eDPI and ADS conversions where applicable; account for game-version/configuration differences.
- [ ] Design a controlled, one-variable-at-a-time test protocol with baseline, repeated trials, and objective measures.
- [ ] Make recommendations as reversible experiments with rationale, expected trade-off, confidence, and a way to reject/undo them.
- [ ] Never change game settings automatically or claim a value is optimal based on one clip. The player must confirm any manual changes.
- [ ] Validate that recommendations outperform a simple baseline and do not merely fit the same clips used to create them.

### P4 — useful coaching experience
- [ ] Build a session review that explains *what happened*, points to evidence frames/timestamps, distinguishes observation from inference, and offers one actionable drill at a time.
- [ ] Include trend summaries only where enough comparable sessions exist; explain missing data and sample sizes.
- [ ] Separate demo/sample data from real user recordings throughout UI, charts, and exports.
- [ ] Add understandable confidence/uncertainty, failure messages, progress states, and accessible keyboard navigation.
- [ ] Ensure reports never imply that manually selected frame labels measure aim accuracy, hit probability, rank, or skill.
- [ ] Validate advice with real players in a small usability study and document the results before making performance claims.

### P5 — release engineering and privacy
- [ ] Create clean Windows install/package instructions and test on a fresh Windows machine/account.
- [ ] Verify OpenCV and all optional dependencies install cleanly; pin/test supported dependency ranges.
- [ ] Add automated packaging/startup smoke tests and a release build checklist.
- [ ] Document local storage locations, what data is saved, export behavior, deletion/retention, and any telemetry (prefer none by default).
- [ ] Check logging and crash reports do not expose personal paths or recording contents unnecessarily.
- [ ] Add backup/export and recovery guidance for the local database.
- [ ] Review software licenses, third-party model/data licenses, and game/platform terms before distribution.
- [ ] Prepare release notes, known limitations, and a support/bug-report workflow.

## 3. Definition of “ready”

Do not mark the project ready just because it launches or the test suite passes. The following gates are all required for the claim that automated coaching is ready:

1. **Engineering:** clean install and launch; latest CI green; database migrations and core flows pass on supported Windows environments.
2. **Detection:** reticle/opponent detections measured on a documented, representative, recording-separated held-out dataset, with acceptable precision/recall agreed before testing.
3. **Event analysis:** overshoot/target-switch/movement claims evaluated against human-labelled ground truth, with uncertainty and failure cases visible.
4. **Recommendations:** sensitivity advice is tested as reversible, one-variable experiments and is not presented as guaranteed optimal.
5. **Product quality:** real users can complete the workflow, understand limitations, and find evidence for every important coaching claim.
6. **Privacy and distribution:** local-data handling, dependencies, licenses, installation, and recovery are documented and tested.

Until these gates are met, describe the app as an **early local analysis prototype with manual annotations and experimental screen-motion summaries**, not a precise automated Siege coach.

## 4. Work in small chat-sized pieces

Use one phase per chat to keep work manageable. Each phase should end with: code committed, tests added, latest CI checked, this roadmap updated, and a short handoff note for the next chat.

| Piece | Scope | Completion evidence |
|---|---|---|
| 1 | Baseline audit and CI repair | Latest CI green; clean install/smoke-test results documented |
| 2 | Recording evaluation dataset and annotation protocol | Dataset schema, guide, split/leakage checks, documented data provenance |
| 3 | Reticle/HUD detection prototype | Reproducible detector and measured held-out results |
| 4 | Opponent detection prototype | Per-condition precision/recall and false-positive review |
| 5 | Overshoot/target-switch event evaluation | Defined labels, event-level metrics, timing-error report |
| 6 | Sensitivity experiment and recommendation engine | Verified calculations, controlled tests, reversible suggestions |
| 7 | Coaching UI and evidence-backed explanations | Usability checks and confidence/uncertainty presentation |
| 8 | Windows packaging, privacy, and release validation | Fresh-machine install evidence and completed release checklist |

## 5. Handoff template for the next chat

Start by reading this file and the current branch/PR state. Do not assume the prior chat's last CI status is current.

- Current branch: `feat/annotated-sequence-metrics`
- Review PR: [#14](https://github.com/IliasK151/siegesense-ai/pull/14)
- First task: **Piece 1 — baseline audit and CI repair**
- First actions: fetch latest workflow runs; identify latest commit and run conclusion; inspect job logs for failures; fix the root cause; rerun CI; inspect project install/test configuration; update this file with verified outcomes.
- Do not merge PRs unless the user explicitly asks.
- Do not claim accuracy, detection, coaching validation, or release readiness without recorded evidence.
