# SiegeSense AI — Readiness Roadmap

**Status:** In development — not ready to claim precise, automated coaching yet  
**Last updated:** 2026-10-26  
**Working branch:** `feat/usable-coach-workflow`  
**Current draft review:** [PR #16](https://github.com/IliasK151/siegesense-ai/pull/16) (stacked on [PR #14](https://github.com/IliasK151/siegesense-ai/pull/14))  
**Project goal:** A local-first Windows desktop coach that analyzes recorded Rainbow Six Siege gameplay and helps players understand aim, movement, decisions, and settings through evidence-backed feedback.

This document is the handoff and source of truth for continuing work across multiple chats. Update the status and evidence as each piece is completed. “Implemented” means code exists; it does not mean the feature is validated on real gameplay.

## 1. Work completed so far

The items below describe work present on the current working branch as recorded in the project history. The latest CI run is green, but that does not replace a fresh end-to-end review or a real Windows smoke test.

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
- Sequence summaries for consecutive manually labelled on/off-target runs, movement markers, timestamp gaps, and adjacent off-target→on-target / on-target→off-target label transitions when sampling timing is known. These are label-transition counts, not validated aim-correction metrics.
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

### Manual spatial annotation prototype
- Click-to-mark tools let a reviewer mark reticle center and a chosen target reference point on a sampled frame; coordinates are normalized to the full frame, including when the preview is letterboxed.
- Annotation storage validates optional coordinate pairs and supports older annotation records without coordinates.
- The UI shows descriptive target-minus-reticle offsets and can export a manual spatial-offset JSON report.
- These are human-marked still-frame geometry measurements. They do not detect the reticle/opponents automatically or establish overshoot, undershoot, mouse movement, aim accuracy, or player skill.

### Documentation and automated checks
- README, annotation guide, analysis validation plan, and roadmap describe the current limitations.
- Latest Quality CI run [40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942) passed on Python 3.10, 3.11, and 3.12. Each job reported 163 passed and 2 skipped; `ruff check .` passed in all three jobs. The two skips are optional OpenCV tests because `cv2` is not installed in CI.
- A missing `pytest` import was found in the motion UI test and patched; subsequent work added manual coordinate marking, spatial-offset reports, and label-transition summaries.
- Local Windows test kit added: `scripts/setup_windows.ps1`, `scripts/run_windows.ps1`, `scripts/check_windows.ps1`, and `scripts/package_windows.ps1`; user guide: [`docs/TEST_YOUR_OWN_SIEGE_CLIP.md`](TEST_YOUR_OWN_SIEGE_CLIP.md). These scripts have been committed but have not been executed on a real Windows environment.
- **Latest Quality CI is green:** [run 40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942) executed successfully on Windows for Python 3.10, 3.11, and 3.12. Each environment reported 163 passed and 2 skipped; Ruff passed in all jobs. The skips are the optional optical-flow tests because OpenCV is not installed in CI. This verifies tests and lint for that commit only; it does not validate packaged builds or the full workflow with real recordings. The repository is now public to enable hosted runners, so review the current tree and Git history for secrets and personal/private data.

## 2. Not ready yet — release blockers

These are required before we can honestly call the product ready as a usable *automated coach*. Prioritize in the order below.

### P0 — establish a reproducible, working baseline
- [x] Add Windows one-click setup/launch and check/package scripts plus a personal-recording test guide. These are code/documentation additions only; execution on Windows remains unverified.
- [ ] Download the feature-branch source ZIP on Windows, double-click `START_SIEGESENSE.bat` to install and launch, then run `CHECK_SIEGESENSE.bat`. Fix any concrete script, dependency, test, or lint errors surfaced locally.
- [x] Restore hosted Quality workflow execution. Making the repository public allowed the Windows runners to initialize and execute all test/lint steps; latest Quality run `40299057942` is green. This does not establish packaging or local end-to-end readiness. Because the repository is public, review the current tree and full Git history for accidentally committed secrets or private data.
- [x] Verify the latest Python 3.10/3.11/3.12 Quality matrix: all three jobs pass, with 161 tests passed and 2 optional OpenCV tests skipped per job; Ruff passes in all three. Packaging and real-media Windows smoke tests remain separate tasks.
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
| 1 | Baseline audit and CI repair | Current failing workflow cause identified; latest CI green; clean install/smoke-test results documented |
| 2 | Recording evaluation dataset and annotation protocol | Dataset schema, guide, split/leakage checks, documented data provenance |
| 3 | Reticle/HUD detection prototype | Reproducible detector and measured held-out results |
| 4 | Opponent detection prototype | Per-condition precision/recall and false-positive review |
| 5 | Overshoot/target-switch event evaluation | Defined labels, event-level metrics, timing-error report |
| 6 | Sensitivity experiment and recommendation engine | Verified calculations, controlled tests, reversible suggestions |
| 7 | Coaching UI and evidence-backed explanations | Usability checks and confidence/uncertainty presentation |
| 8 | Windows packaging, privacy, and release validation | Fresh-machine install evidence and completed release checklist |

## 5. Handoff template for the next chat

Start by reading this file and the current branch/PR state. Do not assume the prior chat's last CI status is current.

- Current branch: `feat/usable-coach-workflow`
- Current draft review: [PR #16](https://github.com/IliasK151/siegesense-ai/pull/16), stacked on [PR #14](https://github.com/IliasK151/siegesense-ai/pull/14). Neither has been merged.
- Latest verified code commit: `b3d0039f87aafc21d28fecf7427561a78568d803`
- Latest Quality run: [40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942) — green across Python 3.10/3.11/3.12; each job reports 163 passed, 2 skipped, and Ruff passed.
- Next task: **run clean-install, package, and real-media smoke tests on Windows**, including migration from an existing v1 database and optional OpenCV dependency behavior.
- The Windows scripts and user test guide are committed but have not yet been run on the user's Windows PC. Record concrete output from setup/check/package and fix any issue found. Keep PR #16 in draft until baseline review and smoke tests are complete.
- Do not merge PRs unless the user explicitly asks.
- Do not claim accuracy, detection, coaching validation, or release readiness without recorded evidence.


## Usability slice — 2026-10-26

Branch: `feat/usable-coach-workflow` (stacked on `feat/annotated-sequence-metrics`; no merge performed).

Changes implemented in code:
- Added a prominent drag-and-drop video zone on Overview and Clip Annotation, with a browse fallback for users who prefer choosing a file.
- Dropped videos are sampled asynchronously at a lighter 500 ms default interval into a new non-overwriting sibling review folder; the UI remains responsive and loads the sampled frames automatically.
- The app creates or reuses a local Session Review record for the video, opens its local playback player, and exposes a single button to move into the sampled-frame review.
- Added scroll containers around each workspace so lower controls in long pages remain reachable at smaller window sizes.
- Added Overview shortcuts for Session Review, Clip Annotation, Settings Lab, and AI Coach.
- Added a Preferences & Privacy workspace that displays the database location and file status, opens the local data folder, and exports a consistent SQLite backup without copying a live database file directly.
- Added a deterministic coaching aggregation service driven by explicitly entered tags. It groups overflick/underflick, target-switch, crosshair-placement, correction, recoil, movement, positioning, and decision tags into one focused practice block with source notes.
- Evidence is described as a single note, repeated in one session, or recurring across sessions. Free text alone does not trigger a diagnosis; no insight is described as proof or as a validated detection.
- Added service-level tests for tag aliases, note deduplication, across-session evidence, and conservative wording, plus UI/backup coverage.

Verification caveat:
- These edits are committed to the feature branch but have not yet been run on the user's Windows PC.
- Latest Quality CI run [40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942) is green: 163 passed and 2 skipped in each Python version, with Ruff passing. The app has not yet been smoke-tested on the user's Windows PC.
- This does not complete the overall product. Automatic reticle/opponent detection, robust temporal event analysis, validated settings recommendations, and real-media Windows validation remain release blockers.


## Manual temporal offset evidence — integration into usability branch

The manually tracked target-relative offset analysis from draft PR #15 is included in this branch's Clip Annotation path:
- annotations can store an optional normalized manual target/sequence ID without breaking older schema-v1 datasets;
- same-target point offsets are compared only for annotated samples exactly one known sampling interval apart;
- UI summary displays horizontal/vertical offset sign-change counts and eligible same-target pair counts;
- a local JSON report records exclusions and explicitly states that automatic detection, overshoot diagnosis, and aim-accuracy evaluation were not performed;
- report export protects the source video, manifest, annotation dataset, and sampled frame files from overwrite.

This is additional review evidence, not automatic aim detection. The latest Quality CI run [40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942) passes tests and lint; the feature still remains unverified in a real Windows PC workflow and does not provide automatic aim detection.


## Settings experiment context additions

Settings Lab records mouse DPI and the active `MouseSensitivityMultiplierUnit` value alongside horizontal/vertical sensitivity and ADS multipliers. These are user-entered configuration context, not automatically detected from the mouse driver or game. Before saving a baseline, users must verify every field against their own active configuration; the app never applies changes.


## Read-only game configuration import

A user-selected `GameSettings.ini` importer reads the `[INPUT]` section without writing to the source file. It maps only explicit values for horizontal/vertical sensitivity, hip-fire/ADS multipliers, global ADS and the exact 1x ADS key. Other scope-specific entries are disclosed rather than guessed across differing UI labels. DPI remains user-entered. Service and UI tests are added; Windows execution is still unverified.


## Current CI and verification status — 2026-10-26

Latest Quality CI run: [40299057942](https://github.com/IliasK151/siegesense-ai/actions/runs/40299057942). Python 3.10, 3.11, and 3.12 jobs all passed; each reported 163 passed, 2 skipped, and successful Ruff checks. Two optional tests skipped because OpenCV is not installed in the CI environment. Hosted runner initialization is now working for this workflow.

Still outstanding: run the setup, check, and package scripts on a clean Windows machine; install or intentionally document optional OpenCV behavior; verify real video/frame playback, database migration, and end-to-end persistence; and audit the public repository's full Git history for secrets or private data. The current draft PR remains [#16](https://github.com/IliasK151/siegesense-ai/pull/16) and must not be merged until these checks are reviewed.
