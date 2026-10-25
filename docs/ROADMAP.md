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
- [ ] Shared reusable components and polished page implementations
- [ ] Compact collapsible navigation, responsive layouts, and keyboard support
- [ ] Clearly isolated demo workspace with end-to-end UI coverage

## Phase 2 — Domain and persistence
- [x] Typed session, observation, metric, settings snapshot, and experiment models
- [x] Initial versioned SQLite schema and repository methods
- [x] Initial session workflow service
- [x] Tests for demo/real-data separation and missing-value handling
- [ ] Safe import/migration from the existing MVP's JSON records

**Migration blocker:** the original MVP source and its JSON schema are not currently in the repository. Do not implement an importer until the real source/schema is available and can be backed up and tested.

## Phase 3 — Session review
- [ ] Recorded-video playback
- [x] Timestamped observations and notes with categories
- [x] Stable local persistence for session and observation records
- [ ] Graceful media errors and file validation
- [ ] Tags and exportable session summary

## Phase 4 — Settings Lab and coaching
- [x] Baseline settings snapshots
- [x] Record an experiment with explicit baseline/test snapshots and changed variable
- [ ] Experiment outcome capture and comparison views
- [ ] Evidence-linked coaching notes with uncertainty
- [ ] Compare experiments without overstating causality

## Phase 5 — Validated analysis
- [ ] Define measurable vision use cases and ground truth
- [ ] Build offline analysis prototypes and benchmark them
- [ ] Display method, units, confidence, and limitations
- [ ] Add capabilities only after validation

## Phase 6 — Release hardening
- [ ] Packaging and installation test on a clean Windows environment
- [ ] Privacy and fair-play review
- [ ] Crash/error reporting policy (opt-in only if added)
- [ ] Release checklist and versioned changelog
