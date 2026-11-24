"""Runtime for transpiled Structured Text: standard FBs, builtins, scan clock."""
from __future__ import annotations

import math


class _Clock:
    now_ms = 0.0


CLOCK = _Clock()


class _Return(Exception):
    pass


class _Ret(Exception):
    pass


def _int(x):
    return int(math.trunc(x)) if not isinstance(x, bool) else int(x)


def _div(a, b):
    if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool):
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b >= 0) else -q
    return a / b


def _mod(a, b):
    return int(math.fmod(a, b))


class TON:
    def __init__(self):
        self.in_ = False
        self.pt = 0.0
        self.q = False
        self.et = 0.0
        self._start = None

    def __call__(self, **kw):
        if "in" in kw:
            self.in_ = bool(kw["in"])
        if "pt" in kw:
            self.pt = float(kw["pt"])
        if self.in_:
            if self._start is None:
                self._start = CLOCK.now_ms
            self.et = min(CLOCK.now_ms - self._start, self.pt)
            self.q = self.et >= self.pt
        else:
            self._start, self.et, self.q = None, 0.0, False


class TOF:
    def __init__(self):
        self.in_ = False
        self.pt = 0.0
        self.q = False
        self.et = 0.0
        self._off = None

    def __call__(self, **kw):
        if "in" in kw:
            self.in_ = bool(kw["in"])
        if "pt" in kw:
            self.pt = float(kw["pt"])
        if self.in_:
            self._off, self.et, self.q = None, 0.0, True
        else:
            if self._off is None:
                self._off = CLOCK.now_ms
            self.et = min(CLOCK.now_ms - self._off, self.pt)
            self.q = self.et < self.pt and self.q


class R_TRIG:
    def __init__(self):
        self.clk = False
        self.q = False
        self._m = False

    def __call__(self, **kw):
        self.clk = bool(kw.get("clk", self.clk))
        self.q = self.clk and not self._m
        self._m = self.clk


class F_TRIG:
    def __init__(self):
        self.clk = False
        self.q = False
        self._m = True

    def __call__(self, **kw):
        self.clk = bool(kw.get("clk", self.clk))
        self.q = (not self.clk) and not self._m
        self._m = not self.clk


def B_ABS(x): return abs(x)
def B_MIN(*a): return min(a)
def B_MAX(*a): return max(a)
def B_LIMIT(mn, x, mx): return max(mn, min(x, mx))
def B_SEL(g, a, b): return b if g else a
def B_TRUNC(x): return _int(x)
def B_REAL_TO_INT(x): return int(round(x))
def B_REAL_TO_DINT(x): return int(round(x))
def B_INT_TO_REAL(x): return float(x)
def B_DINT_TO_REAL(x): return float(x)
def B_BOOL_TO_INT(x): return int(bool(x))


__all__ = ["CLOCK", "_Return", "_Ret", "_int", "_div", "_mod", "TON", "TOF", "R_TRIG", "F_TRIG",
           "B_ABS", "B_MIN", "B_MAX", "B_LIMIT", "B_SEL", "B_TRUNC", "B_REAL_TO_INT", "B_REAL_TO_DINT",
           "B_INT_TO_REAL", "B_DINT_TO_REAL", "B_BOOL_TO_INT"]
