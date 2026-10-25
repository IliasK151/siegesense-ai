# Decision Log

Record consequential decisions here. For larger decisions, add a separate numbered ADR under `docs/adr/`.

## D-001 — Python and PySide6 desktop direction
**Status:** Accepted for initial milestone  
**Decision:** Windows-first desktop app using Python and PySide6.  
**Reason:** Matches the existing MVP direction and supports a native desktop workspace.  
**Revisit when:** Packaging, performance, accessibility, or platform needs show a concrete reason to change.

## D-002 — Local-first data handling
**Status:** Accepted  
**Decision:** Session records and observations are local by default. No automatic upload of recordings.  
**Reason:** Gameplay footage and personal performance history can be sensitive.

## D-003 — Bright professional design system
**Status:** Accepted  
**Decision:** Warm whites, soft grey panels, charcoal text, restrained violet accent; dense but readable analytics; compact collapsible sidebar.  
**Reason:** A high-quality analytics workspace should prioritise legibility and hierarchy over visual effects.

## D-004 — Demo data isolation
**Status:** Accepted  
**Decision:** Demo mode must be visibly labelled and structurally excluded from real progress calculations.  
**Reason:** Synthetic examples must never be mistaken for player results.

## D-005 — Recorded footage before live vision
**Status:** Accepted for first milestone  
**Decision:** Begin with recorded-footage review and manual observations. Add computer vision only as separately validated capabilities.  
**Reason:** Makes measurement limitations easier to test and avoids pretending that live analysis already exists.

## D-006 — Fair-play constraints
**Status:** Accepted  
**Decision:** No game-memory reading, process injection, automated gameplay inputs, or silent game-settings changes.  
**Reason:** The product is for coaching, review, and deliberate practice—not gameplay automation. Any live integration needs a separate review against current game rules.
