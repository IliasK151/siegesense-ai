# SiegeSense Step 2 — Input Tracking, Aim Mechanics & Warm-up Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The player can start **Warm-up Mode**, play in the Shooting Range / T-Hunt, and see live aim metrics (flicks, overshoot, corrections, flick speed, ADS jitter, spray/tap, shooting while moving) in the app and on a small in-game overlay. When they stop, they get a warm-up score, a drill suggestion and a comparison with previous sessions. A 360° calibration makes every number exact for their sensitivity.

**Architecture:** A Windows Raw Input reader runs on its own thread and feeds an `InputHub`, which batches events onto the asyncio loop every 10 ms. Pure, synchronous analysers (`FlickDetector`, `HabitTracker`, `CalibrationSession`) consume those events; they are tested on synthetic traces. `WarmupService` and `CalibrationService` wire the analysers to the WebSocket protocol (new requests + `metrics`/`flick`/`calibration` pushes) and to SQLite. The app adds a Warm-up page, a calibration panel (wizard step + Settings), and a transparent click-through overlay window. A replay input source (`--replay-input`) drives the end-to-end test and is the spec's "replay mode" for reproducing sessions.

**Tech Stack:** Same as step 1. Windows input uses `ctypes` only (no new Python dependencies).

**Spec:** `docs/superpowers/specs/2026-11-01-siegesense-design.md` — build step 2 of §9: §4.2 InputTracker, §4.5 Mechanics (all but reaction time and re-peek), §5 Warm-up Mode, the calibration part of the §6 setup wizard.

## Global Constraints

- Fair play (§2): only the player's own input is read (Raw Input with `RIDEV_INPUTSINK`); nothing is ever sent to the game; no game memory/process access.
- All analysis is local (§4.11). Warm-up summaries are stored in the local SQLite database.
- Mechanics definitions (§4.5), exact values: flick = peak angular speed ≥ **300 °/s** and amplitude ≥ **5°**; correction = reversal along the flick direction ≥ **10 %** of the amplitude within **250 ms** after the peak; overshoot = correction followed by a shot within **400 ms**. Micro-jitter = direction changes under **1°** while ADS.
- Calibration is ground truth: when `counts_per_360` is set it overrides the formula estimate (§4.2).
- Warm-up overlay may show live scoring (§5). The overlay is transparent, click-through and never takes focus.
- Every new status light state explains itself and says how to fix it (§6).
- Windows-only code sits behind an interface with a fake; everything else is tested on Linux.

## Rulings carried in from the spec

- **Reaction time** needs screen capture (step 3) and is deferred there. **Re-peek** needs fight detection (step 3/4) and is deferred too.
- **ADS-specific degree conversion** (scope multipliers, X-factor, FOV) is not modelled yet: all movement is converted with the hip-fire factor. Overshoot/correction are ratios, so they are unaffected; absolute degrees while ADS are approximate. ADS state is still tracked (right mouse button held) for jitter.
- **Formula estimate** for degrees per count: `yaw_sensitivity × mouse_multiplier_unit × 0.0572957795` (community formula; labelled "estimated" in the UI, with calibration recommended). Pitch uses `pitch_sensitivity` the same way. Calibration replaces both with `360 / counts_per_360` (pitch scaled by `pitch_sensitivity / yaw_sensitivity`).
- **Overshoot shot window** starts at the moment the reversal is deepest (the "correction time").
- **Default keys**: W/A/S/D move, C crouch, F8 calibration hotkey. Not configurable in this step.

## Review Focus

1. **The game window is focused (the app isn't).** Input must still be captured — that is what `RIDEV_INPUTSINK` is for. Calibration therefore uses an in-game hotkey (F8), not app buttons. → Task 3 registers with `RIDEV_INPUTSINK`; Task 7 tests hotkey-driven runs.
2. **Not Windows / Raw Input registration fails.** The engine must keep working: input light `warn` with a fix, Warm-up start returns a clear error instead of hanging. → Task 2 `test_unavailable_source`, Task 8 `test_start_warmup_without_input_errors`.
3. **No profile / no calibration.** Warm-up needs a profile (clear error if missing) and works uncalibrated using the estimate, showing "estimated" in the UI. → Task 8 `test_start_warmup_requires_profile`, Task 11 `shows estimated badge`.
4. **Bursty or out-of-order timing (Raw Input delivers bursts, 8 kHz mice).** The flick detector must bin by time, not by event count, and tolerate many events per millisecond. → Task 4 `test_high_rate_mouse_same_result`.
5. **Stop warm-up with too few flicks.** No score, no fake drill: "Not enough flicks yet (need 10)". → Task 6 `test_summary_with_few_flicks`.

---

## File Structure

```
engine/src/siegesense_engine/
  gamesettings.py              (modify) inf/nan, Windows known-folder Documents
  input/__init__.py
  input/events.py              MouseMove / Button / Key events
  input/source.py              InputSource protocol, Fake, Unavailable, Replay sources, default factory
  input/rawinput.py            Windows Raw Input thread + pure decode helpers
  input/hub.py                 InputHub: thread → asyncio batching, subscribers
  mechanics/__init__.py
  mechanics/sensitivity.py     counts → degrees
  mechanics/flicks.py          FlickDetector
  mechanics/habits.py          HabitTracker
  warmup.py                    WarmupSession, score, drills, models
  calibration.py               CalibrationSession
  services.py                  WarmupService, CalibrationService (protocol wiring)
  store.py                     (modify) migration 2: warmup_sessions
  status.py                    (modify) input light
  server.py                    (modify) register services, broadcast()
  __main__.py                  (modify) --replay-input
engine/tests/synth.py          synthetic trace generator (test helper)
protocol/fixtures/             metrics.json, flick.json, calibration.json, warmup_summary.json
app/src/shared/protocol.ts     (modify) new schemas
app/src/main/index.ts          (modify) single-instance lock, overlay window, graceful stop
app/src/main/engineProcess.ts  (modify) graceful stop
app/src/preload/api.ts|index.ts (modify) setOverlayVisible
app/src/renderer/src/
  lib/engineClient.ts          (modify) metrics/flick/calibration pushes
  components/calibration/CalibrationPanel.tsx
  components/warmup/{MetricTile,FlickChart,FlickList,WarmupSummary}.tsx
  pages/Warmup.tsx
  pages/setup/StepCalibrate.tsx
  overlay/OverlayApp.tsx, overlay/main.tsx, overlay.html
```

---

### Task 1: Step 1 follow-ups (from the step 1 final review)

**Files:** Modify `engine/src/siegesense_engine/gamesettings.py`, `engine/src/siegesense_engine/server.py`, `app/src/main/engineProcess.ts`, `app/src/main/index.ts`. Tests: `engine/tests/test_gamesettings.py`, `engine/tests/test_server.py`, `app/tests/engineProcess.test.ts`.

**Interfaces:**
- `EngineSupervisor.stop(graceMs = 2000): void` — ends the child's stdin, kills only if it hasn't exited after `graceMs`.
- `default_documents_dirs()` on win32 first asks `SHGetKnownFolderPath(FOLDERID_Documents)` (GUID `{FDD39AD0-238F-46AF-ADB4-6C85480369C7}`) via ctypes, then adds `~/Documents` and every `~/OneDrive*/Documents` that exists, de-duplicated.

- [ ] **Step 1: Failing tests**
  - `test_inf_and_nan_go_to_missing`: `DefaultFOV=nan`, `MouseYawSensitivity=inf`, `ResolutionWidth=1e400` → none in `values`, all in `missing`, no exception.
  - `test_onedrive_variants_found`: monkeypatch `Path.home()` to tmp with `OneDrive - Contoso/Documents` → included.
  - `test_token_compare_constant_time`: monkeypatch `hmac.compare_digest` spy → called during hello.
  - `test_new_client_does_not_mask_status_change`: client A connected; flip watcher; client B connects (gets new status); A still receives the changed status within 0.5 s.
  - `stop ends stdin before killing` (fake child: assert `stdin` ended, `kill` not called when child exits within grace; `kill` called after grace when it doesn't).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
  - Converters reject non-finite numbers and catch `(ValueError, OverflowError)`.
  - `hmac.compare_digest` for the token.
  - The status ticker keeps its own `last_broadcast` instead of sharing `_last_status` with connects.
  - Supervisor graceful stop.
  - In `index.ts`: `app.requestSingleInstanceLock()` (quit if not acquired; focus the existing window on `second-instance`), `win.webContents.setWindowOpenHandler(() => ({ action: "deny" }))` and `will-navigate` → `preventDefault()` unless the URL is the app's own.
- [ ] **Step 4: Run** engine + app suites → PASS.
- [ ] **Step 5: Commit** `fix: step 1 review follow-ups`.

### Task 2: Input events, sources, hub and degree conversion

**Files:** Create `input/__init__.py`, `input/events.py`, `input/source.py`, `input/hub.py`, `mechanics/__init__.py`, `mechanics/sensitivity.py`. Tests: `engine/tests/test_input.py`, `engine/tests/test_sensitivity.py`.

**Interfaces:**
- `events.py`: frozen slotted dataclasses `MouseMove(t: float, dx: int, dy: int)`, `Button(t: float, button: Literal["left","right","middle","x1","x2"], down: bool)`, `Key(t: float, vk: int, down: bool)`; `InputEvent = MouseMove | Button | Key`. `t` is seconds from `time.perf_counter()`. `dy > 0` means mouse moved down (Windows convention).
- `VK = SimpleNamespace(W=0x57, A=0x41, S=0x53, D=0x44, C=0x43, F8=0x77)`
- `source.py`:
  - `class InputSource(Protocol)`: `available: bool`; `reason: str | None`; `start(self, sink: Callable[[InputEvent], None]) -> None`; `stop(self) -> None`.
  - `FakeInputSource` (`emit(*events)` calls the sink if started).
  - `UnavailableInputSource(reason)` (`start` raises `InputUnavailable(reason)`).
  - `ReplayInputSource(path: Path, speed: float = 1.0)`: JSONL lines `{"k":"m","t":…,"dx":…,"dy":…}` / `{"k":"b","t":…,"b":"left","d":1}` / `{"k":"k","t":…,"vk":87,"d":1}`. On `start` a thread replays events with original spacing (re-based to now), then stops.
  - `def default_input_source() -> InputSource`: `RawInputSource()` on win32 (Task 3), else `UnavailableInputSource("Input tracking works on Windows only")`.
- `hub.py`: `class InputHub`
  - `__init__(self, source: InputSource, *, flush_interval: float = 0.01)`
  - `subscribe(self, cb: Callable[[list[InputEvent]], None]) -> Callable[[], None]`
  - `async def acquire(self) -> None`: starts the source on the first subscriber, ref-counted; raises `InputUnavailable`
  - `def release(self) -> None`: stops the source when the count hits 0
  - `active: bool`
  - The source thread appends to a `collections.deque`; an asyncio task drains it every `flush_interval` and calls subscribers with the batch in time order.
- `sensitivity.py`:
  - `RAD_TO_DEG_MILLI = 0.0572957795`
  - `@dataclass Conversion(yaw: float, pitch: float, source: Literal["calibrated","estimated"])` (degrees per count)
  - `def conversion(profile: Profile) -> Conversion`
  - `def estimated_counts_per_360(profile) -> float`
  - `def cm_per_360(profile) -> float` (`counts_per_360 / dpi × 2.54`, using the calibrated value when present)

- [ ] **Step 1: Failing tests**
  - `test_hub_batches_in_order` (fake source emits 5 events from another thread → one subscriber gets all 5, in order)
  - `test_hub_refcount_starts_and_stops_source`
  - `test_unavailable_source` (`acquire` raises `InputUnavailable` with the reason)
  - `test_replay_source_plays_file` (3-line file, speed 10 → events delivered, dx values match)
  - `test_estimated_conversion` (yaw 10, unit 0.02 → `0.0114591559` ±1e-9, source "estimated")
  - `test_calibrated_conversion` (`counts_per_360=36000`, yaw 10, pitch 5 → yaw 0.01, pitch 0.005, source "calibrated")
  - `test_cm_per_360` (36000 counts at 800 DPI → 114.3 cm)
- [ ] **Step 2: Run** `pytest tests/test_input.py tests/test_sensitivity.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): input events, sources, hub and sensitivity conversion`.

### Task 3: Windows Raw Input source

**Files:** Create `input/rawinput.py`. Test: `engine/tests/test_rawinput_decode.py`.

**Interfaces:**
- Pure helpers (tested on any OS):
  - `def decode_mouse(t: float, flags: int, button_flags: int, last_x: int, last_y: int) -> list[InputEvent]`
    - Relative motion when `flags & MOUSE_MOVE_ABSOLUTE (0x01) == 0` and `(last_x, last_y) != (0, 0)` → `MouseMove`. Absolute motion (tablets/RDP) is ignored.
    - Button flags → `Button` events: `0x0001/0x0002` left down/up, `0x0004/0x0008` right, `0x0010/0x0020` middle, `0x0040/0x0080` x1, `0x0100/0x0200` x2.
  - `def decode_keyboard(t: float, vkey: int, flags: int) -> Key | None` (`RI_KEY_BREAK = 0x01` → up; `vkey == 0xFF` → None)
- `class RawInputSource`:
  - Its thread creates a message-only window (`HWND_MESSAGE`).
  - It registers mouse (usage page 0x01, usage 0x02) and keyboard (0x01, 0x06) with `RIDEV_INPUTSINK (0x100)` and that window as target.
  - It runs `GetMessageW`. On `WM_INPUT (0x00FF)` it calls `GetRawInputData(..., RID_INPUT=0x10000003, ...)` into a buffer sized from the first call, reads `RAWINPUTHEADER.dwType` (0 mouse, 1 keyboard), decodes with the helpers and calls the sink with `time.perf_counter()`.
  - `stop()` posts `WM_QUIT` via `PostThreadMessageW` and joins.
  - `available` is True on win32. If `RegisterRawInputDevices` fails, `start` raises `InputUnavailable("Windows refused raw input registration (error N)")`.
  - Use `ctypes.wintypes`. Define `RAWINPUTHEADER`, `RAWMOUSE` (with the `usButtonFlags`/`usButtonData` union flattened as two USHORTs after `usFlags` + 2-byte padding), `RAWKEYBOARD` and `RAWINPUTDEVICE` structures. Pointer-sized fields use `wintypes.HANDLE`/`WPARAM` so 64-bit layout is correct.

- [ ] **Step 1: Failing tests:** `test_relative_move`, `test_absolute_move_ignored`, `test_zero_move_ignored`, `test_buttons_down_up` (flags `0x0001|0x0008` → left down + right up), `test_key_down_up`, `test_fake_vkey_ignored`, plus `test_module_imports_on_linux` (importing `rawinput` must not fail off Windows).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): windows raw input source`.

### Task 4: Flick detector

**Files:** Create `mechanics/flicks.py`, `engine/tests/synth.py`. Test: `engine/tests/test_flicks.py`.

**Interfaces:**
- `@dataclass FlickConfig`:
  - `min_peak_speed=300.0` (°/s), `min_amplitude=5.0` (°)
  - `correction_window=0.25` (s, after peak), `correction_ratio=0.10`, `shot_window=0.40` (s, after correction time)
  - `bin_s=0.005`, `end_ratio=0.20`, `max_lookback=0.30` (s)
- `@dataclass Flick`:
  - `t_peak: float`
  - `amplitude: float` (°), `peak_speed: float` (°/s), `duration_ms: float` (onset→ballistic end), `direction: float` (° from atan2(−dy, dx), 0 = right, 90 = up)
  - `reversal: float` (°, ≥ 0), `corrected: bool`, `overshoot: bool`, `shot: bool` (any shot within `shot_window` of ballistic end)
  - `trace: list[tuple[float, float]]`: (ms from onset, projection on the flick direction in °), one point per bin from onset to `t_peak + correction_window`
- `class FlickDetector`: `__init__(self, config: FlickConfig = FlickConfig())`; `move(self, t: float, dx_deg: float, dy_deg: float) -> None`; `shot(self, t: float) -> None`; `poll(self, now: float) -> list[Flick]` returns flicks that are finished (`now ≥ max(t_peak + correction_window, correction_time + shot_window)`).
- Algorithm (binding):
  1. Accumulate moves into 5 ms time bins keyed by `floor(t / bin_s)` (many events per bin are summed; out-of-order within 50 ms is tolerated by bin key). Speed of bin i = |bin_i + bin_{i−1}| / (2·bin_s).
  2. When speed ≥ `min_peak_speed`, a candidate starts. Track the max-speed bin. The ballistic end is the first later bin whose speed < `end_ratio × peak`.
  3. The onset is the latest bin before the peak whose speed < `end_ratio × peak`, within `max_lookback`.
  4. Amplitude = |Σ bins onset..ballistic end|. If below `min_amplitude`, discard. Direction unit vector u = sum / amplitude.
  5. Correction: walk bins after the ballistic end up to `t_peak + correction_window`, accumulating projection on u. Reversal = max(0, −min cumulative). `corrected = reversal ≥ correction_ratio × amplitude`. The correction time is the bin of the minimum.
  6. Overshoot = corrected and a shot in [correction time, correction time + `shot_window`].
  7. Until a candidate's ballistic end, no new candidate starts. Within its correction window, a fast movement whose direction has negative dot product with u is not a new flick.
- `synth.py`: `def flick(t0: float, amplitude: float, duration: float, angle_deg: float = 0, rate_hz: int = 1000, overshoot: float = 0, correction_duration: float = 0.08) -> list[tuple[float, float, float]]` returns (t, dx°, dy°) samples. Use a minimum-jerk position profile `A·(10s³ − 15s⁴ + 6s⁵)`. An overshoot is generated as a second minimum-jerk segment of size −overshoot along the same axis right after.

- [ ] **Step 1: Failing tests:**
  - `test_clean_flick`: 30° in 120 ms → 1 flick, amplitude 30 ± 1, peak speed 469 ± 30 °/s, not corrected.
  - `test_overshoot_with_shot`: 30° plus a 6° overshoot back, shot 100 ms after → corrected, overshoot.
  - `test_correction_without_shot`: same but no shot → corrected, not overshoot.
  - `test_small_reversal_not_corrected`: 2° back.
  - `test_slow_pan_not_flick`: 30° over 500 ms.
  - `test_small_twitch_not_flick`: 3° at 400 °/s.
  - `test_two_flicks`: 1 s apart.
  - `test_direction_up_left`: angle 135 → direction 135 ± 3.
  - `test_high_rate_mouse_same_result`: the same flick at 8000 Hz gives amplitude within 0.5° of the 1000 Hz result.
  - `test_poll_waits_for_shot_window`: polled at peak + 0.1 s → [], at +0.7 s → [flick].
  - `test_trace_shape`: the first point is at 0 ms, the last projection is about 24° for the overshoot case.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): flick and overshoot detection`.

### Task 5: Habit tracker

**Files:** Create `mechanics/habits.py`. Test: `engine/tests/test_habits.py`.

**Interfaces:**
- `class HabitTracker`: `__init__(self)`; `button(self, t, button, down)`; `key(self, t, vk, down)`; `move(self, t, dx_deg, dy_deg)`; `snapshot(self) -> HabitStats`.
- `@dataclass HabitStats`:
  - `shots: int`; `taps: int` (hold < 150 ms); `bursts: int` (150–600 ms); `sprays: int` (> 600 ms)
  - `moving_shots: int` (left down while any of W/A/S/D held)
  - `strafe_switches: int` (A down with the last strafe-key down being D within 500 ms, or vice versa)
  - `crouch_spams: int` (one per run of ≥ 3 C downs within 2 s; a run counts once)
  - `ads_seconds: float` (right held)
  - `ads_jitter: int`: while ADS, horizontal displacement is binned in 50 ms bins. One jitter event is counted each time consecutive bins change sign and both have 0.05° < |dx| < 1°.

- [ ] **Step 1: Failing tests:** `test_tap_burst_spray_classification`, `test_moving_shot`, `test_strafe_switch`, `test_crouch_spam_counts_once_per_run`, `test_ads_seconds`, `test_ads_jitter`, `test_jitter_ignores_big_moves` (1.5° bins don't count).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): shooting and movement habit tracking`.

### Task 6: Warm-up session, score, drills and storage

**Files:** Create `warmup.py`; modify `store.py`. Tests: `engine/tests/test_warmup.py`, `engine/tests/test_store.py`.

**Interfaces:**
- `class WarmupMetrics(BaseModel)`:
  - `elapsed_s: float`; `flicks: int`; `corrected: int`; `overshoots: int`
  - `overshoot_rate: float`; `correction_rate: float` (0 when no flicks)
  - `avg_amplitude: float`; `avg_peak_speed: float`
  - `shots`, `taps`, `bursts`, `sprays`, `moving_shots`, `strafe_switches`, `crouch_spams`: `int`
  - `moving_shot_rate: float`; `ads_jitter_per_s: float`
  - `score: int | None`; `conversion: Literal["calibrated","estimated"]`
- `class FlickOut(BaseModel)`: the `Flick` fields with `trace: list[list[float]]`, plus `id: int`.
- `class Drill(BaseModel)`: `key: str`, `title: str`, `text: str`.
- `class WarmupSummary(BaseModel)`: `id: int | None`, `started_at: str` (ISO), `duration_s: float`, `metrics: WarmupMetrics`, `drill: Drill | None`, `message: str`, `history: list[HistoryPoint]` (`HistoryPoint(started_at: str, score: int | None)`, newest last, up to 7 previous sessions).
- `class WarmupSession`:
  - `__init__(self, conversion: Conversion, started_at: datetime, t0: float, flick_config=FlickConfig())`
  - `feed(self, events: list[InputEvent]) -> None`; `poll(self, now: float) -> list[FlickOut]`; `metrics(self, now: float) -> WarmupMetrics`
- Fixed values:
  - `MIN_FLICKS_FOR_SCORE = 5`, `MIN_FLICKS_FOR_DRILL = 10`
  - Score = `round(100 × (0.6 × (1 − overshoot_rate) + 0.4 × (1 − correction_rate)))` when flicks ≥ 5, else `None`
- `def choose_drill(m: WarmupMetrics) -> Drill | None`: `None` if flicks < 10. Otherwise the first matching rule:
  - `overshoot_rate > 0.30` → `overshoot`: "Overshooting your flicks". Text: "In the Shooting Range, flick between two targets at about 70% speed for 20 reps. Focus on stopping on the head, not past it."
  - `correction_rate > 0.40` → `corrections`: "Too many micro-corrections". Text: "Pick a target 60° away and flick to it 20 times without adjusting after. Accuracy first, speed comes later."
  - `moving_shot_rate > 0.50` → `counter_strafe`: "Shooting while moving". Text: "Strafe, stop, then shoot. Do 20 strafe-stop-tap reps on a bot and let your movement settle before each shot."
  - `ads_jitter_per_s > 4` → `smooth_ads`: "Shaky while aiming down sights". Text: "Hold ADS on a static target for 5 seconds, 10 times, keeping your crosshair still. Relax your grip."
  - Else → `clean`: "Clean flicks". Text: "Your flicks are clean. Raise the difficulty: farther targets, faster switches."
- `message` when flicks < 10: "Not enough flicks yet (need 10) — no score or drill for this session." if flicks < 5; otherwise "Score is ready; play a bit longer for a drill suggestion."
- Store migration 2: `warmup_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, duration_s REAL NOT NULL, score INTEGER, summary TEXT NOT NULL)`. Methods `add_warmup(summary: WarmupSummary) -> int` and `recent_warmups(limit: int = 7) -> list[HistoryPoint]` (oldest first).

- [ ] **Step 1: Failing tests:**
  - `test_metrics_from_synthetic_session`: 10 flicks, 4 with overshoot+shot → overshoot_rate 0.4, score `round(100*(0.6*0.6+0.4*0.6))` = 60, drill `overshoot`.
  - `test_summary_with_few_flicks`: 3 flicks → score None, drill None, the message as above.
  - `test_clean_session_drill`
  - `test_store_warmup_history_order`
  - `test_migration_2_from_v1_db`: create a v1 db with a profile, reopen → schema 2, profile intact.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): warm-up session scoring, drills and history`.

### Task 7: 360° calibration session

**Files:** Create `calibration.py`. Test: `engine/tests/test_calibration.py`.

**Interfaces:**
- `class CalibrationState(BaseModel)`:
  - `phase: Literal["armed","measuring","done","cancelled"]`
  - `runs: list[int]`; `current_counts: int`; `target_runs: int = 3`
  - `result: float | None` (median counts per 360); `spread: float | None` ((max − min) / median); `warning: str | None`
- `class CalibrationSession`:
  - `__init__(self, hotkey_vk: int = VK.F8, target_runs: int = 3)`
  - `feed(self, events: list[InputEvent]) -> bool` (True when the state changed)
  - `state(self) -> CalibrationState`; `cancel(self)`
- Rules:
  - F8 down while armed → measuring (counter 0). While measuring, add `dx` (signed). F8 down while measuring → `abs(sum)` recorded as a run, back to armed.
  - Key repeat (F8 down while already down) is ignored.
  - A run < 1000 counts is rejected: not recorded, `warning="That was too small — turn one full circle, then press F8."`.
  - After `target_runs` runs → done, with median `result`. If `spread > 0.03`, set `warning="Your runs differ by N% — try again slowly for a more exact result."` (N rounded).

- [ ] **Step 1: Failing tests:** `test_three_runs_median`, `test_tiny_run_rejected`, `test_key_repeat_ignored`, `test_spread_warning`, `test_left_turn_counts_positive`, `test_cancel`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): 360 degree calibration`.

### Task 8: Services, protocol wiring, input light and replay CLI

**Files:** Create `services.py`; modify `server.py`, `status.py`, `__main__.py`; create `protocol/fixtures/{metrics,flick,calibration,warmup_summary}.json`. Tests: `engine/tests/test_services.py`, `engine/tests/test_status.py`, `engine/tests/test_protocol.py`.

**Interfaces:**
- `Push = Callable[[str, BaseModel | dict], Awaitable[None]]`
- `EngineServer.__init__` gains `input_source: InputSource` (default `UnavailableInputSource("…")` in tests) and builds `InputHub`. It also gains `async def broadcast(self, type: str, payload) -> None`.
- `class WarmupService(hub, store, push, clock=time.perf_counter)`:
  - `async def start(self) -> dict`: no profile → `RequestError("no_profile", "Finish setup first.")`; already running → `RequestError("already_running", …)`; `InputUnavailable` → `RequestError("input_unavailable", reason)`. Otherwise it returns `{"conversion": "calibrated"|"estimated"}`.
  - `async def stop(self) -> WarmupSummary`: also persists the summary. If not running → `RequestError("not_running", …)`.
  - `async def history(self) -> dict`
  - While running: on each hub batch it feeds the session and pushes every polled flick as `flick`; it pushes `metrics` every 0.5 s.
- `class CalibrationService(hub, push)`: `start() -> CalibrationState`, `cancel() -> CalibrationState`. It pushes `calibration` on every state change and releases the hub when done or cancelled.
- New request types: `start_warmup`, `stop_warmup`, `get_warmup_history`, `start_calibration`, `cancel_calibration`. New push types: `metrics`, `flick`, `calibration`.
- `StatusBoard` gains an input light: `input_available: Callable[[], tuple[bool, str | None]]` and `input_active: Callable[[], bool]`.
  - unavailable → `warn`, "Input tracking unavailable", detail = reason, fix "Run SiegeSense on Windows" (or the Windows error)
  - available and idle → `ok`, "Input ready"
  - active → `ok`, "Tracking your mouse"
- CLI: `--replay-input FILE` uses `ReplayInputSource(FILE)` instead of the default.
- Fixtures: one sample each for the new pushes and for the `stop_warmup` response data (`warmup_summary.json` as a `response` envelope).

- [ ] **Step 1: Failing tests:**
  - `test_start_warmup_requires_profile`, `test_start_warmup_without_input_errors`
  - `test_warmup_pushes_flick_and_metrics` (FakeInputSource + synth flick converted to counts with the profile's conversion → client receives `flick` then `metrics` with flicks ≥ 1)
  - `test_stop_returns_summary_and_persists`, `test_double_start_errors`
  - `test_calibration_flow_over_ws` (FakeInputSource emits F8, moves, F8 ×3 → final `calibration` push phase `done`)
  - `test_input_light_states`
  - `test_new_fixtures_validate` (`WarmupMetrics`, `FlickOut`, `CalibrationState`, `WarmupSummary` parse the fixtures)
  - `test_cli_replay_flag` (`--replay-input` is accepted, READY printed)
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** full engine suite → PASS, ruff clean.
- [ ] **Step 5: Commit** `feat(engine): warm-up and calibration services over websocket`.

### Task 9: App protocol and client pushes

**Files:** Modify `app/src/shared/protocol.ts`, `app/src/renderer/src/lib/engineClient.ts`, `app/src/renderer/src/lib/engineContext.tsx`, `app/tests/helpers/fakeEngine.ts`. Tests: `app/tests/protocol.contract.test.ts`, `app/tests/engineClient.test.ts`.

**Interfaces:**
- zod schemas `WarmupMetrics`, `Flick` (= FlickOut), `CalibrationState`, `Drill`, `HistoryPoint`, `WarmupSummary` mirroring Task 6/7 exactly (snake_case).
- `PushMap` gains `metrics: WarmupMetrics`, `flick: Flick`, `calibration: CalibrationState`. Each push is validated with its schema; invalid ones are dropped.
- `FakeEngine` gains `emit(type, payload)` for any push type.

- [ ] **Step 1: Failing tests:** the contract test parses the 4 new fixtures; `delivers metrics flick and calibration pushes`; `drops invalid push`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(app): warm-up and calibration protocol`.

### Task 10: Calibration panel (wizard step + Settings)

**Files:** Create `components/calibration/CalibrationPanel.tsx`, `pages/setup/StepCalibrate.tsx`; modify `pages/setup/draft.ts` (steps), `pages/setup/SetupWizard.tsx`, `pages/Settings.tsx`. Test: `app/tests/calibration.test.tsx`; update `app/tests/setup.test.tsx` for the new step.

**Interfaces:**
- `CalibrationPanel({ onResult(counts: number): void, onCancel?(): void })`: a Start button → `start_calibration`. It shows instructions:
  1. "Switch to Siege (Shooting Range is ideal) and aim at a sharp edge."
  2. "Press F8, turn exactly one full circle to the right, stop on the same edge, press F8."
  3. "Do it 3 times."
- While running it shows the live run counter (`current_counts`), run chips (`runs`), any `warning`, and a Cancel button (`cancel_calibration`). On `done` it shows the result in counts and cm/360 (`counts / dpi × 2.54`, when a DPI is known), with **Use this result** → `onResult(result)` and **Redo**.
- `WIZARD_STEPS = ["Welcome","Player","Sensitivity","Calibrate","Display","Done"]`. The Calibrate step is optional: a "Skip for now" button moves on and leaves `counts_per_360` unset. The Done summary shows "Calibrated" or "Estimated".
- Settings: a "360° calibration" card showing the current value (or "Not calibrated — using estimate"). It opens `CalibrationPanel`; on result it calls `save_profile` with the updated `counts_per_360` and reloads.

- [ ] **Step 1: Failing tests:** `starts calibration and shows live counts`, `use result sets counts`, `shows warning`, `cancel sends cancel_calibration`, `wizard can skip calibration`, `settings saves calibration`. Update the existing setup tests to click through the new step (Skip).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + typecheck.
- [ ] **Step 5: Commit** `feat(app): 360 degree calibration panel`.

### Task 11: Warm-up page

**Files:** Create `pages/Warmup.tsx`, `components/warmup/{MetricTile,FlickChart,FlickList,WarmupSummary}.tsx`; modify `store/nav.ts` (`"warmup"` page), `components/shell/Sidebar.tsx` (a "Warm-up" item with the Crosshair icon after Home), `pages/Home.tsx` (enable Start Warm-up → `go("warmup")`), `App.tsx`. Test: `app/tests/warmup.test.tsx`.

**Interfaces / behaviour:**
- Idle state:
  - A hero with a **Start warm-up** primary button and the short tip "Load the Shooting Range or T-Hunt in Siege, then press start".
  - A Badge "Calibrated" (ok) or "Estimated — calibrate in Settings" (warn), based on the profile's `counts_per_360`.
  - A last-7-sessions score sparkline from `get_warmup_history`.
- Running state (after `start_warmup` resolves):
  - Big Score tile (shows "—" until a score exists); tiles for Flicks, Overshoot %, Corrections %, Avg flick speed (°/s), Shots while moving %, ADS jitter (/s); a pulsing "LIVE" badge; the elapsed timer.
  - `FlickChart`: SVG of the latest flick's trace (x: ms, y: projection °), a dashed line at the amplitude, and the overshoot region tinted `--color-warn` when `corrected`.
  - `FlickList`: last 8 flicks with tags `Clean` (ok), `Correction` (warn), `Overshoot` (error), plus amplitude and speed.
  - Stop button → `stop_warmup`.
- Summary state: big score, message, a drill card (title + text), a history sparkline including today, metric recap, and a "New warm-up" button.
- Errors from start (`input_unavailable`, `no_profile`) show inline with their message.
- While running, call `window.siegesense?.setOverlayVisible(true)`; on stop or unmount, `false`.

- [ ] **Step 1: Failing tests:** `start shows live tiles`, `metrics push updates tiles`, `flick push adds tagged row and chart`, `stop shows summary with drill`, `shows estimated badge`, `start error shown`, `toggles overlay`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + typecheck.
- [ ] **Step 5: Commit** `feat(app): live warm-up mode`.

### Task 12: In-game warm-up overlay

**Files:** Create `app/src/renderer/overlay.html`, `app/src/renderer/src/overlay/main.tsx`, `app/src/renderer/src/overlay/OverlayApp.tsx`; modify `electron.vite.config.ts` (second renderer input), `app/src/main/index.ts`, `app/src/preload/api.ts`, `app/src/preload/index.ts`. Test: `app/tests/overlay.test.tsx`.

**Interfaces:**
- `SiegeSenseApi.setOverlayVisible(visible: boolean): void` (IPC `overlay:set`).
- Main process: a lazily created `BrowserWindow`:
  - 300×140, `transparent: true`, `frame: false`, `resizable: false`, `skipTaskbar: true`, `focusable: false`, `alwaysOnTop: true` with level `"screen-saver"`
  - `setIgnoreMouseEvents(true)`, positioned 24 px from the top-right of the primary display's work area
  - It loads `overlay.html` and is shown with `showInactive()`, hidden on false.
- `OverlayApp`: its own `EngineProvider`-less `EngineClient` (same `getEngine`). It shows the Score (or "—"), Overshoot %, Flicks and the last flick tag. It is a translucent dark card (`bg-bg/80`, `backdrop-blur`) with the accent border, and fades in (200 ms) on each new flick tag.

- [ ] **Step 1: Failing tests:** `overlay shows metrics from push`, `overlay shows last flick tag`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `npm run build` emits both `index.html` and `overlay.html`.
- [ ] **Step 5: Commit** `feat(app): in-game warm-up overlay`.

### Task 13: End-to-end warm-up with replayed input, README

**Files:** Create `engine/tests/fixtures/warmup_replay.jsonl` (generated by `engine/tests/make_replay.py`, committed alongside); modify `app/tests/e2e/globalSetup.ts` (`--replay-input`), create `app/tests/e2e/warmup.spec.ts`; modify `README.md` (status table, how to use Warm-up and calibration).

**Interfaces:**
- `make_replay.py`: writes 12 flicks (5 with an overshoot followed by a shot), 1.2 s apart, starting 1 s after start. It uses counts for the e2e profile's estimated conversion: yaw 12, unit 0.02 → `0.0137509871` °/count.

- [ ] **Step 1: Failing e2e** `warm-up counts flicks and shows summary`: complete setup (Skip calibration) → Warm-up → Start → within 20 s the Flicks tile shows 12 → Stop → the summary shows a score and a drill title.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the full suite (engine pytest + ruff, app typecheck + vitest + e2e) → PASS.
- [ ] **Step 5: Commit** `test: end-to-end warm-up with replayed input`.
