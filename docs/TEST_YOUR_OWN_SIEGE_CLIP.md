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

Use **Export local evaluation report…** to save a JSON report. The spatial report summarizes the manually marked target-minus-reticle offsets. **Analyze screen-space motion…** can export a separate JSON report of visible image-feature movement.

The current reports are experimental/manual-analysis outputs. They are not automatic reticle detection, opponent detection, mouse-input measurement, validated overshoot detection, aim accuracy, hit probability, rank, or skill scores.

## 7. What to send back when something fails

Keep the recording private. Report the exact step that failed, the full error message, your Windows version, python --version from the active virtual environment, and whether the check_windows.ps1 script passes. Do not upload a recording or screenshots containing sensitive information unless you explicitly choose to share them.

For a sampling or playback problem, also mention the file type (for example, MP4 or MKV), video resolution, nominal frame rate, whether a normal media player can play it, and whether other clips work. Avoid sharing the video itself unless necessary and explicitly intended.
