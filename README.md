# SiegeSense AI

**A local-first performance-coaching workspace for Rainbow Six Siege.**

SiegeSense AI is intended to help players understand their aim, movement, settings, and decision patterns through reviewable evidence—not vague advice or fabricated metrics.

> **Current status:** Early development. Session Review and Settings Lab now have local-storage workflows for sessions, timestamped observations, settings snapshots, and experiments. A recorded-video player UI is integrated; real-media codec verification and original-MVP data migration remain outstanding. Automatic vision analysis is not implemented. The Clip Annotation workspace can sample local recordings, label frames, display descriptive summaries, and export a local evaluation report, while the offline evaluation utilities summarize human-labelled frame coverage and reviewer agreement; any on-target share is descriptive only and is not aim accuracy.

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

See [architecture](docs/ARCHITECTURE.md), [product scope](docs/PRODUCT_SPEC.md), [roadmap](docs/ROADMAP.md), and [decisions](docs/DECISIONS.md).

## Development setup

From PowerShell on Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,vision]"
python main.py
```

If you prefer not to install the package in editable mode, set `PYTHONPATH=src` before launching. Editable install is the recommended path. The `vision` extra installs OpenCV for the local frame-sampling workflow.

Run checks:

```powershell
pytest
ruff check .
```

## Review a gameplay recording locally

The current annotation workflow is manual and intended to help build a responsibly validated dataset. It does not detect targets or measure aim automatically.

1. Launch SiegeSense AI and open **Clip Annotation**.
2. Choose **Select gameplay video** and select a local recording. Choose an output folder (or use the suggested `<video-name>_frames` folder).
3. Set the sampling interval and choose **Sample frames**. A shorter interval produces more images and uses more disk space; it does not guarantee precise measurement of a flick or reaction time.
4. Review the sampled frames and label only what is visible. Use **ambiguous** or **unusable** when the image does not support a confident label. Follow the [annotation guide](docs/ANNOTATION_GUIDE.md).
5. Save the annotation dataset locally. If you want to link a label to Session Review, select the matching session and use the link action; the app checks recording identity when the available paths/fingerprints permit it.
6. Use **Export local evaluation report…** to write a JSON summary. The report describes annotation coverage and, if supplied, reviewer agreement. It explicitly does not claim model performance or aim accuracy.

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
