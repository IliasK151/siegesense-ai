# Product Specification

## Purpose

Help a player improve through structured review of aim, movement, and sensitivity/settings experiments. The app should feel like a polished performance analytics product, not a generic AI chat wrapper.

## Core coaching concept

The intended product remains an aim, movement, playstyle, and settings coach for Rainbow Six Siege. The current manual-analysis prototype is an early stepping stone, not a replacement for this goal.

The intended end state is to help a player understand patterns such as:

- Reticle-to-opponent alignment and target acquisition in recorded footage.
- Possible overflicks, underflicks, corrections, target switches, and settling behaviour when the video contains enough clear, correctly timed evidence.
- Movement and peeking patterns visible in the recording, alongside user notes about decisions and positioning.
- Repeatable player-specific settings experiments, including sensitivity and ADS values, with clear rationale, trade-offs, confidence, and a way to compare results.
- Session-to-session trends that account for recording quality, sample sizes, game settings, scope, and uncertainty.

Implementation order is deliberate: first make local recording review dependable; then develop isolated reticle/opponent and event-analysis prototypes; measure them on player-owned recordings with independently reviewed reference labels; and only then use validated results to drive coaching. When a recording cannot support a conclusion, the coach must say that evidence is insufficient rather than fabricate a result.

The product should analyze saved recordings first. It must not need to inject into Siege, read protected game memory, automate aiming or movement, or silently change game settings. The player remains in control of any settings experiment.

## Audience and primary job

A PC Rainbow Six Siege player who wants to understand recurring performance patterns and test changes methodically without being told to change settings based on guesses.

## UX direction

- Bright, professional interface: warm whites, soft grey surfaces, charcoal text, restrained violet accent.
- Dense but readable analytics; balanced dashboard of metrics, trends, coaching priorities, and recent sessions.
- Compact collapsible left navigation; icons and tooltips when collapsed.
- Accessible contrast, keyboard navigation, clear empty/loading/error states, and responsive resizing.
- Demo mode must be unmistakable and isolated from real records.

## Main areas

### Overview
Session summary, trend visualisations, coaching priorities, recent reviews, and data-quality/provenance indicators.

### Aim Lab
Structured aim observations and, when supported by validated footage analysis, measures such as target-transition behaviour. Do not present screen-space estimates as true mouse input or world-space aim without a defensible method.

### Movement
Review observations about peeking, positioning, movement consistency, and recorded events. Avoid unsupported automatic judgments.

### Settings Lab
Record baseline settings, one-variable-at-a-time experiments, expected outcome, sample size, results, and decision. Recommendations are proposals, never silent changes to game configuration.

### Session Review
Recorded-footage playback, timestamps, user-created observations, tags, and links between observations and coaching notes.

### AI Coach
Explain evidence, confidence, limitations, and actionable next steps. Every conclusion must distinguish measured facts from hypotheses.

### Preferences & Privacy
Capture controls, local data management, demo-mode controls, and transparent privacy settings.

## Data rules

- Every metric needs a name, unit, source, calculation method, and validity state.
- Demo records must carry an explicit demo flag and must never be aggregated into real history.
- Missing data is represented as missing—not zero.
- Recommendations include supporting observations and uncertainty.
- No claim of AI or vision capability before its implementation and tests exist.

## Out of scope

- Aimbot, recoil control, macros, automated movement, or automated gameplay inputs.
- Game-memory inspection, process injection, or tampering with protected game processes.
- Unreviewed always-on capture or uploading footage by default.
- Unsupported claims about rank prediction or performance improvements.

## Initial milestone acceptance criteria

- All planned navigation destinations exist and have intentional empty/demo states.
- Shared design tokens and reusable components are established.
- Demo mode is clearly labelled and isolated from user data.
- Architecture separates UI, domain models, persistence, and analysis.
- A test suite covers core data/provenance rules.
- README setup instructions match the actual repository contents.
