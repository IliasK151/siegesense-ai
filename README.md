# SiegeSense AI

**A local-first performance-coaching workspace for Rainbow Six Siege.**

SiegeSense AI is intended to help players understand their aim, movement, settings, and decision patterns through reviewable evidence—not vague advice or fabricated metrics.

> **Current status:** Early development. Session Review and Settings Lab now have local-storage workflows for sessions, timestamped observations, settings snapshots, and experiments; experiments with a test snapshot are checked to ensure exactly one setting differs from baseline. A recorded-video player UI is integrated; real-media codec verification and original-MVP data migration remain outstanding. The app now has an initial, limited screen-space motion estimator for sampled frames using sparse optical flow. It reports visible feature displacement and a descriptive coherent-feature ratio; it does not detect opponents, measure mouse input, or score aim. The Clip Annotation workspace can sample local recordings, label frames, manually mark reticle/target points, display descriptive summaries, and export local evaluation, spatial-offset, and motion reports, while offline utilities summarize human-labelled frame coverage, reviewer agreement, and consecutive-frame label runs when sample timing is known; any on-target share is descriptive only and is not aim accuracy.

## Product principles

- **Evidence before advice.** Every measured metric should identify its source, units, and calculation method.
- **Local-first by default.** Gameplay recordings and personal session notes stay on the user's machine unless the user explicitly chooses otherwise.
- **Clear provenance.** Demo mode is visibly labelled and must never be mixed with real progress.
- **Human-controlled settings.** The app may propose experiments; users review and apply game settings themselves.
- **Fair play.** No game-memory reading, process injection, automated gameplay inputs, recoil control, or hidden competitive advantage.
- **Incremental engineering.** Small changes, tests, documented decisions, and reviewable pull requests.

## Workspace

1. Overview
2. Aim Lab
3. Movement
4. Settings Lab
5. Session Review
6. AI Coach
7. Preferences & Privacy

Overview, Session Review, and Settings Lab have initial functional workflows. Aim Lab, Movement, AI Coach, and Preferences & Privacy remain scaffolded. The recorded-video player still needs verification against representative real clips. Recorded-footage analysis and measurable coaching capabilities will be delivered as separate, testable increments.

## Technology

- Windows-first desktop application
- Python 3.10–3.12
- PySide6
- Local SQLite schema and session/settings services; Session Review and Settings Lab are connected to the service layer
- Safe migration from the original MVP remains blocked until its source and JSON schema are available
- Automated tests and CI checks

See [architecture](docs/ARCHITECTURE.md), [product scope](docs/PRODUCT_SPEC.md), [roadmap](docs/ROADMAP.md), [decisions](docs/DECISIONS.md), the [release-readiness gate](docs/RELEASE_READINESS.md), and the [implementation plan](docs/IMPLEMENTATION_PLAN.md) for the staged path to a validated coaching product.

## Windows preview package

A Windows x64 preview package can be built from GitHub Actions using the **Windows package** workflow (Actions → Windows package → Run workflow). If hosted runners are unavailable, the same intended local path is provided in `scripts/package_windows.ps1`; it installs the dependencies, runs tests and lint, builds with PyInstaller, and smoke-tests the packaged executable before creating `dist/SiegeSenseAI-Windows-x64.zip`. The local script has been added but still needs to be executed on a supported Windows machine. Neither a successful startup smoke test nor a package build verifies video codecs or coaching accuracy.

For the fastest path to trying your own recording, follow the [Windows clip-testing guide](docs/TEST_YOUR_OWN_SIEGE_CLIP.md). It explains how to set up, launch, check, and package the preview. The artifact remains an early local recording-review and manual-annotation prototype, not a validated automatic aim coach; complete the [release-readiness checks](docs/RELEASE_READINESS.md) before distributing it as a reliable performance tool.

## Development setup

**Simplest Windows path:** after extracting the source ZIP, double-click `START_SIEGESENSE.bat`. On first launch, it checks for the Python Launcher, runs the setup script if the project environment is missing, and then starts the app. It needs Python 3.12 for Windows and an internet connection for the initial dependency install. To run tests and lint, double-click `CHECK_SIEGESENSE.bat`.

For a PowerShell workflow, use:

```powershell
.\scripts\setup_windows.ps1
.\scripts\run_windows.ps1
```

The setup script uses Python 3.12, creates a project-local virtual environment, and installs the application plus developer and vision dependencies. If you prefer to run the steps manually:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,vision]"
python main.py
```

Run local checks through `.\scripts\check_windows.ps1`, or activate the virtual environment and use `python -m pytest` followed by `python -m ruff check .`. The `vision` extra installs OpenCV for local frame sampling.

## Review a gameplay recording locally

The annotation labels remain manual. The optional screen-space motion report estimates visible feature movement between adjacent sampled frames, but does not detect targets or measure aim automatically. The annotation workflow now supports optional click-to-mark reticle/target coordinates on a frame preview, normalized against the full source image even when the preview is letterboxed. It displays descriptive spatial offsets in the UI and JSON evaluation report; these are human-marked geometric measurements, not automatic detections or aim-accuracy scores.

1. Launch SiegeSense AI and open **Clip Annotation**.
2. Choose **Select gameplay video** and select a local recording. Choose an output folder (or use the suggested `<video-name>_frames` folder).
3. Set the sampling interval and choose **Sample frames**. A shorter interval produces more images and uses more disk space; it does not guarantee precise measurement of a flick or reaction time. The manifest records requested seek-grid timestamps separately from OpenCV's reported post-read position; the latter is backend-dependent and is not guaranteed to be a true presentation timestamp.
4. Review the sampled frames and label only what is visible. Use **ambiguous** or **unusable** when the image does not support a confident label. Follow the [annotation guide](docs/ANNOTATION_GUIDE.md).
5. Save the annotation dataset locally. If you want to link a label to Session Review, select the matching session and use the link action; the app checks recording identity when the available paths/fingerprints permit it.
6. Use **Export local evaluation report…** to write a JSON summary of annotation coverage and, if supplied, reviewer agreement. Optionally choose **Analyze screen-space motion…** to export a second JSON report of visible feature motion between adjacent sampled frames. Motion analysis uses resized images, evenly samples eligible frame pairs when capped, and reports analyzed, subsampled, unusable, and timestamp-gap pair counts. It can be affected by camera movement, recoil animation, moving objects, effects, and compression; it is not mouse input, aim accuracy, or a skill score.

**Keep the evidence honest:** frame labels are human observations, not ground truth for your overall skill. A manually selected on-target share is not accuracy, hit probability, or a representative performance score. Store recordings, sampled frames, annotations, and reports outside version control; they can contain personal information.

## Project workflow

- Use [GitHub Issues](https://github.com/IliasK151/siegesense-ai/issues) for tasks and defects.
- Implement substantial changes on a focused branch.
- Open a pull request with tests, screenshots for UI changes, and honest verification notes.
- Keep session data and recordings out of Git.

## Fair-play and privacy boundary

SiegeSense AI is a coaching and review tool, not a gameplay automation tool. It must not read protected game memory, modify the game, inject into the game process, or automate aiming or movement. Screen capture and any future live mode must be opt-in, visible, locally controlled, and reviewed against current game rules before release.

## License

No license has been selected yet. Until one is added, all rights are reserved by default.


The manual sequence summary also counts adjacent off-target→on-target and on-target→off-target label transitions when the sampling interval is known. These are counts of consecutive reviewed labels only; gaps, missing labels, and unknown intervals are not inferred, and the counts are not validated aim-correction metrics.
