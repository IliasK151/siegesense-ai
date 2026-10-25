# Roadmap

The GitHub issue tracker is the execution queue. This page records phase order and intended outcomes.

## Phase 0 — Repository foundations
- [ ] Product scope, architecture, decision log, and contribution workflow
- [ ] Modular source layout and dependency definition
- [ ] CI for tests and static checks
- [ ] Issue templates and pull-request template

## Phase 1 — Desktop shell and design system
- [ ] Shared theme tokens and reusable components
- [ ] Compact collapsible navigation and all planned page destinations
- [ ] Responsive layouts, empty states, error states, and keyboard support
- [ ] Clearly isolated demo workspace

## Phase 2 — Domain and persistence
- [ ] Typed session, observation, metric, and experiment models
- [ ] SQLite schema and migrations
- [ ] Safe import/migration from the existing MVP's JSON records
- [ ] Tests for demo/real-data separation and missing-value handling

## Phase 3 — Session review
- [ ] Recorded-video playback
- [ ] Timestamped observations, tags, and notes
- [ ] Stable persistence and graceful media errors
- [ ] Exportable session summary

## Phase 4 — Settings Lab and coaching
- [ ] Baseline settings snapshots
- [ ] One-variable-at-a-time experiment workflow
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
