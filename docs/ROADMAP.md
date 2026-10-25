# Roadmap

The GitHub issue tracker is the execution queue. This page records phase order and intended outcomes.

## Phase 0 — Repository foundations
- [x] Product scope, architecture, decision log, and contribution workflow
- [x] Modular source layout and dependency definition
- [x] CI for tests and static checks (CI is present; PR checks must be green before merge)
- [x] Issue templates and pull-request template

## Phase 1 — Desktop shell and design system
- [x] Initial shared theme tokens and basic shell
- [x] All planned page destinations represented in the shell
- [x] Reusable panels, metric cards, and initial functional page implementations
- [x] Compact collapsible navigation with tooltips
- [ ] Responsive layouts and keyboard accessibility audit
- [x] Demo/real record separation in persistence and UI tests

## Phase 2 — Domain and persistence
- [x] Typed session, observation, metric, settings snapshot, and experiment models
- [x] Initial versioned SQLite schema and repository methods
- [x] Initial session workflow service
- [x] Tests for demo/real-data separation and missing-value handling
- [ ] Safe import/migration from the existing MVP's JSON records

**Migration blocker:** the original MVP source and its JSON schema are not currently in the repository. Do not implement an importer until the real source/schema is available and can be backed up and tested.

## Phase 3 — Session review
- [ ] Verify end-to-end playback with representative real video files/codecs
- [x] Playback controls, seeking, and local file selection UI
- [x] Timestamped observations and notes with categories
- [x] Stable local persistence for session and observation records
- [x] Missing recording paths are detected and reported
- [x] Exportable Markdown session summary
- [x] Optional observation tags with normalisation and local persistence
- [x] Search/filter session notes and Aim Lab/Movement review by text or tag
- [x] Include tags in Markdown exports
- [x] Exportable structured data (JSON/CSV)

## Phase 4 — Settings Lab and coaching
- [x] Baseline settings snapshots
- [x] Record an experiment with explicit baseline/test snapshots and changed variable
- [x] Experiment status and outcome capture
- [x] Side-by-side baseline/test snapshot comparison with exact changed values
- [x] Show changed-setting counts in experiment history
- [x] Summarise outcomes across completed/inconclusive experiments with non-causal wording
- [x] Evidence-linked, transparent coaching prompts based on manual notes
- [x] Aim and movement note-review pages
- [x] Coaching prompts explicitly avoid causal claims and distinguish manual notes from automatic analysis

## Phase 5 — Validated analysis

Current baseline: the desktop app now supports local recorded-session review, timestamped manual notes, local settings snapshots, experiment outcomes, overview counts, and transparent rules-based review prompts. It does not yet perform computer-vision analysis or claim to be a trained AI coach.

- [ ] Define measurable vision use cases and ground truth
- [x] Build an initial offline frame-sampling utility with manifest and tests
- [x] Add schema-versioned local annotation data service with source-fingerprint validation
- [x] Build initial graphical local frame annotation workflow
- [x] Document annotation labels and ambiguity-handling protocol
- [x] Add dataset label-coverage and recording-level leakage checks
- [x] Add reviewer agreement summaries and local JSON report export
- [x] Include a descriptive summary of manually labelled aim frames, with selection-bias caveats
- [x] Summarize consecutive human-labelled on/off-target frame runs when sampling interval is known, with tests and duration caveats
- [x] Add an initial screen-space optical-flow report for sampled frames, with explicit limitations and tests
- [x] Add optional human-marked reticle/target coordinate storage and descriptive spatial-offset summaries
- [ ] Add aspect-ratio-safe click-to-mark reticle/target points in the annotation UI and test marking consistency
- [ ] Benchmark annotation workflow, motion estimates, and sampling against real recordings
- [ ] Display method, units, confidence, and limitations
- [ ] Add capabilities only after validation

## Phase 6 — Release hardening
- [ ] Packaging and installation test on a clean Windows environment
- [ ] Privacy and fair-play review
- [ ] Crash/error reporting policy (opt-in only if added)
- [ ] Release checklist and versioned changelog
