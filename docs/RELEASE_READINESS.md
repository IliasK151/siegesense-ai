# Release readiness and accuracy gate

## Current decision

**Status: preview build only — not a validated aim coach.**

The desktop app has usable local workflows for session notes, settings snapshots/experiments, video frame sampling, manual frame annotation, and descriptive optical-flow reports. The motion report is not a mouse-input measurement, reticle detector, opponent detector, or aim score. Do not advertise precision coaching until the validation gates below are met.

## Engineering checks

- [ ] CI tests and lint pass on Python 3.10, 3.11, and 3.12 on Windows.
- [x] The Windows packaging workflow builds on a clean GitHub Actions runner.
- [ ] The packaged-app offscreen smoke test passes reliably; recent runs exposed a failure and diagnostic logging is being improved.
- [ ] Install and launch the packaged app on a separate clean Windows machine with no Python environment installed.
- [ ] Verify supported video playback with representative recordings and codecs.
- [ ] Verify database creation, restart persistence, and error messaging when the local data directory is unavailable.
- [ ] Verify sampling on constant-frame-rate and variable-frame-rate recordings; compare exported timestamps to the media player's actual timestamps.
- [ ] Audit keyboard navigation, scaling, minimum window size, and accessibility.
- [ ] Review local data paths, overwrite protection, export destinations, and privacy wording.

## Evidence required before claiming accurate aim coaching

1. **Define each claim.** For every metric, document its unit, exact algorithm, required recording conditions, and known failure modes.
2. **Collect a consented evaluation set.** Use player-owned recordings across different resolutions, frame rates, maps, scopes, HUD settings, and compression levels. Keep recordings local unless participants explicitly consent otherwise.
3. **Create reference labels.** Annotate visible reticle location, opponent/target visibility, target transitions, and relevant timestamps. Have a second reviewer label a subset and report agreement.
4. **Split by entire recording/session.** Do not allow frames from the same recording into both tuning and held-out evaluation data.
5. **Measure detector performance.** For each detection task, report precision, recall, false-positive examples, false-negative examples, sample size, and confidence intervals where appropriate. Compare timing estimates with manual references and report the error distribution.
6. **Check failure conditions.** Test low visibility, motion blur, occlusion, recoil animation, camera movement, rapid turns, UI overlays, and scene transitions. If input quality is insufficient, return “unavailable” rather than guessing.
7. **Validate coaching usefulness.** Check recommendations against repeated sessions and controlled one-variable-at-a-time settings experiments. A correlation in one clip is not proof that a setting caused improvement.
8. **Release gate.** Publish a model/algorithm card with measured results and limitations. Do not call a metric “accurate” until it meets predeclared acceptance thresholds on held-out recordings.

## Fair-play and privacy gate

- No protected game-memory reading, process injection, automated gameplay inputs, recoil automation, or hidden capture.
- Recorded-video analysis is user-initiated and local-first.
- Any future live capture must be opt-in, visible, stoppable, and reviewed against current game rules and platform policies.
- Do not upload recordings, frames, or annotations without explicit user action and clear disclosure.

## Packaging workflow

The Windows packaging workflow can be started manually from GitHub Actions or by pushing a version tag. It runs tests and lint before building a Windows x64 onedir package. The generated artifact is a preview package until the clean-machine install and media playback checks above are completed.
