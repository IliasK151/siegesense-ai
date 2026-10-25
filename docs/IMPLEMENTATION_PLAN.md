# SiegeSense AI completion plan

This plan breaks the work into reviewable slices. A slice is complete only when its code, automated tests, documentation, and stated verification evidence are present. Passing CI alone does not establish coaching accuracy.

## Product definition

The target is a local-first Rainbow Six Siege review and coaching desktop app that analyzes player-owned recordings, identifies observable mistakes, explains evidence and uncertainty, and helps a player test settings safely. It must not read protected game memory, inject into the game, automate gameplay inputs, or silently change settings.

## Slice 1 — Release and startup reliability

**Status: implementation added; latest CI verification pending.**

- [x] Add a startup smoke-test mode that initializes Qt, the navigation shell, and the local database without entering the normal event loop.
- [x] Run the packaged Windows executable in offscreen smoke-test mode during the Windows package workflow.
- [x] Capture a traceback to a temporary diagnostic file when the packaged smoke test fails, so windowed builds can be debugged without a console.
- [x] Add a source-entry-point subprocess smoke test.
- [x] Document what the package smoke test proves and what it does not prove.
- [ ] Confirm latest quality checks and Windows package workflow pass on the same commit.
- [ ] Install and launch the artifact on a separate clean Windows machine without Python installed.
- [ ] Verify representative real video files and codecs.

**Exit criteria:** CI tests/lint pass, package is built, packaged executable smoke test passes, and a human confirms clean-machine launch and media playback.

## Slice 2 — Recording and timestamp integrity

- Audit frame sampling against actual media timestamps, including constant-frame-rate and variable-frame-rate clips.
- Add tests for timestamp accuracy, duplicate/near-duplicate timestamps, rotation/orientation metadata, unreadable files, and interrupted sampling.
- Make sampling reports explicit about effective frame timestamps, source fingerprint, codec/metadata limitations, and skipped frames.
- Ensure session-to-recording links remain safe when source paths change or recordings are replaced.

**Exit criteria:** timestamp behavior is measured against a reference player or trusted media metadata on a representative test set; unsupported or ambiguous media conditions return clear errors instead of silently misleading results.

## Slice 3 — Reticle and opponent detection prototype

- Define a human annotation format for reticle center, visible opponent boxes/centers, target visibility, occlusion, and target transitions.
- Build a small local-only, consented, human-reviewed evaluation set from player-owned recordings.
- Implement candidate detection as an optional, isolated module with confidence values and explicit “unknown/unavailable” output.
- Visualize detections over sampled frames so false positives and false negatives can be reviewed.
- Keep training/tuning and held-out evaluation splits separated by whole recording/session.

**Exit criteria:** publish precision, recall, sample sizes, representative false-positive/false-negative cases, and confidence intervals where practical on held-out recordings. No claims of accuracy until predeclared acceptance thresholds are met.

## Slice 4 — Aim and movement event analysis

- Derive candidate events only when reticle/target detections are reliable enough; otherwise request manual labels.
- Separate screen/camera movement from player input where the available video evidence cannot distinguish them.
- Define exact units and algorithms for overshoot, settling, target-switching, reaction-time estimates, and movement consistency.
- Test each metric against human-reviewed event timestamps and report error distributions.
- Treat recoil, camera motion, blur, occlusion, compression, sensitivity changes, frame drops, and scene transitions as potential confounders.

**Exit criteria:** each exposed metric has documented validity conditions and held-out validation results; ambiguous events are marked unavailable rather than guessed.

## Slice 5 — Evidence-linked coaching and settings experiments

- Generate recommendations only from validated metrics and session context; include the evidence, confidence/limitations, and a suggested drill.
- Avoid one-clip conclusions and generic claims that a setting is “best.”
- Use the existing one-variable-at-a-time Settings Lab to compare repeatable baseline and test sessions.
- Keep users in control of applying settings; never write game configuration automatically.
- Track whether recommendations help across repeated sessions, not just a single clip.

**Exit criteria:** recommendations can be traced to evidence, tested with controlled comparisons, and withheld when evidence is insufficient.

## Slice 6 — Product polish, privacy, and release

- Verify local database persistence, migration paths, backup/export behavior, and data-directory failure handling.
- Audit keyboard navigation, screen scaling, minimum window size, and error messages.
- Verify install/uninstall and upgrades on a clean Windows machine.
- Review privacy disclosure, recording consent, storage locations, retention/deletion instructions, and crash/log behavior.
- Select and add an appropriate license before public distribution.
- Publish a release note and an algorithm/model card that clearly separates implemented features from validated capabilities.

**Exit criteria:** all release-readiness checklist items are verified and documented; the product does not advertise unvalidated precision coaching.

## Current product truth

The existing app provides session/settings workflows, manual video-frame annotations, annotation/evaluation summaries, and a descriptive optical-flow report. The current motion estimator is not a reticle detector, opponent detector, mouse-input measurement, aim score, or validated coaching system. The project should remain labelled as a preview until the gates above are met.
