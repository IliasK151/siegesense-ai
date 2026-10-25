# Architecture

## Target shape

The codebase should separate presentation from application logic and persistence. Keep the initial implementation small, but avoid placing all pages, storage, analysis, and global shortcuts into one giant window class.

```text
src/siegesense/
  app.py                 # application entry point and dependency wiring
  ui/
    shell.py             # navigation, page host, global layout
    theme.py             # design tokens and shared stylesheet helpers
    components/          # reusable cards, tables, charts, empty states
    pages/               # overview, aim lab, movement, settings lab, review, coach, preferences
  domain/
    models.py            # sessions, observations, metrics, experiments
    rules.py             # validation and provenance rules
  services/
    session_service.py
    experiment_service.py
    coaching_service.py
  storage/
    database.py          # connection lifecycle
    migrations/          # schema migrations
    repositories.py      # persistence queries
  analysis/
    recorded_video.py    # future offline/recorded-footage analysis
    metrics.py           # validated metric calculations
tests/
  unit/
  integration/
docs/
```

This is a target layout, not a claim that all modules already exist.

## Boundaries

- **UI:** renders state and sends user intent to services; no SQL or metric calculations inside widgets.
- **Domain:** typed records and validation rules independent of Qt.
- **Services:** coordinate workflows and produce explicit success/error results.
- **Storage:** local persistence behind repository interfaces; schema changes use migrations.
- **Analysis:** deterministic calculations with tests, input requirements, units, and confidence/validity metadata.
- **Coaching:** converts supported observations into explainable suggestions; never invents measurements.

## Persistence

Move from ad-hoc JSON files to SQLite only through a planned migration. Preserve existing user data, back up before migration, version the schema, and test upgrade and rollback/failure behaviour. Never silently overwrite a user's records.

Suggested core entities:
- PlayerProfile
- Session
- MediaAsset (path/reference and metadata, not necessarily copied video bytes)
- Observation
- MetricResult
- SettingsSnapshot
- SettingsExperiment
- CoachingNote
- DataSource / provenance metadata

Demo data should be generated in a separate namespace or tagged in a way that all queries can reliably exclude it from real-session analytics.

## Media and screen capture

Start with user-selected recorded footage. Any future screen capture must be opt-in and visibly indicated, with explicit stop controls. Avoid background capture by default. Do not inspect protected game memory, inject into the game, or send automated gameplay input.

## Concurrency and shortcuts

Qt UI updates must occur on the GUI thread. If global shortcuts are implemented, isolate platform-specific registration, handle permission/failure paths, unregister cleanly on exit, and test that callbacks dispatch safely to the UI thread. Do not imply that a shortcut enables a vision engine until that engine exists.

## Quality gates

- Unit tests for domain rules and metric calculations.
- Persistence tests using temporary databases.
- UI smoke tests for navigation and startup.
- Lint/type checks added as the codebase stabilises.
- Pull requests include verification evidence and note known limitations.


## Implemented foundation snapshot

The initial domain/storage increment now provides:
- Immutable typed records for sessions, observations, metric results, settings snapshots, and experiments.
- SQLite schema version 1 with foreign keys and migration metadata.
- Repository methods that exclude demo records by default.
- Validation that observations and metrics match the parent session's demo provenance.
- Metric provenance fields (source, method, unit, validity) and nullable values for missing measurements.
- Local data path resolution without creating files during module import.

This is the first persistence increment, not yet a migration/import of the older JSON data. Before connecting it to the UI, add explicit backup/import tooling and additional migration-failure tests.


## Application lifecycle and local paths

The feature branch now resolves a per-user data directory without filesystem side effects during module import. The SQLite constructor creates the parent directory only when the database is opened. Windows uses Local AppData (falling back to AppData or the user's Local AppData convention); macOS uses Application Support; Linux respects XDG_DATA_HOME and otherwise uses ~/.local/share.

The application bootstrap opens one database, constructs the session service, injects that service into the main window, and closes the database on application shutdown. If opening the database fails, startup shows an explicit error instead of silently continuing with an unusable persistence layer.

The UI has only received the dependency-injection seam so far; session review controls are not yet wired to CRUD operations. Existing MVP data migration remains blocked on obtaining the original source/schema.


## Settings workflow service

A UI-independent settings service now creates and lists settings snapshots and records experiments that reference explicit baseline/test snapshots. The service delegates validation and persistence to the repository layer. It does not apply settings to the game, collect hidden game state, or claim that a change improved performance; outcomes must be recorded by the user and supported by their own review.
