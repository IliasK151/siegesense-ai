# Contributing

## Working agreement

1. Read the relevant product and architecture docs before implementing a feature.
2. Link each substantial change to a GitHub Issue.
3. Create a focused branch; avoid unrelated cleanup in feature branches.
4. Add or update tests for behaviour changes.
5. Run checks locally and report the actual results.
6. Open a pull request describing motivation, implementation, verification, screenshots for UI changes, and limitations.
7. Merge only when checks pass and the diff has been reviewed.

## Pull request checklist

- [ ] Linked issue and clear scope
- [ ] Acceptance criteria met
- [ ] Tests added/updated and run
- [ ] No real/demo data mixing
- [ ] No secrets, tokens, personal recordings, or machine-specific paths committed
- [ ] UI states checked at small and large window sizes (if applicable)
- [ ] Accessibility and keyboard behaviour considered
- [ ] Documentation and changelog updated when relevant
- [ ] Fair-play and privacy boundaries preserved

## Coding conventions

- Prefer small modules and typed domain models.
- Keep Qt widgets focused on presentation.
- Keep persistence and calculations outside UI widgets.
- Use descriptive names and explain non-obvious trade-offs.
- Never swallow exceptions silently; show useful user-facing errors and retain diagnostic context without leaking sensitive paths or content.
- Avoid adding a dependency without a clear purpose.

## Reporting a bug

Include expected behaviour, actual behaviour, reproduction steps, application/Python versions, relevant logs with sensitive information removed, and whether the issue occurs with demo data.
