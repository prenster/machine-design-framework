"""Tolerance stack-ups: worst case, RSS and Monte Carlo.

stacks.yaml:
  stacks:
    - id: STK-REG
      requirement: REQ-PROC-001
      text: "endsheet trailing edge to signature spine edge"
      target: {nominal: 0.0, tol: 0.3}            # result must stay within nominal +/- tol
      contributors:
        - {name: ..., nominal: 0.0, tol: 0.08, dist: normal|uniform, sens: 1, source: "datasheet: ...",
           param: optional param name for tol (keeps one source of truth)}

Verdicts:
  PASS  worst case inside the target
  WARN  worst case outside, but RSS and Monte Carlo inside with Cpk >= 1.33: statistically acceptable,
        needs the chief engineer's acceptance (and parts from a stable process)
  FAIL  RSS or Monte Carlo outside, or Cpk < 1.33
Normal contributors: tol is +/-3 sigma. Uniform: tol is the half-width.
"""
from __future__ import annotations

import math

import numpy as np

from .checks import FAIL, PASS, WARN, CheckResult


def run_stacks(proj, n: int = 200_000, seed: int = 1) -> list[CheckResult]:
    st = proj.data.get("stacks")
    if not st:
        return []
    rng = np.random.default_rng(seed)
    res = []
    for s in st["stacks"]:
        tgt = s["target"]
        nom_t, tol_t = float(tgt.get("nominal", 0.0)), float(tgt["tol"])
        nominal, wc, var = 0.0, 0.0, 0.0
        samples = np.zeros(n)
        rows = []
        for c in s["contributors"]:
            tol = proj.param(c["param"]) if c.get("param") else float(c["tol"])
            sens = float(c.get("sens", 1.0))
            nom = float(c.get("nominal", 0.0))
            nominal += sens * nom
            wc += abs(sens) * tol
            if c.get("dist", "normal") == "uniform":
                sig = tol / math.sqrt(3)
                samples += sens * rng.uniform(nom - tol, nom + tol, n)
            else:
                sig = tol / 3.0
                samples += sens * rng.normal(nom, sig, n)
            var += (sens * sig) ** 2
            rows.append((c["name"], tol, (sens * sig) ** 2))
        rss3 = 3 * math.sqrt(var)
        lo, hi = nom_t - tol_t, nom_t + tol_t
        mean, std = float(samples.mean()), float(samples.std())
        cpk = min(hi - mean, mean - lo) / (3 * std) if std > 0 else float("inf")
        out_frac = float(np.mean((samples < lo) | (samples > hi)))
        wc_ok = (nominal - wc) >= lo and (nominal + wc) <= hi
        rss_ok = (nominal - rss3) >= lo and (nominal + rss3) <= hi
        mc_ok = cpk >= 1.33
        details = [f"nominal {nominal:+.3f}, target {nom_t:+.3f} +/- {tol_t}",
                   f"worst case +/- {wc:.3f} ({'inside' if wc_ok else 'OUTSIDE'})",
                   f"RSS (3 sigma) +/- {rss3:.3f} ({'inside' if rss_ok else 'OUTSIDE'})",
                   f"Monte Carlo n={n:,}: Cpk {cpk:.2f}, {out_frac * 1e6:,.0f} ppm out of tolerance"]
        tot = sum(r[2] for r in rows) or 1.0
        for name, tol, v in sorted(rows, key=lambda r: -r[2]):
            details.append(f"  {name}: +/-{tol:g} -> {v / tot:.0%} of variance")
        if wc_ok:
            status = PASS
        elif rss_ok and mc_ok:
            status = WARN
            details.insert(0, "worst case exceeds the target; statistically acceptable only if the chief engineer "
                              "accepts it and contributors come from stable processes. Biggest lever is listed first.")
        else:
            status = FAIL
            details.insert(0, "stack does not close even statistically: reduce the largest contributors")
        res.append(CheckResult(s["id"], status, f"{s['text']}: WC +/-{wc:.3f}, RSS +/-{rss3:.3f} vs +/-{tol_t}",
                               details))
    return res
