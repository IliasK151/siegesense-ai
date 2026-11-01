"""Writes a synthetic two-round match video for the Live Mode end-to-end test.

Round 1: prep → action → you eliminate Thermite_1 → Bandit.X kills you → round lost.
Round 2: prep → action → round won.
Usage (from engine/): python tests/make_live_replay.py OUT.mp4
"""

import sys
from fractions import Fraction

import av
from hudsynth import render

FPS = 15
SIZE = (1280, 720)
MY_KILL = ("Ash.Main", "blue", "Thermite_1", "orange")
MY_DEATH = ("Bandit.X", "orange", "Ash.Main", "blue")


def state_at(t: float) -> dict:
    if t < 1.0:
        return {"timer": None, "score": (0, 0), "health": 100, "kills": []}
    if t < 4.0:  # round 1 prep
        return {"timer": int(45 - (t - 1.0)), "score": (0, 0), "health": 100, "kills": []}
    if t < 12.0:  # round 1 action
        kills = []
        if 6.0 <= t < 11.0:
            kills.append(MY_KILL)
        if 8.0 <= t < 12.0:
            kills.insert(0, MY_DEATH)
        health = 100 if t < 8.0 else None
        return {"timer": int(180 - (t - 4.0)), "score": (0, 0), "health": health, "kills": kills}
    if t < 14.0:  # round over, lost
        return {"timer": None, "score": (0, 1), "health": None, "kills": []}
    if t < 17.0:  # round 2 prep
        return {"timer": int(45 - (t - 14.0)), "score": (0, 1), "health": 100, "kills": []}
    if t < 22.0:  # round 2 action
        return {"timer": int(180 - (t - 17.0)), "score": (0, 1), "health": 100, "kills": []}
    return {"timer": None, "score": (1, 1), "health": 100, "kills": []}  # won


def main(out_path: str, seconds: float = 25.0) -> None:
    with av.open(out_path, "w") as out:
        stream = out.add_stream("libx264", rate=FPS, options={"preset": "veryfast", "crf": "23"})
        stream.width, stream.height, stream.pix_fmt = SIZE[0], SIZE[1], "yuv420p"
        stream.codec_context.time_base = Fraction(1, FPS)
        for i in range(int(seconds * FPS)):
            frame = av.VideoFrame.from_ndarray(render(state_at(i / FPS), size=SIZE), format="bgr24")
            frame.pts = i
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)


if __name__ == "__main__":
    main(sys.argv[1])
