# SiegeSense Step 1 — App Shell, Engine Link & Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A polished Electron desktop app that launches the Python engine, connects to it over an authenticated localhost WebSocket, shows live status lights, and walks the player through a setup wizard that saves their profile (name, DPI, sensitivity imported from `GameSettings.ini`, display settings).

**Architecture:** `engine/` is a Python package (`siegesense_engine`) run as `python -m siegesense_engine`. It serves a JSON protocol over WebSocket and stores data in SQLite. `app/` is an electron-vite project: the main process spawns the engine and hands the port and token to the renderer through the preload bridge; the React renderer talks to the engine directly over WebSocket. Message shapes are pinned by shared JSON fixtures in `protocol/fixtures/`, validated by both pydantic (Python) and zod (TypeScript).

**Tech Stack:** Python 3.12+ (websockets 15+, pydantic 2, psutil, pytest, pytest-asyncio, ruff) · Node 22, Electron, electron-vite, React 19, TypeScript, Tailwind CSS 4, zod, zustand, lucide-react, motion, @fontsource/inter, @fontsource/jetbrains-mono, Vitest, Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-01-siegesense-design.md` (this plan covers build step 1 of §9, plus the profile half of the §6 setup wizard).

## Global Constraints

- Fair play (§2): no game memory reading, no injection, no hooking the game process, no input sending. Step 1 only reads process lists, window info and `GameSettings.ini`.
- Everything stays local (§4.11): the engine binds to `127.0.0.1` only; data lives in the app's user-data folder.
- Each engine launch gets a random auth token (§3). A connection that does not send `hello` with the right token as its first message is closed with WebSocket close code `4401`.
- Every message has `type`, `ts` (monotonic ms) and `payload` (§3). Requests also carry `id`.
- Look (§6): dark tactical theme, one accent colour, 150–250 ms transitions, no clutter. Design tokens are defined once (Task 6) and used everywhere; there are no hard-coded colours in components.
- Every status light explains itself and says how to fix a problem (§6 UX rules).
- Windows-only code sits behind an interface with a fake implementation, so all tests run on Linux (§4).

## Review Focus

1. **A `GameSettings.ini` that is UTF-16 encoded, missing keys, or has odd casing.** Expect a partial import: the keys that were found are filled, the missing ones are listed, nothing crashes. → Task 3 tests `test_utf16_file`, `test_missing_keys_reported`, `test_case_insensitive_keys`.
2. **The engine never starts (Python missing, crash on boot) or dies later.** Expect a clear banner in the app, one automatic restart, and a 15 s start timeout instead of hanging forever. → Task 7 tests `parses ready line`, `times out without ready line`, `restarts once then gives up`.
3. **Bad or missing auth token.** Expect the connection to close with code 4401 and no data to be sent. → Task 5 tests `test_rejects_wrong_token`, `test_rejects_non_hello_first_message`.
4. **Invalid profile values (DPI 0, empty or illegal name, sensitivity 0).** Expect the wizard to block Next with a clear inline message, and the engine to reject the save with an error response if it gets one anyway. → Task 2 `test_profile_validation`, Task 9 `blocks next on invalid name`.
5. **The WebSocket drops mid-session (engine restart).** Expect the client to reconnect with backoff and the UI to show "Reconnecting…" rather than freezing. → Task 7 test `reconnects after close`, Task 8 test `shows reconnecting banner`.

---

## File Structure

```
protocol/fixtures/*.json                 Sample messages, the contract between both sides
engine/pyproject.toml
engine/src/siegesense_engine/
  __init__.py
  __main__.py          CLI entry: args → server, prints READY line
  protocol.py          pydantic message models + parse/serialize helpers
  profile.py           Profile model + validation
  store.py             SQLite Store (schema v1: profiles)
  gamesettings.py      GameSettings.ini discovery + parser
  game_watcher.py      GameWatcher interface, Fake + Windows implementations
  status.py            StatusBoard → status lights
  server.py            WebSocket server, auth, request routing, status broadcast
engine/tests/...       one test file per module
app/                   electron-vite project
  src/main/index.ts            window creation, IPC
  src/main/engineProcess.ts    spawn/supervise engine, READY parsing
  src/preload/index.ts         contextBridge API
  src/shared/protocol.ts       zod schemas mirroring protocol.py
  src/renderer/src/
    main.tsx, App.tsx
    styles.css                 Tailwind + design tokens
    lib/engineClient.ts        WebSocket client (auth, requests, events, reconnect)
    lib/engineContext.tsx      React provider + hooks
    store/nav.ts               zustand navigation/app state
    components/ui/*.tsx        Button, Card, Field, StatusLight, Stepper, Badge
    components/shell/*.tsx     TitleBar, Sidebar, EngineBanner
    pages/Home.tsx, Live.tsx, Review.tsx, Progress.tsx, Settings.tsx
    pages/setup/*.tsx          SetupWizard + one file per step
  tests/...                    vitest tests; e2e/ Playwright
.github/workflows/ci.yml
README.md
```

---

### Task 1: Engine package and protocol contract

**Files:**
- Create: `engine/pyproject.toml`, `engine/src/siegesense_engine/__init__.py`, `engine/src/siegesense_engine/protocol.py`
- Create: `protocol/fixtures/hello.json`, `response_ok.json`, `response_error.json`, `status.json`, `save_profile.json`
- Test: `engine/tests/test_protocol.py`

**Interfaces:**
- Produces:
  - `Envelope(BaseModel)`: `type: str`, `ts: int`, `id: str | None = None`, `payload: dict[str, Any] = {}`
  - `LightState = Literal["ok", "warn", "error", "off"]`
  - `Light(BaseModel)`: `state: LightState`, `label: str`, `detail: str`, `fix: str | None = None`
  - `StatusPayload(BaseModel)`: `lights: dict[Literal["game","capture","input","hud","coach","voice"], Light]`
  - `ErrorInfo(BaseModel)`: `code: str`, `message: str`
  - `def now_ms() -> int` (from `time.monotonic_ns() // 1_000_000`)
  - `def make(type: str, payload: dict | BaseModel | None = None, id: str | None = None) -> str` returns JSON text
  - `def response(id: str, payload=None) -> str` → envelope `type="response"`, payload `{"ok": true, "data": ...}`
  - `def error_response(id: str, code: str, message: str) -> str` → payload `{"ok": false, "error": {code, message}}`
  - `def parse(text: str) -> Envelope` raises `ProtocolError` on invalid JSON or shape
- Request types used in this step: `hello{token}`, `get_profile`, `save_profile{profile}`, `find_game_settings`, `import_game_settings{path}`, `get_status`. Push type: `status`.

- [ ] **Step 1: Create `engine/pyproject.toml`**: hatchling build, `src/` layout, `requires-python = ">=3.12"`, deps `websockets>=15`, `pydantic>=2.8`, `psutil>=6`; dev extra `pytest>=8`, `pytest-asyncio>=0.24`, `ruff`; `[tool.pytest.ini_options] asyncio_mode = "auto"`; ruff line-length 100. Install with `cd engine && uv venv && uv pip install -e ".[dev]"`.
- [ ] **Step 2: Write the fixtures**, one envelope each, e.g. `hello.json` = `{"type":"hello","id":"1","ts":0,"payload":{"token":"abc"}}`; `status.json` contains all six light keys; `save_profile.json` contains a full valid profile (matching Task 2's fields).
- [ ] **Step 3: Write failing tests**
  - `test_all_fixtures_parse`: every file in `protocol/fixtures/` parses with `parse()`.
  - `test_status_fixture_matches_model`: `StatusPayload.model_validate(parse(status).payload)` succeeds and has 6 lights.
  - `test_make_roundtrip`: `parse(make("status", {"a": 1}, id="7"))` gives `type=="status"`, `id=="7"`, `payload=={"a":1}`, `ts>=0`.
  - `test_error_response_shape`: payload is `{"ok": False, "error": {"code": "bad", "message": "m"}}`.
  - `test_parse_rejects_garbage`: `parse("not json")` and `parse('{"ts":1}')` raise `ProtocolError`.
- [ ] **Step 4: Run** `cd engine && pytest tests/test_protocol.py -v` → FAIL (module missing).
- [ ] **Step 5: Implement `protocol.py`.**
- [ ] **Step 6: Run** the same command → PASS. Also run `ruff check .` → clean.
- [ ] **Step 7: Commit** `feat(engine): add protocol models and shared fixtures`.

### Task 2: Profile model and SQLite store

**Files:**
- Create: `engine/src/siegesense_engine/profile.py`, `engine/src/siegesense_engine/store.py`
- Test: `engine/tests/test_profile.py`, `engine/tests/test_store.py`

**Interfaces:**
- Produces:
  - `ADS_KEYS = ("1x", "2.5x", "3x", "4x", "5x", "12x")`
  - `WindowMode = Literal["fullscreen", "windowed", "borderless", "unknown"]`
  - `Profile(BaseModel)` fields and rules:
    - `in_game_name: str`: regex `^[A-Za-z0-9._-]{3,15}$`
    - `dpi: int`: 100–32000
    - `yaw_sensitivity: int`, `pitch_sensitivity: int`: 1–100
    - `mouse_multiplier_unit: float = 0.02`: >0, ≤1
    - `x_factor_aiming: float = 0.02`: >0, ≤1
    - `ads_sensitivity: dict[str, int] = {}`: keys ⊆ `ADS_KEYS`, values 1–200
    - `fov: float = 75.0`: 60–90
    - `resolution_width: int = 1920`, `resolution_height: int = 1080`: 640–7680 / 480–4320
    - `hud_scale: int = 100`: 50–100 (percent; entered manually)
    - `window_mode: WindowMode = "unknown"`
    - `counts_per_360: float | None = None` (filled by step 2's calibration)
  - `class Store`: `__init__(self, path: Path)` creates parent dirs, opens SQLite and runs migrations; `get_profile(self) -> Profile | None`; `save_profile(self, p: Profile) -> None`; `schema_version(self) -> int`; `close()`.
  - Schema v1: `meta(key TEXT PRIMARY KEY, value TEXT)` holding `schema_version`; `profiles(id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL, updated_at TEXT NOT NULL)` storing the profile as JSON. Migrations are an ordered list of SQL strings so later steps can append to it.

- [ ] **Step 1: Write failing tests**
  - `test_profile_validation` (parametrized): `dpi=0`, `in_game_name="ab"`, `"bad name!"`, `yaw_sensitivity=0`, `fov=120`, `ads_sensitivity={"7x":50}` each raise `ValidationError`; a valid profile from `protocol/fixtures/save_profile.json` passes.
  - `test_store_empty_returns_none`, `test_store_roundtrip` (save → new `Store` on the same file → equal profile), `test_store_overwrite` (second save replaces the first), `test_schema_version_is_1`.
- [ ] **Step 2: Run** `pytest tests/test_profile.py tests/test_store.py -v` → FAIL.
- [ ] **Step 3: Implement `profile.py` and `store.py`** (stdlib `sqlite3`, `check_same_thread=False`, a single connection guarded by a `threading.Lock`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): add player profile model and sqlite store`.

### Task 3: GameSettings.ini discovery and parser

**Files:**
- Create: `engine/src/siegesense_engine/gamesettings.py`
- Create: `engine/tests/fixtures/GameSettings_utf8.ini`, `GameSettings_utf16.ini`, `GameSettings_partial.ini`
- Test: `engine/tests/test_gamesettings.py`

**Interfaces:**
- Produces:
  - `@dataclass GameSettingsImport`: `values: dict[str, Any]` (keys are `Profile` field names), `missing: list[str]` (Profile field names not found), `source: str`
  - `def parse_game_settings(path: Path) -> GameSettingsImport`
  - `def find_game_settings(documents_dirs: list[Path]) -> list[dict]` → `[{"path": str, "modified": float}]` sorted newest first; searches `<doc>/My Games/Rainbow Six - Siege/*/GameSettings.ini`.
  - `def default_documents_dirs() -> list[Path]` → `~/Documents`, plus `~/OneDrive/Documents` if it exists.
- Key mapping (case-insensitive, searched in every section, first match wins):
  - `MouseYawSensitivity` → `yaw_sensitivity` (int)
  - `MousePitchSensitivity` → `pitch_sensitivity` (int)
  - `MouseSensitivityMultiplierUnit` → `mouse_multiplier_unit`
  - `XFactorAiming` → `x_factor_aiming`
  - `ADSMouseSensitivity1x` → `ads["1x"]`, `ADSMouseSensitivity2xHalf` → `ads["2.5x"]`, `ADSMouseSensitivity3x` → `ads["3x"]`, `ADSMouseSensitivity4x` → `ads["4x"]`, `ADSMouseSensitivity5x` → `ads["5x"]`, `ADSMouseSensitivity12x` → `ads["12x"]`
  - `DefaultFOV` → `fov` (float)
  - `ResolutionWidth` / `ResolutionHeight` → the resolution fields
  - `WindowMode` → `window_mode`: `0`→`fullscreen`, `1`→`windowed`, `2`→`borderless`, anything else → `unknown`
- Encoding: if the file starts with a UTF-16 BOM, decode as UTF-16; otherwise `utf-8-sig`, falling back to `latin-1`. Parse line by line (`key=value`, `[section]`, ignore `;`/`#` comments), not with `configparser`, so duplicate keys don't crash it. Values that don't parse go into `missing`.

- [ ] **Step 1: Write the fixtures.** `utf8` has every key; `utf16` is the same content saved as UTF-16-LE with BOM; `partial` has only `MouseYawSensitivity=12` and `[DISPLAY]` with `WindowMode=2`.
- [ ] **Step 2: Write failing tests**
  - `test_full_file` (`yaw_sensitivity==` the fixture value, `ads_sensitivity` has all 6 keys, `window_mode=="borderless"` or as fixture says)
  - `test_utf16_file` (same values as utf8)
  - `test_missing_keys_reported` (partial → `missing` contains `pitch_sensitivity` and `fov`, `values=={"yaw_sensitivity":12,"window_mode":"borderless"}`)
  - `test_case_insensitive_keys` (`mouseyawsensitivity=5` read)
  - `test_bad_value_goes_to_missing` (`DefaultFOV=abc`)
  - `test_find_game_settings` (tmp tree with two profile folders, newest first; missing dir → `[]`)
- [ ] **Step 3: Run** `pytest tests/test_gamesettings.py -v` → FAIL.
- [ ] **Step 4: Implement `gamesettings.py`.**
- [ ] **Step 5: Run** → PASS.
- [ ] **Step 6: Commit** `feat(engine): import sensitivity and display settings from GameSettings.ini`.

### Task 4: GameWatcher and StatusBoard

**Files:**
- Create: `engine/src/siegesense_engine/game_watcher.py`, `engine/src/siegesense_engine/status.py`
- Test: `engine/tests/test_status.py`

**Interfaces:**
- Produces:
  - `GAME_PROCESS_NAMES = ("RainbowSix.exe", "RainbowSix_BE.exe", "RainbowSix_Vulkan.exe")`
  - `@dataclass GameState`: `running: bool`, `focused: bool`
  - `class GameWatcher(Protocol)`: `def poll(self) -> GameState`
  - `class FakeGameWatcher`: `state: GameState` attribute, set by tests; `poll` returns it
  - `class PsutilGameWatcher`: `running` via `psutil.process_iter(["name"])` (case-insensitive name match); `focused` via `ctypes` `GetForegroundWindow` + `GetWindowThreadProcessId` on Windows, always `False` elsewhere
  - `def default_game_watcher() -> GameWatcher` → `PsutilGameWatcher()`
  - `class StatusBoard`: `__init__(self, watcher: GameWatcher, profile_getter: Callable[[], Profile | None])`; `def compute(self) -> StatusPayload`
- Light rules:
  - **game:**
    - not running → `warn`, "Siege not running", fix "Launch Rainbow Six Siege"
    - running and the profile's `window_mode=="fullscreen"` → `warn`, "Exclusive fullscreen", fix "Switch Siege to Borderless in Display settings so the overlay can show"
    - running and not focused → `ok`, "Siege running (in background)"
    - running and focused → `ok`, "Siege running"
  - **capture, input, hud, coach, voice:** `off`, detail "Arrives in a later update" (each later step replaces its light)
  - No profile → the game light still works as above; the profile requirement is shown by the wizard, not by a light.

- [ ] **Step 1: Write failing tests**
  - `test_game_not_running_warns`
  - `test_fullscreen_warns_with_fix` (asserts `"Borderless" in fix`)
  - `test_running_focused_ok`
  - `test_unbuilt_lights_off` (all five other keys `off`)
  - `test_psutil_watcher_not_running`: monkeypatch `psutil.process_iter` to return fake procs named `chrome.exe` → `running is False`; with `rainbowsix.EXE` → `running is True`
- [ ] **Step 2: Run** `pytest tests/test_status.py -v` → FAIL.
- [ ] **Step 3: Implement both modules.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(engine): detect Siege and report status lights`.

### Task 5: WebSocket server and CLI entry

**Files:**
- Create: `engine/src/siegesense_engine/server.py`, `engine/src/siegesense_engine/__main__.py`
- Test: `engine/tests/test_server.py`, `engine/tests/test_main.py`

**Interfaces:**
- Consumes: `protocol`, `Store`, `parse_game_settings`, `find_game_settings`, `default_documents_dirs`, `StatusBoard`, `GameWatcher`.
- Produces:
  - `class EngineServer`: `__init__(self, *, token: str, store: Store, watcher: GameWatcher, documents_dirs: list[Path], status_interval: float = 1.0)`; `async def start(self, port: int = 0) -> int` (binds `127.0.0.1`, returns the actual port); `async def stop(self)`.
  - Behaviour:
    - The first message must be `hello` with a matching token, otherwise close `4401` "unauthorized". After auth, reply `response(id, {"engine_version": __version__})` and immediately push one `status`.
    - Every `status_interval` seconds, push `status` to all authed clients, but only when it changed since the last push (always on connect).
    - `get_profile` → `{"profile": dict | None}`
    - `save_profile{profile}` → validate with `Profile`; on error `error_response(id, "invalid_profile", <first pydantic error message>)`; on success save it and return `{"profile": ...}`
    - `find_game_settings` → `{"files": [...]}`
    - `import_game_settings{path}` → `{"values":…, "missing":…, "source":…}`; a missing file gives `error_response(id, "not_found", ...)`
    - `get_status` → the StatusPayload
    - Unknown type → `error_response(id, "unknown_type", ...)`; malformed JSON → `error_response("", "bad_message", ...)` without closing the connection.
  - CLI: `python -m siegesense_engine --token T --data-dir D [--port 0] [--documents-dir P ...]`. It creates `Store(D / "siegesense.db")`, starts the server, then prints exactly `READY <port>` on its own line to stdout and flushes. It exits cleanly on SIGINT/SIGTERM or when stdin closes (the parent died).

- [ ] **Step 1: Write failing tests** (pytest-asyncio, `websockets.asyncio.client.connect`, `FakeGameWatcher`, tmp store):
  - `test_rejects_wrong_token` (close code 4401)
  - `test_rejects_non_hello_first_message` (4401)
  - `test_hello_then_status_push`
  - `test_save_and_get_profile`
  - `test_save_invalid_profile_errors` (`ok False`, code `invalid_profile`, connection still open)
  - `test_import_game_settings` (uses the Task 3 fixture)
  - `test_import_missing_file_not_found`
  - `test_unknown_type_errors`
  - `test_status_push_on_change` (flip `FakeGameWatcher.state.running`, with `status_interval=0.05` → receive a new status with game `ok`)
  - `test_main.py::test_cli_prints_ready`: start `sys.executable -m siegesense_engine --token t --data-dir tmp` with `subprocess.Popen`, read the first stdout line, match `^READY \d+$`, connect + hello OK, then terminate.
- [ ] **Step 2: Run** `pytest tests/test_server.py tests/test_main.py -v` → FAIL.
- [ ] **Step 3: Implement `server.py` and `__main__.py`.** Use `websockets.asyncio.server.serve`. Run blocking Store/file work with `asyncio.to_thread`. Watch stdin closing with a reader thread that calls `loop.call_soon_threadsafe(stop_event.set)`.
- [ ] **Step 4: Run** the whole engine suite `pytest -v` → all PASS; `ruff check .` clean.
- [ ] **Step 5: Commit** `feat(engine): serve authenticated websocket protocol`.

### Task 6: App scaffold, design tokens and protocol schemas

**Files:**
- Create: `app/package.json`, `app/electron.vite.config.ts`, `app/tsconfig*.json`, `app/vitest.config.ts`, `app/src/main/index.ts` (minimal window), `app/src/preload/index.ts` (empty bridge), `app/src/renderer/index.html`, `app/src/renderer/src/main.tsx`, `app/src/renderer/src/App.tsx`, `app/src/renderer/src/styles.css`, `app/src/shared/protocol.ts`
- Test: `app/tests/protocol.contract.test.ts`

**Interfaces:**
- Produces in `src/shared/protocol.ts` (zod, exporting both the schema and the inferred type):
  - `Envelope`, `LightState`, `Light`, `LightKey = "game"|"capture"|"input"|"hud"|"coach"|"voice"`, `StatusPayload`, `Profile` (same fields, ranges and regex as Task 2, camelCase **not** used; field names stay snake_case to match the wire), `ADS_KEYS`, `GameSettingsImport`, `GameSettingsFile`, `ErrorInfo`.
  - `ResponsePayload = {ok: true, data: unknown} | {ok: false, error: ErrorInfo}`.
- Design tokens in `styles.css` (Tailwind 4 `@theme`), the only place colours are defined:
  - `--color-bg: #0A0C0F`; `--color-surface: #111419`; `--color-surface-2: #181C23`; `--color-border: #242A33`
  - `--color-text: #E7EBF0`; `--color-muted: #8A94A3`
  - `--color-accent: #FF6A1A`; `--color-accent-strong: #FF8640`
  - `--color-ok: #22C55E`; `--color-warn: #F5A524`; `--color-error: #F04438`
  - `--font-sans: "Inter Variable"`; `--font-mono: "JetBrains Mono Variable"`
  - `--radius-card: 14px`
  - durations `--duration-fast: 150ms`, `--duration-base: 220ms`
- Scripts: `dev`, `build`, `typecheck` (`tsc --noEmit -p` for node and web), `test` (`vitest run`), `e2e` (`playwright test`), `lint` (`eslint .`).

- [ ] **Step 1: Scaffold** with `npm create @quick-start/electron@latest app -- --template react-ts` (or write the files by hand to the same layout), then add `tailwindcss @tailwindcss/vite zod zustand lucide-react motion @fontsource-variable/inter @fontsource-variable/jetbrains-mono` and dev deps `vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom ws @types/ws @playwright/test`. If the Electron binary download is blocked, set `ELECTRON_SKIP_BINARY_DOWNLOAD=1`, because unit and e2e tests don't need it. Remove the template's demo content.
- [ ] **Step 2: Write `styles.css`** with the tokens above, a base layer (`body` bg/text/font, `font-feature-settings: "tnum"` on `.font-mono`) and the custom scrollbar styling. `App.tsx` renders a placeholder "SiegeSense" heading using tokens.
- [ ] **Step 3: Write the failing contract test** `protocol.contract.test.ts`: for every JSON file in `../protocol/fixtures`, `Envelope.parse` succeeds; `status.json` payload passes `StatusPayload`; `save_profile.json` `payload.profile` passes `Profile`; `Profile.safeParse({...valid, dpi: 0}).success === false`.
- [ ] **Step 4: Run** `cd app && npm test` → FAIL (schemas missing).
- [ ] **Step 5: Implement `protocol.ts`.**
- [ ] **Step 6: Run** `npm test` and `npm run typecheck` → PASS. Run `npm run build` → succeeds.
- [ ] **Step 7: Commit** `feat(app): scaffold electron app with design tokens and protocol schemas`.

### Task 7: Engine process supervisor, preload bridge and WebSocket client

**Files:**
- Create: `app/src/main/engineProcess.ts`, `app/src/renderer/src/lib/engineClient.ts`
- Modify: `app/src/main/index.ts`, `app/src/preload/index.ts`
- Create: `app/src/renderer/src/env.d.ts` (types for `window.siegesense`)
- Test: `app/tests/engineProcess.test.ts`, `app/tests/engineClient.test.ts`

**Interfaces:**
- Produces:
  - `engineProcess.ts`:
    - `type EngineCommand = { command: string; args: string[]; cwd?: string }`
    - `function resolveEngineCommand(opts: { isPackaged: boolean; resourcesPath: string; appRoot: string }): EngineCommand`. In dev it returns `python` (`py -3` on win32, `python3` elsewhere) with `-m siegesense_engine`, `cwd = <appRoot>/../engine/src`. Packaged returns `<resourcesPath>/engine/siegesense-engine.exe` (step 6 builds it).
    - `function parseReadyLine(line: string): number | null` (`/^READY (\d+)\s*$/`)
    - `class EngineSupervisor extends EventEmitter`: `constructor(cmd: EngineCommand, opts: { dataDir: string; startTimeoutMs?: number /*15000*/; spawnFn?: typeof spawn })`; `start(): Promise<EngineConnection>`; `stop(): void`; `connection: EngineConnection | null`. Events: `"state"` with `EngineState = { phase: "starting"|"ready"|"restarting"|"failed"; message?: string }`.
    - The token is `randomBytes(24).toString("hex")`, passed via `--token`. Keep stdin open as a pipe so the engine exits when the app dies.
    - After an unexpected exit following ready, restart once; a second unexpected exit → `failed`, with the last 20 stderr lines in `message`.
  - `type EngineConnection = { port: number; token: string }`
  - Preload exposes `window.siegesense = { getEngine(): Promise<EngineConnection>, onEngineState(cb: (s: EngineState) => void): () => void, pickFile(filters?: {name: string; extensions: string[]}[]): Promise<string | null>, platform: string }` through IPC channels `engine:get`, `engine:state`, `dialog:pickFile`.
  - `engineClient.ts`:
    - `type ConnState = "connecting" | "open" | "reconnecting" | "closed"`
    - `class EngineClient`: `constructor(getConn: () => Promise<EngineConnection>, opts?: { WebSocketImpl?: typeof WebSocket; backoffMs?: number[] /*[250,500,1000,2000,4000]*/ ; requestTimeoutMs?: number /*8000*/ })`
    - Methods: `connect(): Promise<void>`; `request<T>(type: string, payload?: object): Promise<T>` (rejects with `EngineError(code, message)` on `ok:false` or timeout); `on(type: "status", cb: (p: StatusPayload) => void): () => void`; `onState(cb: (s: ConnState) => void): () => void`; `close(): void`.
    - It sends `hello` first and resolves `connect` on the hello response. Reconnecting re-calls `getConn()` (the port may change after a restart), cycling through the backoff list and staying on the last value. Pending requests reject with code `disconnected` on close.
- Main `index.ts`: frameless window (`titleBarStyle: "hidden"`, `titleBarOverlay` with `color: "#0A0C0F"`, `symbolColor: "#E7EBF0"`, `height: 40` on Windows), `minWidth 1100`, `minHeight 700`, bg `#0A0C0F`, show on `ready-to-show`. Start the supervisor with `dataDir = app.getPath("userData")` and forward its state to the renderer.

- [ ] **Step 1: Write failing tests**
  - `engineProcess.test.ts` (fake `spawnFn` returning an EventEmitter-based child with PassThrough streams):
    - `parses ready line` (`parseReadyLine("READY 51234\n") === 51234`, `"hi"` → null)
    - `resolves connection on ready`
    - `times out without ready line` (`startTimeoutMs: 50` → rejects, state `failed`)
    - `restarts once then gives up` (exit after ready → second spawn; exit again → `failed`)
    - `passes token and data dir args`
  - `engineClient.test.ts` (a real `ws` `WebSocketServer` on port 0 in the test, Node env, `WebSocketImpl` from `ws`):
    - `sends hello first`
    - `request resolves data`
    - `request rejects EngineError on ok false`
    - `request times out`
    - `delivers status events`
    - `reconnects after close` (the server closes the socket → state goes `reconnecting` → `open`, and hello is sent again)
- [ ] **Step 2: Run** `npm test` → FAIL.
- [ ] **Step 3: Implement** `engineProcess.ts`, `engineClient.ts`, the preload and the main wiring.
- [ ] **Step 4: Run** `npm test && npm run typecheck` → PASS.
- [ ] **Step 5: Commit** `feat(app): supervise engine process and connect over websocket`.

### Task 8: Design-system components and app shell

**Files:**
- Create: `app/src/renderer/src/components/ui/{Button,Card,Field,StatusLight,Stepper,Badge,Tooltip}.tsx`, `components/shell/{TitleBar,Sidebar,EngineBanner}.tsx`, `lib/engineContext.tsx`, `store/nav.ts`, `pages/{Home,Live,Review,Progress,Settings}.tsx`
- Modify: `App.tsx`
- Test: `app/tests/ui.test.tsx`, `app/tests/shell.test.tsx`

**Interfaces:**
- Consumes: `EngineClient`, `StatusPayload`, `Light`, `Profile`.
- Produces:
  - `Button` props: `variant: "primary"|"secondary"|"ghost"`, `size: "sm"|"md"|"lg"`, `icon?: LucideIcon`, `loading?: boolean` + native button props. The primary variant uses the accent with a subtle glow on hover.
  - `Card`: `title?`, `action?`, `children`
  - `Field`: `label`, `hint?`, `error?`, `suffix?` + input props (the error is shown in `--color-error` with `role="alert"`)
  - `StatusLight`: `{ lightKey: LightKey; light: Light }` → a coloured dot with a pulse animation when `warn`/`error`, plus label. Tooltip shows `detail` and `fix`. `aria-label = "<label>: <detail>"`.
  - `Stepper`: `steps: string[]`, `current: number`
  - `Badge`: `tone: "neutral"|"ok"|"warn"|"error"|"accent"`
  - `store/nav.ts`: zustand `useNav` with `page: "home"|"live"|"review"|"progress"|"settings"|"setup"` and `go(page)`
  - `engineContext.tsx`: `EngineProvider` (creates one `EngineClient` from `window.siegesense.getEngine`. In a plain browser it falls back to the `?port=&token=` URL params for e2e). Hooks: `useEngine(): EngineClient`, `useConnState(): ConnState`, `useStatus(): StatusPayload | null`, `useProfile(): { profile: Profile | null; loading: boolean; reload(): Promise<void> }`.
- Shell layout:
  - `TitleBar` (40 px, draggable, app logo mark + "SiegeSense", leaves room for the native controls)
  - `Sidebar` (Home, Live, Review, Progress, Settings with lucide icons; the active item has an accent bar; a compact status-light row sits at the bottom)
  - `EngineBanner` on top of content: "Reconnecting to engine…" when `reconnecting`; red "Engine stopped" with the message and a "Restart app" hint when the supervisor state is `failed`
- Pages: `Home` shows a hero card with **Start Live Mode** and **Start Warm-up** (disabled, tooltip "Arrives in a later update"), a status card with all six `StatusLight`s, and a profile summary card (name, DPI, sensitivity, eDPI = `dpi*yaw_sensitivity`) with an "Edit setup" button → `go("setup")`. `Live`, `Review` and `Progress` show a designed empty state (icon, title, one line saying what's coming). `Settings` shows the profile summary + "Re-run setup".
- App routing: when `useProfile().profile === null` after loading → force `setup`.
- Page transitions: `motion` fade + 6 px slide, 220 ms.

- [ ] **Step 1: Write failing tests** (jsdom, a fake `EngineClient` object implementing the same public methods)
  - `ui.test.tsx`: `StatusLight shows fix in tooltip` (hover → text contains fix), `Field shows error with role alert`, `Button loading disables`.
  - `shell.test.tsx`: `redirects to setup when no profile`, `home shows six status lights`, `shows reconnecting banner` (fake client emits `reconnecting`), `sidebar navigates to review`, `eDPI computed` (dpi 800 × sens 10 → "8000").
- [ ] **Step 2: Run** `npm test` → FAIL.
- [ ] **Step 3: Implement** the components, shell and pages.
- [ ] **Step 4: Run** `npm test && npm run typecheck` → PASS.
- [ ] **Step 5: Commit** `feat(app): add design system components and app shell`.

### Task 9: Setup wizard

**Files:**
- Create: `app/src/renderer/src/pages/setup/{SetupWizard,StepWelcome,StepPlayer,StepSensitivity,StepDisplay,StepDone}.tsx`, `pages/setup/draft.ts`
- Modify: `App.tsx` (route `setup`)
- Test: `app/tests/setup.test.tsx`

**Interfaces:**
- Consumes: `useEngine`, `useProfile`, `Profile` schema, `window.siegesense.pickFile`, engine requests `find_game_settings`, `import_game_settings`, `save_profile`.
- Produces:
  - `draft.ts`: `type ProfileDraft = Partial<Profile>`; `function validateStep(step: "player"|"sensitivity"|"display", d: ProfileDraft): Record<string, string>` returns field → message using the zod `Profile` field schemas
  - `const WIZARD_STEPS = ["Welcome", "Player", "Sensitivity", "Display", "Done"]`. Later steps (Calibration, HUD check, Voice, AI) are inserted here by later plans.
- Step behaviour:
  - **Welcome:** what SiegeSense does + the fair-play promise in one line ("SiegeSense only sees your screen and your own mouse — it never touches the game."). Primary button "Get started".
  - **Player:** in-game name field. Inline error for an invalid name: "3–15 characters: letters, numbers, . _ -".
  - **Sensitivity:**
    - On mount, call `find_game_settings`. If files are found, show them as selectable cards ("Found your Siege settings" + modified date) with the newest preselected and an **Import** button. Always offer "Browse…" (`pickFile` with `ini` filter).
    - After import, fill the fields and show a Badge per field: "Imported" (`accent`), or "Not found — enter manually" (`warn`) for `missing`.
    - Fields: DPI (required, not in the file; hint "Check your mouse software"), yaw/pitch sensitivity, and the ADS values in a collapsible "Scopes (ADS)" section. Live eDPI readout.
  - **Display:**
    - Resolution width/height, FOV, HUD scale.
    - If `window_mode` is `fullscreen`, show a warn callout "Switch Siege to Borderless so the in-game overlay can show"; if `borderless`, show an ok callout.
  - **Done:** summary of everything, **Save profile** → `save_profile`. On `EngineError` show the message in a callout and stay; on success `reload()` the profile and `go("home")`.
  - Next is disabled while `validateStep` returns errors; Back keeps the draft. When re-running setup, the draft starts from the existing profile.
  - The `Stepper` sits at the top, with steps animating horizontally (220 ms).

- [ ] **Step 1: Write failing tests** (fake client with scripted responses)
  - `blocks next on invalid name` ("ab" → Next disabled + message visible)
  - `imports found settings` (`find_game_settings` returns 1 file → click Import → yaw field shows the imported value and the "Imported" badge; missing `fov` shows the warn badge)
  - `browse uses pickFile`
  - `requires dpi`
  - `fullscreen shows borderless warning`
  - `saves profile and goes home` (asserts the `save_profile` payload equals the expected full profile)
  - `shows engine error on save failure` (`EngineError("invalid_profile","dpi too low")` → text visible, still on Done)
  - `prefills from existing profile`
- [ ] **Step 2: Run** `npm test` → FAIL.
- [ ] **Step 3: Implement** the wizard.
- [ ] **Step 4: Run** `npm test && npm run typecheck` → PASS.
- [ ] **Step 5: Commit** `feat(app): add first-run setup wizard`.

### Task 10: End-to-end test, CI and README

**Files:**
- Create: `app/playwright.config.ts`, `app/tests/e2e/setup.spec.ts`, `.github/workflows/ci.yml`, `README.md`, `.gitignore`

**Interfaces:**
- Consumes: everything above.
- E2E setup:
  - Playwright `globalSetup` starts the real engine (`python -m siegesense_engine --token e2e --data-dir <tmp> --documents-dir <tmp/docs>`, with the Task 3 utf8 fixture copied to `<tmp/docs>/My Games/Rainbow Six - Siege/abc/GameSettings.ini`) and reads the READY port.
  - `webServer` runs the renderer with `vite` (electron-vite `dev:web` or a renderer-only vite config).
  - Tests open `/?port=<p>&token=e2e`.

- [ ] **Step 1: Write the failing e2e test** `setup.spec.ts`: `first run completes setup and shows home`. Fresh data dir → the wizard appears → enter name `Ash.Main` → Sensitivity shows the found file → Import → enter DPI 800 → Display → Done → Save → Home shows "Ash.Main" and eDPI. Reloading the page stays on Home (the profile persisted in the real SQLite).
- [ ] **Step 2: Run** `cd app && npm run e2e` → FAIL until the config and the browser fallback are wired, then fix until it passes. Use the preinstalled Chromium; don't run `playwright install`.
- [ ] **Step 3: Write `ci.yml`.** Jobs `engine` (ubuntu, Python 3.12, `pip install -e engine[dev]`, `ruff check engine`, `pytest engine`) and `app` (ubuntu, Node 22, `npm ci`, `npm run typecheck`, `npm test`, `npx playwright install --with-deps chromium`, `npm run e2e`), plus `ELECTRON_SKIP_BINARY_DOWNLOAD=1`.
- [ ] **Step 4: Write `README.md`.** What SiegeSense is, the fair-play promise, project layout, dev setup on Windows (Python 3.12+, Node 22, `pip install -e engine[dev]`, `cd app && npm install && npm run dev`), how to run the tests, and the roadmap (the 6 build steps with step 1 ticked). Write `.gitignore` (node_modules, out, dist, .venv, __pycache__, *.db, test-results, playwright-report).
- [ ] **Step 5: Run the full suite** `cd engine && pytest && ruff check . && cd ../app && npm run typecheck && npm test && npm run e2e` → all PASS.
- [ ] **Step 6: Commit** `test: add end-to-end setup flow, CI and README`.
