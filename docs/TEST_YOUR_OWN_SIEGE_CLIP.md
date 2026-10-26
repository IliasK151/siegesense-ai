# Test SiegeSense AI with your own Siege recording

This is the fastest path to test the current preview on Windows. It processes a recording saved to disk; it does not observe live gameplay, read game memory, overlay the game, or control your mouse.

## 1. Get the source

Open the private repository while signed in to GitHub:

https://github.com/IliasK151/siegesense-ai/tree/feat/annotated-sequence-metrics

Use Code → Download ZIP, then extract the folder to a normal local directory (for example, C:\Dev\siegesense-ai). Keep recordings, sampled frames, annotation files, and reports outside Git.

## 2. Install and launch

Install Python 3.12 for Windows from python.org, including the Python Launcher. Then double-click `START_SIEGESENSE.bat` in the extracted project folder. On first run, the launcher creates a local `.venv`, installs the application, test/lint tools, and OpenCV, and starts the app. The initial dependency installation needs an internet connection.

You can also run the setup and launch steps from PowerShell:

```powershell
.\scripts\setup_windows.ps1
.\scripts\run_windows.ps1
```

To run tests and lint, double-click `CHECK_SIEGESENSE.bat` or run this in PowerShell:

```powershell
.\scripts\check_windows.ps1
```

To build a local Windows x64 preview ZIP after those checks pass:

```powershell
.\scripts\package_windows.ps1
```

The ZIP is written to dist\SiegeSenseAI-Windows-x64.zip. The package script runs the test/lint checks and a packaged-app startup smoke test before creating the ZIP. This local package still needs a real-media playback check on the machine where it will be used.

## 3. Prepare a short recording

Use a short clip from a match you recorded and are allowed to analyze. Start with a clip where the reticle and opponent are reasonably visible. Make sure the recording file plays in a normal media player first. Do not add the video or sampled images to the Git repository.

## 4. Sample the video

1. In SiegeSense AI, open **Clip Annotation**.
2. Choose **Select gameplay video** and select the recording.
3. Choose a new, empty output folder, or keep the suggested video-name frames folder.
4. Leave the sampling interval at its default **100 ms** for the first pass, then choose **Sample frames**. Sampling at 100 ms yields about 10 sampled frames per second when successful; it can miss faster events and is not precise flick timing.
5. If sampling succeeds, the generated sampling_manifest.json should load into the annotation workspace automatically. If it does not, use the manifest picker to select it.

Use a separate output folder for each recording or sampling run. Do not select the source recording itself as the output folder.

## 5. Review a small sequence

1. Select a readable frame and add the best label for what is actually visible. Use **ambiguous** or **unusable frame** rather than guessing.
2. For spatial review, choose **Mark reticle**, click the visible reticle center, choose **Mark target**, and click a consistent reference point on the opponent (for example, torso center). Save the annotation after marking the points.
3. Review adjacent sampled frames when considering movement. A still frame or a pair of sparse samples cannot prove that the mouse overshot, a shot missed, or a sensitivity value is wrong.
4. Save several annotations and try moving to another frame and back to confirm that the local marks persisted.

Follow the annotation guide (ANNOTATION_GUIDE.md) for label definitions and point-marking limitations.

## 6. Export and check the results

Use **Export local evaluation report…** to save a JSON report. The spatial report summarizes manually marked target-minus-reticle offsets. For adjacent frames showing the same clearly identifiable opponent, enter the same short **Target / sequence ID** (for example, `target-a`) before saving each annotation. Leave the field blank when you cannot confidently track the same opponent. The aim-transition report counts offset sign changes only when the same manually assigned target ID is present on consecutive samples at the known sampling interval. **Analyze screen-space motion…** exports visible image-feature motion, which is not mouse input.

The current reports are experimental/manual-analysis outputs. They are not automatic reticle detection, opponent detection, mouse-input measurement, validated overshoot detection, aim accuracy, hit probability, rank, or skill scores.

## 7. Try the coaching-to-settings loop

1. Open **Session Review**, create a real review session, and link a saved Clip Annotation to it or add timestamped observations directly.
2. When recording a review note, use the **Add a coaching tag** dropdown for what is visible (for example, `overflick`, `underflick`, `crosshair-placement`, `movement`, or `positioning`). Do not tag a clip with a diagnosis you cannot support.
3. Open **AI Coach**. Select a tagged pattern to read its evidence level, source notes, and one practice block.
4. A single note should not enable a settings experiment. When an overflick, underflick, or correction tag appears in multiple sessions, the coach can offer **Prepare a controlled settings experiment**. It fills a draft only; it does not assert that your current sensitivity is wrong.
5. Open **Settings Lab**. Confirm every displayed value against the actual game/mouse configuration before saving a baseline. The settings fields include horizontal/vertical sensitivity, ADS values, mouse DPI, and `MouseSensitivityMultiplierUnit`. Save a baseline snapshot, change exactly one game setting yourself, save a test snapshot, select the pair, and compare them. Keep scope, weapon, range, and drill as similar as practical. Record the observed result, including inconclusive results.

The preview never changes game configuration or mouse software settings. Legacy snapshots saved before the DPI/multiplier fields were added may not be comparable with new full snapshots; create a fresh pair of baseline/test snapshots for experiments.

## 8. What to send back when something fails

Keep the recording private. Report the exact step that failed, the full error message, your Windows version, python --version from the active virtual environment, and whether the check_windows.ps1 script passes. Do not upload a recording or screenshots containing sensitive information unless you explicitly choose to share them.

For a sampling or playback problem, also mention the file type (for example, MP4 or MKV), video resolution, nominal frame rate, whether a normal media player can play it, and whether other clips work. Avoid sharing the video itself unless necessary and explicitly intended.


## Import the real settings before an experiment

The Settings Lab **Import GameSettings.ini…** button reads a selected configuration file without changing it. The default Windows location is commonly `Documents\My Games\Rainbow Six - Siege\<profile-id>\GameSettings.ini`; Ubisoft documents this path in its [PC data-centre settings guide](https://www.ubisoft.com/en-us/help/rainbow-six-siege/purchases-and-rewards/article/changing-your-data-centre-manually-in-rainbow-six-siege-pc/000060594).

The importer maps only explicit entries it can safely associate with the fields: horizontal/vertical sensitivity, `MouseSensitivityMultiplierUnit`, `ADSMouseMultiplierUnit`, global ADS sensitivity, and the exact 1x ADS key. It reports but does not guess other per-scope keys (for example, a `2x` key is not assumed to mean a `2.5x` UI value). DPI is not in `GameSettings.ini`, so verify it in your mouse software and enter it manually. Confirm all fields against your in-game settings before saving snapshots. The importer only reads; it never applies settings or writes to the game.
