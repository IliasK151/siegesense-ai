# SiegeSense AI — release readiness plan

This plan is split into small, reviewable phases. A phase is complete only when its code, tests, documentation, and validation evidence are present. A green CI run alone does not prove coaching accuracy.

## Product promise

The first public release may be described as a **local gameplay-review and manual-analysis tool**. It must not be described as a precise automatic AI aim coach until the relevant detectors and coaching recommendations have been measured on representative, independently annotated Siege footage.

## Phase 1 — trustworthy manual spatial analysis

**Goal:** make the existing manual reticle/target workflow useful and exportable without implying automatic detection.

- [x] Save normalized reticle and target coordinates alongside frame annotations.
- [x] Keep point marking aligned to the source image despite aspect-ratio letterboxing.
- [x] Calculate target-minus-reticle offsets only when both points are manually marked.
- [x] Export a standalone JSON report with units, source dataset, and limitations.
- [x] Protect the source annotation dataset from being overwritten by the report.
- [x] Add unit and UI integration tests for report generation.
- [ ] Obtain a green CI run for the final commit and run the tests on a clean Windows environment.
- [ ] Conduct a manual usability pass using a real Siege clip.

**Exit criteria:** exported offsets match hand-calculated sample coordinates; missing points are excluded rather than guessed; tests and lint pass; the report clearly says that no automatic detector or model-performance evaluation was used.

## Phase 2 — reliable data and video workflow

- Verify playback, seeking, sampling, and image decoding with several real recordings and supported Windows codecs.
- Test missing, moved, renamed, corrupt, and partially sampled media.
- Confirm all user data and reports stay local unless the user explicitly exports them.
- Verify source fingerprints and annotation-to-recording safeguards.
- Test long recordings, large frame counts, cancellation/error paths, and report paths.
- Document supported formats, known limitations, and backup/recovery behavior.

**Exit criteria:** repeatable tests on a clean Windows machine; no known silent data loss; actionable errors for unsupported/corrupt media; no unsubstantiated format compatibility claims.

## Phase 3 — annotated dataset and measurement quality

- Define the intended use cases before choosing any model: reticle localization, opponent localization, target association, and temporal overshoot/correction analysis are separate tasks.
- Write annotation instructions with consistent reticle center and opponent reference-point rules.
- Have at least two reviewers label overlapping clips; measure point-coordinate agreement as well as categorical-label agreement.
- Include varied maps, operators, scopes, UI settings, resolutions, frame rates, motion blur, effects, occlusion, and recording quality.
- Split evaluation by recording/player/session, not random adjacent frames, to prevent leakage.
- Record class coverage, exclusions, uncertainty, failure cases, and selection bias.

**Exit criteria:** a documented dataset protocol and baseline agreement results. No model accuracy claim before this phase.

## Phase 4 — visual detectors and temporal aim analysis

- Establish simple baseline methods and a reproducible held-out evaluation before adding a model.
- Evaluate reticle detection and opponent detection separately against human-marked ground truth.
- Track detector confidence and explicitly abstain when the frame is ambiguous or out of distribution.
- Only infer overshoot/undershoot/correction when consecutive observations, sampling timing, and target association support it.
- Compare automated outputs with human labels and report precision/recall or suitable task-specific errors, including failure slices.
- Never infer mouse input, recoil control, hit probability, or player skill from generic screen-space motion alone.

**Exit criteria:** measured held-out performance, documented failure modes, useful abstention behavior, and thresholds chosen from validation—not arbitrary confidence numbers.

## Phase 5 — coaching and settings recommendations

- Start with evidence-linked explanations based on validated observations, not generic AI text.
- Separate observed facts, possible interpretations, and suggested drills.
- Treat sensitivity recommendations as controlled experiments: change one setting at a time, preserve baseline values, record the result, and allow rollback.
- Do not promise that a particular sensitivity is objectively best or automatically change game settings.
- Test recommendations with users and compare against simple baselines; allow the coach to say “insufficient evidence.”

**Exit criteria:** each recommendation links to the source observations and uncertainty; no causal claim unsupported by an experiment; no fabricated metrics.

## Phase 6 — release engineering and trust

- Fix all known test/lint failures and obtain a green CI run.
- Build and install on a clean supported Windows environment.
- Verify first-run setup, optional dependencies, app launch, local storage, export, upgrade, and uninstall behavior.
- Add versioning, changelog, license/dependency review, and clear issue-reporting instructions.
- Complete privacy, fair-play, and data-retention review.
- Label the release accurately: manual review / experimental visual analysis until the validation gates above are met.

**Exit criteria:** repeatable clean installation, green automated checks, completed smoke-test checklist, transparent limitations, and no open release-blocking defects.

## Work in small chat-sized slices

1. One slice = one bounded user-visible behavior, tests, and docs.
2. Inspect the current branch and CI before editing.
3. Avoid merging pull requests without explicit approval.
4. Report what changed, what was tested, what is still blocked, and the next slice.
5. Never call the product “ready” based only on implemented features; readiness requires evidence against the exit criteria above.
