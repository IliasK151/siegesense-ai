# SiegeSense — Design Spec

**Date:** 2026-11-01
**Status:** Draft, awaiting owner review

## 1. Purpose

SiegeSense is a Windows desktop app that watches a Rainbow Six Siege (PC) player **live** — in ranked and in warm-ups — and coaches them to improve. It measures the player's own mechanics (aim, overshoot, flicks, movement) and round behaviour (deaths, trades, timing), then delivers coaching at natural breaks in the game.

- **First user:** the owner, testing on their own PC (GTX 1080 Ti, 11 GB VRAM).
- **Later:** a public download that anyone can install and configure with their own settings.
- **Cost to run:** $0. All analysis and AI run locally. No paid API is required.

### Success criteria (v1)

1. The owner can install the app, finish setup in under 5 minutes, press **Start Live Mode** and play ranked with no noticeable FPS loss (target: < 5% FPS drop).
2. Every death the player suffers is detected, clipped and annotated with at least one specific, data-backed coaching note.
3. Aim metrics (overshoot rate, flick speed, reaction time) are measured from real input and shown live in Warm-up mode.
4. The coach speaks only at breaks (death, between rounds, prep, end of match) or when the player asks via push-to-talk.

## 2. Fair-play rules (non-negotiable)

- The app **never** reads game memory, injects code, hooks the game process or modifies game files.
- It sees only what the player sees (screen capture) and what the player does (their own mouse/keyboard via Windows Raw Input).
- It **never** reveals information the player could not see themselves: no enemy positions, no markers, no wallhack-style overlays, no aim assistance of any kind.
- The coach gives no tactical callouts mid-round. Coaching is delivered only at breaks.

## 3. Architecture

```
┌────────────────────────── Windows PC ───────────────────────────┐
│                                                                 │
│  Electron App (React + TypeScript)                              │
│   ├─ Main window: Setup, Home, Live, Review, Progress, Settings  │
│   └─ Overlay window: transparent, click-through, always-on-top  │
│                │  WebSocket (localhost, per-launch auth token)  │
│                ▼                                                │
│  Engine (Python, bundled with PyInstaller, started by the app)  │
│   ├─ GameWatcher    – detects RainbowSix process/window         │
│   ├─ InputTracker   – Raw Input → mouse/keyboard event stream   │
│   ├─ ScreenCapture  – Windows Graphics Capture, rolling buffer  │
│   ├─ HudReader      – kill feed, round phase, timer, health     │
│   ├─ Mechanics      – flicks, overshoot, reaction, movement     │
│   ├─ RoundTracker   – builds the round/match timeline           │
│   ├─ ClipWriter     – saves death clips to disk                 │
│   ├─ CoachBrain     – rules → prioritised coaching tips         │
│   ├─ LocalLLM       – optional Ollama model for phrasing & Q&A  │
│   ├─ Voice          – Whisper (STT) + Piper (TTS), offline      │
│   └─ Store          – SQLite + clips folder                     │
└─────────────────────────────────────────────────────────────────┘
```

### Repository layout

```
app/        Electron + React + TypeScript UI
engine/     Python engine (package: siegesense_engine)
docs/       Specs, plans, decisions
```

### Communication

- The Electron main process launches the engine as a child process and passes it a random auth token and a port.
- The UI and the engine exchange JSON messages over a localhost WebSocket.
  - Engine → UI: `status`, `event`, `metrics`, `tip`, `round_summary`, `match_report`.
  - UI → Engine: `start_live`, `stop_live`, `start_warmup`, `config_update`, `ask` (text question), `ptt_start` / `ptt_stop`.
- Every message has a `type`, a `ts` (monotonic ms) and a typed payload. The schemas are defined once in `engine/` and mirrored as TypeScript types in `app/`, kept in sync by a contract test.

## 4. Engine components

Each component has one job, a small interface, and a **fake** implementation, so everything except the real Windows capture/input can be tested on any OS.

### 4.1 GameWatcher
- Polls for `RainbowSix.exe` / `RainbowSix_BE.exe` and finds the game window and its resolution.
- Reports `game_running`, `game_focused` and `display_mode` (warns when the game is in exclusive fullscreen, because the overlay cannot show there).

### 4.2 InputTracker
- Windows Raw Input (`RIDEV_INPUTSINK`) on its own thread: raw mouse deltas (up to 1000 Hz+), mouse buttons and the relevant keys (A/D strafe, crouch, lean, ADS).
- Reads only the player's own device input. Never sends input.
- Turns raw counts into **degrees** using the player's profile:
  - Imported from Siege's `GameSettings.ini` (yaw/pitch sensitivity, ADS multipliers, X-factor, FOV) plus the mouse DPI the player enters.
  - **360° calibration** (recommended): the player turns exactly one full rotation in-game and the app records the counts. This is the ground truth and overrides the formula-based estimate.

### 4.3 ScreenCapture
- Windows Graphics Capture of the game window at 30 fps (configurable 20–60), with a dxcam fallback.
- Keeps a rolling **15-second ring buffer** of downscaled frames in memory for clips.
- Hands HUD crops to HudReader at a lower rate (about 10 Hz) to save CPU.

### 4.4 HudReader
- Reads HUD regions defined in normalised coordinates, adjusted for resolution and HUD scale:
  - **Kill feed:** OCR (RapidOCR, ONNX, runs on CPU) + fuzzy match against the player's name and recently seen names; headshot icon by template match. Produces `kill` events (`killer`, `victim`, `headshot`, `involves_me`).
  - **Round phase:** prep / action / round over, from the timer region and phase banners.
  - **Round timer** and **score**.
  - **Own health** (digits) and **alive / dead / spectating** state.
- Each reading carries a confidence score. A death is confirmed only when two signals agree (a kill-feed entry where the player is the victim, plus the dead/spectator HUD state).
- The **HUD check** in setup runs HudReader on one live screenshot and shows the player what it read, so they can confirm or adjust.

### 4.5 Mechanics
Works on the stream of input deltas converted to degrees. Definitions:
- **Flick:** a movement segment whose peak angular speed is above a threshold (default 300°/s) and whose amplitude is at least 5°.
- **Overshoot / correction:** within 250 ms after the flick's peak, a reversal in the main direction of at least 10% of the flick amplitude. Reported as *correction*, and counted as *overshoot* when a shot follows within 400 ms.
- **Micro-jitter:** high-frequency direction changes under 1° while ADS.
- **Reaction time** (Warm-up mode): time from target appearing (frame change in the centre region) to the first flick.
- **Spray vs tap:** length of continuous fire bursts.
- **Movement habits:** strafe frequency, shooting while moving, crouch-spam, re-peek (returning to the same view angle within 3 s after a fight).
- Output: rolling per-round and per-match aggregates, plus per-event samples tied to timestamps.

### 4.6 RoundTracker
- Combines HudReader and Mechanics into a timeline: match → rounds → events.
- Works out round facts: time alive, first death / first kill, traded / traded-a-teammate (a kill within 5 s), alone-at-death (no teammate kill-feed activity nearby; best-effort), and the player's mechanics during the round.

### 4.7 ClipWriter
- On a confirmed death, encodes the last 10 s from the ring buffer (plus 2 s after) to MP4 in a background thread, with the input trace saved alongside.
- Limits disk use (default 5 GB, oldest clips deleted first).

### 4.8 CoachBrain (rule-based, always on)
- A library of rules. Each rule has: a **condition** over round/match/session stats, a **priority**, a **cooldown**, a **tip template** and the **evidence** it is based on.
- Examples:
  - Overshoot rate > 30% over the last 10 flicks → "You're overshooting your flicks…"
  - First death in ≥ 3 of the last 5 attack rounds → "Stop taking first contact alone…"
  - Re-peeked the same angle after a kill ≥ 2 times → "After a kill, reposition…"
- Delivery slots:
  - **On death:** 1 tip about that death.
  - **Between rounds / prep:** 1 focus for next round.
  - **End of match:** match report (top 3 problems, best moment, one drill).
- Never more than one spoken tip per break. Repeated issues are merged ("still overshooting, 3rd round in a row").
- Every tip links to its evidence (the clip, the metrics), shown in Review.

### 4.9 LocalLLM (optional, default on when it can run)
- Ollama with a small model (default: a 3–4B instruct model, 4-bit; about 3 GB of VRAM, which fits beside Siege on a 1080 Ti).
- Used for: rewording CoachBrain tips into natural coaching, writing the match report, and answering push-to-talk questions.
- **Grounded:** the prompt contains only structured facts from the session; the model is told not to invent data. If its answer mentions numbers not in the facts, the plain CoachBrain text is used instead.
- Runs only at breaks. Turned off automatically if it isn't installed, or if it doesn't answer within 4 s, falling back to CoachBrain text.
- Optional cloud AI provider (bring your own key) is available in Settings, off by default.

### 4.10 Voice
- **Push-to-talk** key (default: a configurable key that doesn't clash with Siege's bindings) → faster-whisper (small model, CPU) → question → LocalLLM, or a keyword-based CoachBrain answer if the LLM is off.
- **TTS:** Piper, offline. Volume and voice are configurable, and it can be switched off (text only).

### 4.11 Store
- SQLite tables: `profiles`, `sessions`, `matches`, `rounds`, `events`, `deaths` (clip path), `metric_samples`, `tips`.
- Everything stays on the PC. Nothing is uploaded.

## 5. Modes

- **Live Mode (ranked / any match):** all components on, coach at breaks.
- **Warm-up Mode (Shooting Range, T-Hunt, custom vs bots):** mechanics-focused, live aim scoring on the overlay (allowed here because there is no competitive opponent), drill suggestions and a warm-up score compared with previous days.

## 6. UI / UX

**Look:** dark tactical theme, one sharp accent colour, clean type, generous spacing, smooth 150–250 ms transitions, no clutter. Built with React, Tailwind and a small component library; charts with a lightweight charting library.

**Screens**
1. **Setup wizard** (first launch, can be re-run): in-game name → import `GameSettings.ini` + DPI → 360° calibration → resolution / HUD scale → HUD check → voice & push-to-talk key → local AI check (Ollama detection, guided install).
2. **Home:** big **Start Live Mode** and **Start Warm-up** buttons; status lights (Game, Capture, Input, HUD, Coach AI, Voice); last-session summary card; current weekly focus.
3. **Live:** compact live view: round, alive/dead, live metric tiles (overshoot %, flicks, reaction), feed of the coach's notes.
4. **Overlay** (in game, borderless windowed): a small card appears on death, between rounds and at match end, then fades. Nothing shows mid-round in Live Mode. Position and size are configurable.
5. **Session Review:** match list → round timeline → death cards (clip player with the input trace drawn under the video, coach note, evidence) → match report.
6. **Progress:** trends across sessions for each metric and habit, weekly goals, best/worst maps and operators by survival.
7. **Settings:** coach frequency, voice, overlay, capture quality, clip storage limit, AI model, privacy (delete all data).

**UX rules**
- Every status light explains itself on hover and says how to fix a problem ("Siege is in exclusive fullscreen → switch to borderless").
- Every tip can be expanded to show *why* (the evidence).
- Works fully without the local AI; the experience degrades gracefully.

## 7. Error handling

- **Engine crash:** the app shows a clear banner, restarts the engine once, and keeps the session data saved up to the crash.
- **Game not found / not focused:** Live Mode waits and shows "Waiting for Siege…".
- **Low HUD confidence:** events are flagged as uncertain and are not used for tips, and the HUD status light turns amber with a "Re-run HUD check" action.
- **Performance guard:** if capture or analysis falls behind, the engine lowers the capture fps and HUD rate automatically and tells the player.
- **Ollama missing or slow:** fall back to CoachBrain text; status light shows "Basic coach".

## 8. Testing

- **Replay mode:** the engine can run on a recorded video + input log instead of live sources. This is the main way to test on non-Windows machines and to reproduce bugs from the owner's sessions.
- **Engine unit tests (pytest):** Mechanics on synthetic mouse traces (known flicks/overshoots), CoachBrain rules on fixed stats, RoundTracker on scripted event sequences, HudReader on a library of real HUD screenshots (supplied by the owner) at several resolutions.
- **Contract test:** engine message schemas vs TypeScript types.
- **UI tests:** component tests (Vitest + Testing Library) and end-to-end tests (Playwright) against a fake engine.
- **On-device checks (owner's PC):** FPS impact, death-detection accuracy over 3 ranked matches, latency from death to tip (< 3 s without LLM, < 6 s with it).

## 9. Build order (each step usable on its own)

1. App shell, design system, setup wizard, engine process + WebSocket link, status lights.
2. InputTracker + Mechanics + 360° calibration → **Warm-up Mode** working end to end.
3. ScreenCapture + HudReader + RoundTracker + ClipWriter → deaths and rounds detected live.
4. CoachBrain + overlay + Voice + LocalLLM → **Live Mode** coaching at breaks and match report.
5. Session Review + Progress screens.
6. Installer (single `.exe`), auto-start of the engine, settings polish.

## 10. Out of scope for v1

Accounts, cloud sync, subscriptions, console support, other games, macOS/Linux builds, team/squad analysis, tactical mid-round callouts, and any enemy-related information.
