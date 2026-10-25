# Data and Privacy Contract

## Default behaviour

- Session records, observations, settings snapshots, experiments, and local preferences are stored on the user's device.
- Demo records must be explicitly marked and excluded from personal metrics, coaching summaries, and exports by default.
- No gameplay footage or notes are uploaded to a remote service by default.
- No game-memory reading, code injection, automated gameplay input, or silent in-game settings changes are part of the product.
- Recording paths are references to user-selected files; the app should not copy or upload footage without clear user intent.

## Evidence contract

Every performance metric must document its definition, units, collection method, source, and limitations. Manual observations are not equivalent to detected events. A category count is not a diagnosis, and an experiment outcome is not proof of causality.

## Retention and deletion

Users must be able to locate their data directory, export session notes, and delete local records through a clearly labelled action. Deletion should be confirmed before destructive operations. Database migrations must preserve a backup and never overwrite an unrecognised schema.

## Future model or cloud features

Before introducing remote inference or third-party services, add an explicit opt-in, list what data leaves the device, explain retention and provider handling, and provide an offline fallback where feasible. Never send recorded footage or personal notes to a remote provider silently.

## Fair-play boundaries

Start with recorded footage and user-tagged observations. Any future live-screen capture or game-specific integration requires a separate fair-play, anti-cheat, platform-terms, and privacy review. Never bypass anti-cheat or read protected game memory.
