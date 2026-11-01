# SiegeSense

A live coach for **Rainbow Six Siege (PC)**. SiegeSense watches your screen and your own mouse while you play ranked or warm up, measures your mechanics (flicks, overshoot, reaction time) and round habits, and coaches you between rounds. It runs entirely on your PC and costs nothing to use.

> **Fair play:** SiegeSense never reads game memory, injects code, hooks the game or sends input. It only sees what you see and what you do, and it never shows enemy information.

## Status

| Build step | What it delivers | Status |
|---|---|---|
| 1 | App shell, design system, engine link, status lights, setup wizard | ✅ Done |
| 2 | Mouse input tracking, aim metrics, 360° calibration, Warm-up Mode | ✅ Done |
| 3 | Screen capture, HUD reading (kill feed, rounds, deaths), death clips | ⏳ Next |
| 4 | Coach brain, in-game overlay, voice, local AI, match report → Live Mode | |
| 5 | Session Review and Progress screens | |
| 6 | Windows installer and settings polish | |

Design spec: [`docs/superpowers/specs/2026-11-01-siegesense-design.md`](docs/superpowers/specs/2026-11-01-siegesense-design.md)

## Project layout

```
app/        Electron + React + TypeScript desktop app (UI, overlay)
engine/     Python engine: capture, analysis, coaching, local storage
protocol/   Sample messages: the contract between app and engine
docs/       Specs and implementation plans
```

The app starts the engine as a background process and talks to it over an authenticated WebSocket on `127.0.0.1`. Your data lives in a local SQLite database in the app's user-data folder.

## Running it on Windows (development)

Requirements: **Python 3.12+** (with the `py` launcher) and **Node.js 22+**.

```powershell
# 1. Engine
cd engine
py -3 -m pip install -e ".[dev]"

# 2. App
cd ..\app
npm install
npm run dev
```

The app window opens and launches the engine automatically. Run Siege in **Borderless** display mode so the in-game overlay can show (coming in step 4).

## Using Warm-up Mode

1. Run Siege in **Borderless** so the small overlay can show in the top-right corner.
2. *(Recommended, once)* **Settings → 360° calibration → Calibrate.** In Siege, aim at a sharp edge, press **F8**, turn exactly one full circle to the right, stop on the same edge, press **F8**. Repeat 3 times. This makes every aim number exact for your sensitivity.
3. Load the **Shooting Range** or **T-Hunt**, then in SiegeSense open **Warm-up → Start warm-up**.
4. Flick between targets like you normally would. Each flick is tagged **Clean**, **Correction** (you adjusted after the flick) or **Overshoot** (you went past the target, came back and shot).
5. Press **Stop** for your warm-up score (needs 5+ flicks) and a drill to work on (needs 10+ flicks). Scores are kept so you can compare days.

What it measures: flick speed and size, overshoot and correction rates, spray vs tap, shooting while moving, strafe switches, crouch spam, and crosshair jitter while aiming down sights. It reads only your own mouse and keyboard; nothing is sent to the game.

## Tests

```bash
# Engine
cd engine && pytest && ruff check .

# App
cd app && npm run typecheck && npm test

# End-to-end (real engine + UI in Chromium, with a replayed warm-up session)
cd app && npm run e2e
```
