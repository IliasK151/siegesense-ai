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
