# SiegeSense AI

**A local-first performance-coaching workspace for Rainbow Six Siege.**

SiegeSense AI is intended to help players understand their aim, movement, settings, and decision patterns through reviewable evidence—not vague advice or fabricated metrics.

> **Current status:** Early MVP / architecture and product foundations. This repository is the source of truth for requirements, implementation, issues, and decisions. Features are not considered implemented until code and verification support that claim.

## Product principles

- **Evidence before advice.** Every measured metric should identify its source, units, and calculation method.
- **Local-first by default.** Gameplay recordings and personal session notes stay on the user's machine unless the user explicitly chooses otherwise.
- **Clear provenance.** Demo data is visibly labelled and never mixed with real session records.
- **Human-controlled settings.** The app may propose experiments; users review and apply game settings themselves.
- **Fair play.** No game-memory reading, process injection, automated gameplay inputs, recoil control, or hidden competitive advantage. Any live-screen integration must be reviewed separately for game rules and privacy.
- **Incremental engineering.** Small changes, tests, documented decisions, and reviewable pull requests.

## Planned workspace

1. Overview
2. Aim Lab
3. Movement
4. Settings Lab
5. Session Review
6. AI Coach
7. Preferences & Privacy

The initial milestone is a maintainable desktop shell and design system with honest demo data. Recorded-footage analysis and measurable coaching capabilities follow as separate, testable increments.

## Technology direction

- Windows-first desktop application
- Python and PySide6
- Local persistence, with a versioned database schema planned
- Automated tests and CI checks

The exact architecture is documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development setup

Python 3.10–3.12 is the initial target until CI validates a broader range.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

These commands assume the MVP entry point and requirements file have been added to the checkout. See the issues and roadmap for the current implementation state.

## Project workflow

- [Roadmap](docs/ROADMAP.md)
- [Product scope](docs/PRODUCT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Decision log](docs/DECISIONS.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

Use GitHub Issues for tasks and defects. Implement substantial work on a branch and open a pull request with tests, screenshots for UI changes, and clear verification notes.

## Fair-play and privacy boundary

SiegeSense AI is a coaching and review tool, not a gameplay automation tool. It must not read protected game memory, modify the game, inject into the game process, or automate aiming or movement. Screen capture and any future live mode must be opt-in, visible, locally controlled, and checked against current game rules before release.

## License

No license has been selected yet. Until one is added, all rights are reserved by default.
