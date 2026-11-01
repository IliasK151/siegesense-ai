"""Writes tests/fixtures/warmup_replay.jsonl: a synthetic 12-flick warm-up for the e2e test.

Run from engine/: python tests/make_replay.py
Counts use the e2e profile's estimated conversion (yaw 12 x 0.02 x 0.0572957795 deg/count).
"""

import json
from pathlib import Path

from synth import end_time, flick, to_counts

DEG_PER_COUNT = 12 * 0.02 * 0.0572957795
OUT = Path(__file__).parent / "fixtures" / "warmup_replay.jsonl"


def main() -> None:
    lines = [{"k": "k", "t": 0.0, "vk": 0x91, "d": 0}]  # anchor so the first flick starts at 1 s
    t = 1.0
    for i in range(12):
        samples = flick(
            t, 30, 0.12, angle_deg=0 if i % 2 == 0 else 180, overshoot=6 if i < 5 else 0
        )
        for m in to_counts(samples, DEG_PER_COUNT):
            lines.append({"k": "m", "t": round(m.t, 6), "dx": m.dx, "dy": m.dy})
        shot = round(end_time(samples) + 0.1, 6)
        lines.append({"k": "b", "t": shot, "b": "left", "d": 1})
        lines.append({"k": "b", "t": round(shot + 0.08, 6), "b": "left", "d": 0})
        t += 1.2
    OUT.write_text("\n".join(json.dumps(x, separators=(",", ":")) for x in lines) + "\n")


if __name__ == "__main__":
    main()
