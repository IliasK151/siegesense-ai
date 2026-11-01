"""Flick, correction and overshoot detection (spec §4.5).

Movement is binned by *time* (5 ms bins), so the result does not depend on the mouse's
polling rate or on Raw Input delivering events in bursts.

A flick: smoothed angular speed peaks at ≥ 300 °/s and the ballistic movement covers ≥ 5°.
A correction: within 250 ms after the peak, the aim moves back along the flick direction by
≥ 10 % of the amplitude. An overshoot: a correction followed by a shot within 400 ms.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlickConfig:
    min_peak_speed: float = 300.0  # °/s
    min_amplitude: float = 5.0  # °
    correction_window: float = 0.25  # s after the peak
    correction_ratio: float = 0.10
    shot_window: float = 0.40  # s after the correction (or ballistic end)
    bin_s: float = 0.005
    end_ratio: float = 0.20
    max_lookback: float = 0.30  # s before the peak to search for the onset
    late_tolerance: float = 0.05  # s; events may arrive this late/out of order


@dataclass
class Flick:
    t_peak: float
    amplitude: float
    peak_speed: float
    duration_ms: float
    direction: float  # degrees, 0 = right, 90 = up
    reversal: float = 0.0
    corrected: bool = False
    overshoot: bool = False
    shot: bool = False
    trace: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class _Candidate:
    peak_speed: float
    peak_idx: int
    start_idx: int  # first bin whose speed crossed the flick threshold


@dataclass
class _Correcting:
    flick: Flick
    ux: float
    uy: float
    onset_idx: int
    ballistic_end_idx: int
    window_end_idx: int
    cum: float = 0.0
    max_cum: float = 0.0  # furthest point reached along the flick direction
    reversal: float = 0.0  # deepest pull-back from that furthest point
    min_idx: int = 0
    trace_tail: list[tuple[int, float]] = field(default_factory=list)


@dataclass
class _Pending:
    flick: Flick
    ref_time: float  # shot window starts here
    corr_time: float | None
    ready_at: float


class FlickDetector:
    def __init__(self, config: FlickConfig | None = None) -> None:
        self.cfg = config or FlickConfig()
        self._bins: dict[int, list[float]] = {}
        self._next_idx: int | None = None
        self._history: deque[tuple[int, float, float, float]] = deque()  # idx, dx, dy, speed
        self._prev: tuple[float, float] = (0.0, 0.0)
        self._candidate: _Candidate | None = None
        self._correcting: _Correcting | None = None
        self._pending: list[_Pending] = []
        self._shots: deque[float] = deque()

    # -- input ---------------------------------------------------------------------------
    def move(self, t: float, dx: float, dy: float) -> None:
        idx = math.floor(t / self.cfg.bin_s)
        if self._next_idx is not None and idx < self._next_idx:
            idx = self._next_idx  # too late for its own bin; fold into the next open one
        b = self._bins.setdefault(idx, [0.0, 0.0])
        b[0] += dx
        b[1] += dy

    def shot(self, t: float) -> None:
        self._shots.append(t)

    # -- output --------------------------------------------------------------------------
    def poll(self, now: float) -> list[Flick]:
        self._process_until(math.floor((now - self.cfg.late_tolerance) / self.cfg.bin_s))
        done: list[Flick] = []
        still: list[_Pending] = []
        for p in self._pending:
            if now >= p.ready_at:
                self._resolve_shots(p)
                done.append(p.flick)
            else:
                still.append(p)
        self._pending = still
        horizon = now - 5.0
        while self._shots and self._shots[0] < horizon:
            self._shots.popleft()
        return done

    # -- processing ----------------------------------------------------------------------
    def _process_until(self, last_idx: int) -> None:
        if not self._bins and self._candidate is None and self._correcting is None:
            return
        if self._next_idx is None:
            self._next_idx = min(self._bins) if self._bins else last_idx + 1
        idx = self._next_idx
        while idx <= last_idx:
            if self._candidate is None and self._correcting is None and idx not in self._bins:
                # Idle with nothing here: jump to the next bin that has movement.
                later = [k for k in self._bins if k > idx]
                if not later:
                    self._prev = (0.0, 0.0)
                    idx = last_idx + 1
                    break
                nxt = min(later)
                if nxt > last_idx:
                    self._prev = (0.0, 0.0)
                    idx = last_idx + 1
                    break
                if nxt > idx + 1:
                    self._prev = (0.0, 0.0)
                idx = nxt
            dx, dy = self._bins.pop(idx, (0.0, 0.0))
            self._step(idx, dx, dy)
            idx += 1
        self._next_idx = idx

    def _step(self, idx: int, dx: float, dy: float) -> None:
        cfg = self.cfg
        px, py = self._prev
        speed = math.hypot(dx + px, dy + py) / (2 * cfg.bin_s)
        self._prev = (dx, dy)
        self._history.append((idx, dx, dy, speed))
        max_hist = int(cfg.max_lookback / cfg.bin_s) + 2
        while len(self._history) > max_hist:
            self._history.popleft()

        if self._correcting is not None:
            self._step_correction(idx, dx, dy)
            return

        cand = self._candidate
        if cand is None:
            if speed >= cfg.min_peak_speed:
                self._candidate = _Candidate(speed, idx, idx)
            return

        if speed > cand.peak_speed:
            cand.peak_speed, cand.peak_idx = speed, idx
        if speed < cfg.end_ratio * cand.peak_speed:
            self._finish_ballistic(idx)

    def _finish_ballistic(self, end_idx: int) -> None:
        cfg = self.cfg
        cand = self._candidate
        assert cand is not None
        self._candidate = None
        threshold = cfg.end_ratio * cand.peak_speed
        lookback = int(cfg.max_lookback / cfg.bin_s)
        # Only recent bins count: after an idle gap, old bins are not part of this flick.
        hist = [h for h in self._history if cand.peak_idx - lookback <= h[0] <= end_idx]
        onset_idx = cand.start_idx
        for h_idx, _, _, h_speed in reversed(hist):
            if h_idx < cand.peak_idx and h_speed < threshold:
                onset_idx = h_idx
                break
        if onset_idx > cand.start_idx:
            onset_idx = cand.start_idx
        ballistic = [(i, x, y) for i, x, y, _ in hist if onset_idx <= i < end_idx]
        sx = sum(x for _, x, _ in ballistic)
        sy = sum(y for _, _, y in ballistic)
        amplitude = math.hypot(sx, sy)
        if amplitude < cfg.min_amplitude:
            return
        ux, uy = sx / amplitude, sy / amplitude
        t_peak = (cand.peak_idx + 0.5) * cfg.bin_s
        flick = Flick(
            t_peak=t_peak,
            amplitude=amplitude,
            peak_speed=cand.peak_speed,
            duration_ms=(end_idx - onset_idx) * cfg.bin_s * 1000,
            direction=math.degrees(math.atan2(-sy, sx)),
        )
        # Trace of the ballistic part: cumulative projection on the flick direction.
        cum = 0.0
        trace: list[tuple[int, float]] = []
        for i, x, y in ballistic:
            cum += x * ux + y * uy
            trace.append((i, cum))
        corr = _Correcting(
            flick=flick,
            ux=ux,
            uy=uy,
            onset_idx=onset_idx,
            ballistic_end_idx=end_idx,
            window_end_idx=math.floor((t_peak + cfg.correction_window) / cfg.bin_s),
            min_idx=end_idx,
            trace_tail=trace,
        )
        self._correcting = corr
        # The bin that ended the ballistic phase belongs to the correction window.
        last = self._history[-1]
        self._history.pop()
        self._step_correction(last[0], last[1], last[2])
        self._history.append(last)

    def _step_correction(self, idx: int, dx: float, dy: float) -> None:
        c = self._correcting
        assert c is not None
        if idx > c.window_end_idx:
            self._finish_correction()
            return
        c.cum += dx * c.ux + dy * c.uy
        c.max_cum = max(c.max_cum, c.cum)
        if c.max_cum - c.cum > c.reversal:
            c.reversal, c.min_idx = c.max_cum - c.cum, idx
        base = c.trace_tail[-1][1] if c.trace_tail else 0.0
        c.trace_tail.append((idx, base + dx * c.ux + dy * c.uy))
        if idx == c.window_end_idx:
            self._finish_correction()

    def _finish_correction(self) -> None:
        cfg = self.cfg
        c = self._correcting
        assert c is not None
        self._correcting = None
        f = c.flick
        f.reversal = c.reversal
        f.corrected = f.reversal >= cfg.correction_ratio * f.amplitude
        f.trace = [((i - c.onset_idx) * cfg.bin_s * 1000, round(p, 3)) for i, p in c.trace_tail]
        ballistic_end_t = c.ballistic_end_idx * cfg.bin_s
        corr_time = (c.min_idx + 1) * cfg.bin_s if f.corrected else None
        ref = max(ballistic_end_t, corr_time or 0.0)
        self._pending.append(
            _Pending(
                flick=f,
                ref_time=ballistic_end_t,
                corr_time=corr_time,
                ready_at=max(f.t_peak + cfg.correction_window, ref + cfg.shot_window),
            )
        )

    def _resolve_shots(self, p: _Pending) -> None:
        w = self.cfg.shot_window
        p.flick.shot = any(p.ref_time <= s <= p.ref_time + w for s in self._shots)
        if p.corr_time is not None:
            p.flick.overshoot = any(p.corr_time <= s <= p.corr_time + w for s in self._shots)
