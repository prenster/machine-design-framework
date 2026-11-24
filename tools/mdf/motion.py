"""Motion laws over machine angle.

Every axis in the machine is a function of the master angle (0-360 deg per
cycle). This is how a mechanical cam, an electronic cam (e.g. SEW MOVIKIT
Camming) and a CODESYS SoftMotion cam table all think about motion, so the
same data drives the PLC cam tables and the simulation.

Units: position in mm (or deg for rotary axes), velocity in units/deg,
acceleration in units/deg^2. Convert to time domain with omega (deg/s):
    v_t = v * omega,   a_t = a * omega**2
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Segment:
    law: str          # dwell | cycloidal | poly5 | linear
    start: float      # deg
    end: float        # deg
    s0: float
    s1: float
    v0: float = 0.0   # units/deg (poly5 only)
    v1: float = 0.0
    coeffs: np.ndarray | None = None

    @property
    def span(self) -> float:
        return self.end - self.start

    def prepare(self) -> None:
        if self.law == "poly5":
            # s(u) = sum c_k u^k, u in [0,1]; boundary pos, vel, acc(=0)
            D = self.span
            A = np.array([
                [1, 0, 0, 0, 0, 0],
                [1, 1, 1, 1, 1, 1],
                [0, 1, 0, 0, 0, 0],
                [0, 1, 2, 3, 4, 5],
                [0, 0, 2, 0, 0, 0],
                [0, 0, 2, 6, 12, 20],
            ], dtype=float)
            b = np.array([self.s0, self.s1, self.v0 * D, self.v1 * D, 0.0, 0.0])
            self.coeffs = np.linalg.solve(A, b)

    def eval(self, theta: float) -> tuple[float, float, float]:
        """Return (pos, vel per deg, acc per deg^2) at theta inside segment."""
        D = self.span
        u = (theta - self.start) / D
        h = self.s1 - self.s0
        if self.law == "dwell":
            return self.s0, 0.0, 0.0
        if self.law == "linear":
            return self.s0 + h * u, h / D, 0.0
        if self.law == "cycloidal":
            s = self.s0 + h * (u - math.sin(2 * math.pi * u) / (2 * math.pi))
            v = h * (1 - math.cos(2 * math.pi * u)) / D
            a = h * 2 * math.pi * math.sin(2 * math.pi * u) / D**2
            return s, v, a
        if self.law == "poly5":
            c = self.coeffs
            s = sum(c[k] * u**k for k in range(6))
            ds = sum(k * c[k] * u ** (k - 1) for k in range(1, 6))
            dds = sum(k * (k - 1) * c[k] * u ** (k - 2) for k in range(2, 6))
            return s, ds / D, dds / D**2
        raise ValueError(f"unknown motion law {self.law!r}")


class Axis:
    def __init__(self, axis_id: str, spec: dict):
        self.id = axis_id
        self.spec = spec
        self.segments: list[Segment] = []
        for seg in spec["segments"]:
            s = Segment(
                law=seg["law"],
                start=float(seg["from"]),
                end=float(seg["to"]),
                s0=float(seg.get("s0", seg.get("at", 0.0))),
                s1=float(seg.get("s1", seg.get("at", 0.0))),
                v0=float(seg.get("v0", 0.0)),
                v1=float(seg.get("v1", 0.0)),
            )
            if s.law == "dwell":
                s.s1 = s.s0
            s.prepare()
            self.segments.append(s)

    def eval(self, theta: float) -> tuple[float, float, float]:
        t = theta % 360.0
        for seg in self.segments:
            if seg.start <= t < seg.end or (t == 360.0 and seg.end == 360.0):
                return seg.eval(t)
        # theta exactly 360 after modulo is 0, handled above
        raise ValueError(f"axis {self.id}: angle {t} not covered by any segment")

    def pos(self, theta: float) -> float:
        return self.eval(theta)[0]


def omega_deg_s(cycles_per_hour: float) -> float:
    return cycles_per_hour / 3600.0 * 360.0


def ms_to_deg(ms: float, cycles_per_hour: float) -> float:
    return ms / 1000.0 * omega_deg_s(cycles_per_hour)
