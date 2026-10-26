# SiegeSense Annotation Guide (v1)

This guide defines manual labels for sampled frames from user-owned Rainbow Six Siege recordings. Labels describe only what is visible in the frame; they do not infer intent, skill, or whether an action was correct.

## Before annotating

- Use a local recording you own or are authorized to review.
- Confirm the manifest belongs to the intended source video.
- Use the same label definitions across reviewers.
- If the image is unreadable, do not guess: use `unusable_frame` or `ambiguous`.
- Add a short note when context from adjacent frames is required. A single still frame cannot establish motion direction or timing by itself.

## Labels

| Label | Use when | Do not use when |
|---|---|---|
| `target_transition` | A sampled frame is selected as a point associated with a visible transition between targets, usually with surrounding frames available for review. | The still frame alone does not establish a transition and no surrounding footage was reviewed. |
| `crosshair_on_target` | The visible reticle/crosshair appears to overlap the visible opponent's body or hitbox area in this frame. | The opponent is occluded, the reticle is not visible, or overlap cannot be judged confidently. |
| `crosshair_off_target` | The visible reticle is clearly separated from a visible opponent in this frame. | Either the reticle or opponent is too unclear to judge. |
| `movement_start` | A reviewed sequence indicates the beginning of a movement event; record the event timestamp and note what visual cue supports it. | Only a single isolated still is available with no temporal context. |
| `movement_stop` | A reviewed sequence indicates the end of a movement event; record the event timestamp and note what visual cue supports it. | Only a single isolated still is available with no temporal context. |
| `ambiguous` | More than one label could reasonably apply, or the available evidence is insufficient. Explain the uncertainty in the note. | The frame clearly meets a label definition. |
| `unusable_frame` | Compression, blur, obstruction, missing HUD/reticle, or capture artifacts prevent reliable annotation. | The frame is readable and supports a defined label. |

## Review procedure

1. Inspect the selected frame and nearby frames where the label depends on timing.
2. Choose one label only; add a short evidence note rather than a skill judgment.
3. Record annotator identity consistently across the dataset.
4. For agreement checks, have reviewers label the same sampled frames independently before discussing disagreements.
5. Resolve disagreements only after the independent labels have been saved. Preserve the original datasets for auditability.
6. Keep all frames from one source recording in a single train, tuning, or evaluation split. Do not randomly split adjacent frames across splits.

## Optional spatial point marks

The Clip Annotation frame preview can store two optional points for a labelled frame:

- **Reticle:** mark the center of the visible reticle/crosshair.
- **Target:** mark one consistent visual reference point on the visible opponent. For consistency, use the same convention across the dataset (for example, the center of the visible torso); do not imply this is an exact game hitbox.

Choose **Mark reticle** or **Mark target**, then click inside the displayed image. The surrounding letterboxed margins are not clickable. Coordinates are normalized to the full source frame, so resizing the preview does not change the underlying point location. Point marks are stored with the current annotation and can be edited or cleared.

The spatial report calculates target-minus-reticle horizontal offset as a percentage of frame width, vertical offset as a percentage of frame height, and straight-line separation as a percentage of the frame diagonal. Positive horizontal offset means the marked target point is to the right of the reticle; positive vertical offset means it is below the reticle. These calculations describe only the points selected by a human reviewer. They do not detect targets, establish a hitbox, infer mouse movement, diagnose overshoot from one frame, or predict hit probability.

## Limits and reporting

- Report the number of recordings, labelled frames, and count for every label, including zero-count labels.
- Report exact frame agreement and Cohen's kappa only on frames labelled by both reviewers. Always include overlap count; a statistic without its sample size is not informative.
- Kappa can be undefined for degenerate label distributions. Treat that as unavailable, not as perfect agreement.
- Agreement statistics measure consistency, not correctness. A reviewer can be consistently wrong.
- These labels are a foundation for later validation, not proof that automatic aim or movement detection works.
- Evaluation reports may summarize runs of consecutive manually labelled on-target/off-target frames when the sampling interval is known. These are sampled-frame spans, not precise event durations; missing or unlabelled samples break a run, and unknown intervals must not be converted into timing claims.


When the sampling interval is known, the sequence summary may count adjacent off-target→on-target and on-target→off-target label transitions. Counts include only consecutive annotated samples exactly one interval apart; they do not establish why the reticle changed relative to a target and are not a validated aim-correction metric.
