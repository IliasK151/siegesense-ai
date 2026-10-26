# Coaching tags and evidence limits

SiegeSense AI currently uses **explicit manual tags** to group review observations into practice prompts. It does not inspect note text to infer a weakness, and these prompts are not automatic detections.

## Supported coaching tags

Use these tags in Session Review (aliases are accepted):

| Tag | Aliases accepted | What the prompt focuses on |
|---|---|---|
| `overflick` | `overshoot`, `overshot`, `over flick` | Record the first reticle endpoint before a correction |
| `underflick` | `undershoot`, `undershot`, `under flick` | Record whether the first endpoint stops short |
| `target-switch` | `target switching`, `target transition` | Review planned target choice and acquisition |
| `crosshair-placement` | `placement`, `pre aim`, `preaim` | Separate pre-aim position from reactive aim |
| `correction` | `micro correction`, `double correction` | Count visible corrections after the first endpoint |
| `recoil` | `recoil control`, `spray control` | Isolate recoil control from target acquisition |
| `movement` | `peek`, `wide peek`, `overpeek` | Review exposure and peek path |
| `positioning` | `cover`, `angle` | Review cover, escape routes, and angle choice |
| `decision` | `decision making`, `timing decision` | Compare choices with information available at the time |

Other tags (for example, a weapon or scope name) remain useful filters but do not create a coaching claim.

## Evidence levels

- **Single note:** one manually tagged instance; only a question to review.
- **Repeated in one session:** multiple notes in one session; verify whether it recurs before changing settings.
- **Recurring across sessions:** multiple manually tagged observations across sessions; worth testing in a controlled drill, but not proof of cause.

Suggestions are intentionally conservative. Keep settings unchanged during a short evidence-gathering block, compare similar situations, and change one variable only when repeated evidence supports an experiment. The app does not measure mouse input, automatically detect opponents, or infer overshoot from screen-motion summaries.
