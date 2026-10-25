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


## Implemented annotation data layer

`src/siegesense/vision/annotations.py` now provides a local annotation store keyed to a sampling manifest's source SHA-256. Supported human labels are target transition, crosshair on/off target, movement start/stop, ambiguous, and unusable frame. An annotation must reference an exact sampled frame from the manifest. JSON datasets are schema-versioned and saved via a temporary file followed by replacement. Loading against a different source fingerprint is rejected. Dataset loading also rejects duplicate annotation IDs and frame filenames that are not local basenames, preventing malformed records and path traversal. This is a data layer only; a graphical annotation UI is still pending.


## Annotation workspace

The desktop shell now includes a Clip Annotation page. It can sample a user-selected local video into a separate output folder, then opens the generated local `sampling_manifest.json`, lists sampled frames, previews the selected image, and saves a manual label plus annotator and optional note to `annotations.json` beside the manifest. The sampling interval is user-configurable; shorter intervals produce more files but do not by themselves establish precise aim timing. Saved annotations can be selected, edited, and deleted through the UI. Editing preserves the annotation ID and frame reference while updating the label, annotator, and note. The page validates frame filenames as local basenames and uses the annotation service's source-fingerprint checks. A UI integration test exercises loading a generated frame and persisting a label. No automatic image interpretation is performed.


## Linking manual annotations to session review

The Clip Annotation page can attach a selected saved annotation to a real local Session Review session as a timestamped observation. The observation includes the annotation label, optional note, source frame filename, and tags (`clip-annotation`, the label, and a stable annotation ID tag). Linking checks the target session for that stable tag first and blocks duplicate links to the same session. Movement-start/stop labels are categorized as movement; other labels are categorized as aim. This is a user-initiated copy into the session observation store; the annotation dataset remains the source annotation record. No automatic model prediction is implied.


### Recording identity guard

When a Session Review session has a recording path and the loaded sampling manifest includes a source path, annotation linking compares their resolved local paths. If they point to different files, linking is blocked with a visible explanation. This is a conservative local-path check, not cryptographic proof that two files with different paths contain different video or that two matching paths have unchanged contents. Sessions without a stored media path remain linkable; future work may persist and compare a source fingerprint for stronger provenance.


## Opening linked frames from Session Review

Session Review includes an explicit action for the selected observation. For observations tagged with a stable `annotation-id:` value, the app looks for that annotation in the currently loaded local annotation dataset and locates the frame by timestamp and filename. If the dataset or frame is not loaded, the app directs the user to load the matching sampling manifest rather than guessing. Ordinary observations without annotation IDs remain unaffected.


## Session recording provenance

Session records support an optional SHA-256 fingerprint for their linked media. Fingerprinting is explicit and chunked through `SessionService.fingerprint_session_media`, so importing or creating a session does not unexpectedly hash a large video on the UI thread. The database migrates older local stores to schema version 2 without discarding session data. When both a session and annotation manifest have fingerprints, linking requires an exact match; when either fingerprint is unavailable, the UI falls back to the existing conservative resolved-path check. A matching hash is stronger evidence of file identity than a path, while path-only matching is not proof that file contents are unchanged.


## Evaluation dataset hygiene prototype

`src/siegesense/vision/evaluation.py` provides a first reporting/validation utility for named annotation JSON datasets. It summarizes annotation counts by human label and rejects reuse of the same source SHA-256 across separate dataset entries, guarding against recording-level leakage between training and evaluation. It does not train a model or claim detection accuracy. Before any model evaluation, curate multiple distinct recordings, agree on annotation definitions, and record annotator agreement and exclusions.


## Annotation guide and reviewer agreement

The human-label definitions and review protocol are in [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md). The evaluation helper now compares two annotation JSON files on the same source recording and exact overlapping sampled frames, reporting overlap count, exact agreement, observed agreement, and Cohen's kappa when defined. It rejects duplicate labels for the same sampled frame within either reviewer dataset instead of silently choosing one. Agreement is not a correctness score; model validation still requires separate held-out recordings and measurable detection metrics.


## Local evaluation report export

`write_evaluation_report(output_path, datasets, annotator_pairs=...)` writes a versioned local JSON report containing label coverage, reviewer agreement for overlapping frames, generation time, and explicit limitations. The helper refuses to overwrite any annotation dataset passed as an input. It explicitly marks `model_performance_evaluated` as false: this report is about annotation readiness, not detector accuracy.


### Run the local evaluation report CLI

After installing the project in editable mode, create a coverage report for a named dataset:

```bash
python -m siegesense.vision.report --dataset heldout=path/to/annotations.json --output path/to/evaluation-report.json
```

To include an independently annotated subset, add a reviewer-pair argument (both files must identify the same source recording and share labelled frame keys):

```bash
python -m siegesense.vision.report --dataset heldout=path/to/annotations.json --agreement double_review=path/to/reviewer-a.json,path/to/reviewer-b.json --output path/to/evaluation-report.json
```

Repeat `--dataset NAME=PATH` for distinct recording-level splits. The command exits with a non-zero status on invalid inputs and never claims model performance.


## Descriptive aim-frame summary

Evaluation reports and the Clip Annotation workspace now include counts of manually labelled crosshair-on-target, crosshair-off-target, target-transition, ambiguous, and unusable frames. When at least one on-target/off-target frame exists, the report includes the on-target share among those selected, determinate labels. This is strictly a summary of frames a human chose to label: it is **not** aim accuracy, hit probability, or a representative estimate of gameplay performance. Sampling strategy and annotator selection can bias this share. Automatic detection and time-to-target measurement remain unimplemented pending higher-resolution clips and validation against reviewed events.
