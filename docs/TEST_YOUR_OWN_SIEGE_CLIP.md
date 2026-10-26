# Test SiegeSense AI with your own Siege recording (Windows)

This preview reviews recordings saved to disk. It does not attach to live gameplay, read protected game memory, overlay the game, or control your mouse. Aim-related summaries are manual-review evidence—not automatic aim diagnosis.

## 1. Download the current build

Open the public feature branch here:

https://github.com/IliasK151/siegesense-ai/tree/feat/usable-coach-workflow

Choose **Code → Download ZIP**, then extract it into a **new folder** such as C:\Dev\siegesense-ai-coach. Do not reuse the older extracted folder; it will not magically update. Keep recordings, sampled frames, annotations and reports outside Git.

## 2. Run setup and checks

Install Python 3.12 for Windows from the official [Python downloads page](https://www.python.org/downloads/windows/) if it is not already installed, and include the Python Launcher. From the extracted folder, double-click START_SIEGESENSE.bat first. On first launch it creates a project-local environment and installs app, developer, and vision dependencies; this requires an internet connection. When the app opens, confirm it starts, then close it and double-click CHECK_SIEGESENSE.bat to run the local test suite and Ruff lint checks.

If either file exits with an error, copy the entire terminal output. Do not assume a startup alone means tests or video playback passed.

## 3. Prepare a short recording

Use a short match recording you are allowed to review. Choose a clip where the reticle and visible opponents are reasonably clear, and verify the video opens in a normal media player first. Do not add the recording or sampled images to the repository.

## 4. Start a review with drag and drop

1. On **Overview**, drag your gameplay video onto the large drop area, or click **Choose a video**. You can also use the same drop area on **Clip Annotation**.
2. SiegeSense samples frames in the background at the default **500 ms** interval (about 2 frames per second). It creates a new folder beside the source recording named like \`gameplay_siegesense_review\`; if that folder already exists, it uses a numbered alternative rather than overwriting it.
3. When sampling finishes, the app creates or reuses a local review session, loads the video into **Session Review**, and opens the video player. Press **Play** when you're ready to watch the recording.
4. Choose **Open sampled-frame review** on the playback panel to move into **Clip Annotation**, where the first sampled frame is already selected. Your frame labels and notes remain local and are still entered manually.
5. Use **Advanced options** on the drop panel only if you need to change the interval, choose a different output folder, or load an existing \`sampling_manifest.json\`.

The default interval is intended for lightweight browsing and manual review, not precise event timing. Very long videos can take longer to sample and use more disk space, although the app stays responsive while sampling. The source video is never modified or uploaded.
## 5. Mark a small sequence

1. Select a readable frame and assign the best label for what is actually visible. Use **ambiguous** or **unusable** instead of guessing.
2. For spatial review, choose **Mark reticle**, click the reticle center, choose **Mark target**, and click a consistent reference point on the opponent.
3. Enter the same **Target / sequence ID** only for frames where you can confidently identify the same visible opponent throughout one continuous sequence. Leave it blank when identity is uncertain.
4. Save the annotation. Review two or more adjacent samples and confirm the labels and marks persist when you switch frames.

These coordinates and IDs are manually entered. The app does not automatically detect or track opponents.

## 6. Export and interpret reports cautiously

Use **Export local evaluation report…** for annotation coverage. The spatial report describes manually marked target-minus-reticle offsets. **Export manual aim-transition report…** counts horizontal/vertical offset sign changes only when the same manual target ID has complete point pairs at exactly one known sample interval apart. **Analyze screen-space motion…** estimates visible image-feature displacement between frames.

None of these metrics measures mouse input, proves overflick/underflick, determines hit/miss, or gives an aim-accuracy or skill score. Camera motion, opponent movement, animation and sparse sampling can confound the measurements. Treat reports as prompts to inspect the original video.

## 7. Try the review-to-coaching workflow

1. Open **Session Review** and create/select a real review session.
2. Add a concise timestamped observation and use **Add a coaching tag** for only what you can support from the footage (for example, \`overflick\`, \`underflick\`, \`crosshair-placement\`, \`movement\`, or \`positioning\`).
3. Open **AI Coach** and select a pattern to see the evidence level, linked notes, and one practice block.
4. A single note is not a recurring pattern. The experiment handoff is enabled only for supported aim tags across multiple sessions; it creates an editable hypothesis and never claims the current setting is wrong.

This is deterministic, tag-based guidance—not a trained AI model or automatic reticle/opponent detector.

## 8. Import settings safely and compare experiments

In **Settings Lab**, click **Import GameSettings.ini…** and choose the active profile file. The common default location is:

\`Documents\My Games\Rainbow Six - Siege\<profile-id>\GameSettings.ini\`

Ubisoft documents this location in its [PC data-centre settings guide](https://www.ubisoft.com/en-us/help/rainbow-six-siege/purchases-and-rewards/article/changing-your-data-centre-manually-in-rainbow-six-siege-pc/000060594). The importer is read-only: it never writes or applies changes to the game.

The importer maps only known fields: horizontal/vertical sensitivity, \`MouseSensitivityMultiplierUnit\`, \`ADSMouseMultiplierUnit\`, global ADS sensitivity, and the exact 1x ADS key. It does **not** assume a config key named \`2x\` or \`3x\` corresponds to a UI field named \`2.5x\`, \`3.5x\`, or \`8x\`. Those fields are left for manual confirmation. DPI is not in \`GameSettings.ini\`; verify it in your mouse software and enter it yourself.

Review every populated and unchanged field against the active in-game configuration before saving a baseline. Save a fresh baseline and test snapshot with the same context, change exactly one value yourself, then compare the pair and record what you observed—including inconclusive results. Old snapshots may not contain the new DPI/multiplier fields, so create a fresh pair for new experiments. The tool never edits your game config or mouse settings.

## 9. If anything fails

Keep the recording private. Send the exact step, the full error message, your Windows version, \`py -3.12 --version\`, and the output from \`CHECK_SIEGESENSE.bat\`. For video problems, also report the file type (MP4/MKV/etc.), resolution and nominal frame rate, whether the recording plays in a normal player, and whether another clip works. Do not send the recording itself unless you explicitly choose to share it.
