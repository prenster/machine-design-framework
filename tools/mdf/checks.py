"""Verification checks for a station project.

Each check returns CheckResult objects. Checks are deterministic: the same
project data always gives the same verdict. They are the judge of a design;
an agent's reasoning about the design is not.

Check IDs (referenced from requirements.yaml -> verification.ref):
  CYC-LAW         motion laws cover the cycle, continuous position/velocity
  CYC-LIMITS      peak velocity/acceleration within drive limits at max speed
  VALVE-TIMING    effective valve windows (with response delay) at every speed
  SWEEP-CLEARANCE planar collision/clearance sweep over the full cycle
  PROD-PICK       vacuum established at the pick port before the carrier leaves
  PROD-CARRY      product held for the whole transfer; inertial load vs. grip
  PROD-PLACE      release happens at the place port within registration tolerance
  GLUE-BEAD       glue lands on the product, in spec, at the right gap, at all speeds
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon

from .motion import ms_to_deg, omega_deg_s
from .project import Project

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


@dataclass
class CheckResult:
    check_id: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)
    speed: str | None = None
    data: dict = field(default_factory=dict)


def in_window(theta: float, window) -> bool:
    a, b = window[0] % 360.0, window[1] % 360.0
    t = theta % 360.0
    if window[1] - window[0] >= 360.0:
        return True
    if a <= b:
        return a <= t <= b
    return t >= a or t <= b


def frange(step: float):
    n = int(round(360.0 / step))
    return [i * step for i in range(n)]


class World:
    """Planar (side-view) kinematic world at a given machine speed."""

    def __init__(self, proj: Project, cph: float):
        self.p = proj
        self.cph = cph
        lay = proj.layout
        car = lay["carrier"]
        self.ax_x = proj.axes[car["x_axis"]]
        self.ax_z = proj.axes[car["z_axis"]]
        self.carrier_bodies = [(b["id"], Polygon(b["polygon"])) for b in car["bodies"]]
        self.static = [(b["id"], Polygon(b["polygon"])) for b in lay["static"]]
        prod = lay["product"]
        self.product_id = prod["id"]
        self.product_poly = Polygon(prod["polygon"])
        self.grip_valve = prod["grip_valve"]
        self.placed_until = float(prod["placed_until"])
        self.grip = self.valve_window(self.grip_valve)
        self.thickness = self.product_poly.bounds[3] - self.product_poly.bounds[1]
        self._sheet = None
        self._sheet_done = False

    def supported(self, theta: float) -> bool:
        x, z = self.carrier(theta)
        for port in ("pick", "place"):
            p = self.p.layout["ports"][port]
            if abs(x - p["x"]) <= p["tol_x"] and abs(z - p["z"]) <= p["tol_z"]:
                return True
        return False

    @property
    def sheet(self):
        if not self._sheet_done:
            from .sheetdyn import simulate
            self._sheet = simulate(self.p, self, self.supported)
            self._sheet_done = True
        return self._sheet

    def product_shape(self, theta: float):
        """Product polygon in carrier frame, deformed by sheet dynamics when available."""
        sh = self.sheet
        w = sh.deflection(theta) if sh is not None else None
        if w is None:
            return self.product_poly
        xs = sh.x_nodes
        z0 = self.product_poly.bounds[1]
        bottom = [(float(x), z0 + float(wi)) for x, wi in zip(xs, w)]
        top = [(float(x), z0 + float(wi) + self.thickness) for x, wi in zip(xs[::-1], w[::-1])]
        return Polygon(bottom + top)

    def valve_window(self, valve_id: str) -> tuple[float, float]:
        v = self.p.cycle["valves"][valve_id]
        on = v["on"] + ms_to_deg(self.p.num(v["on_delay"]), self.cph)
        off = v["off"] + ms_to_deg(self.p.num(v["off_delay"]), self.cph)
        return on % 360.0, off % 360.0

    def carrier(self, theta: float) -> tuple[float, float]:
        return self.ax_x.pos(theta), self.ax_z.pos(theta)

    def gripped(self, theta: float) -> bool:
        return in_window(theta, self.grip)

    def placed(self, theta: float) -> bool:
        return in_window(theta, (self.grip[1], self.placed_until)) and not self.gripped(theta)

    def moving_bodies(self, theta: float):
        x, z = self.carrier(theta)
        out = [(bid, affinity.translate(poly, x, z)) for bid, poly in self.carrier_bodies]
        if self.gripped(theta):
            out.append((self.product_id, affinity.translate(self.product_shape(theta), x, z)))
        return out

    def static_bodies(self, theta: float):
        out = list(self.static)
        if self.placed(theta):
            rx, rz = self.carrier(self.grip[1])
            out.append((f"{self.product_id}_placed", affinity.translate(self.product_poly, rx, rz)))
        return out


# ---------------------------------------------------------------- cycle laws
def check_cycle_law(proj: Project) -> list[CheckResult]:
    results = []
    for axis in proj.axes.values():
        issues, warns = [], []
        segs = axis.segments
        if abs(segs[0].start) > 1e-9:
            issues.append(f"first segment starts at {segs[0].start} deg, not 0")
        if abs(segs[-1].end - 360.0) > 1e-9:
            issues.append(f"last segment ends at {segs[-1].end} deg, not 360")
        pairs = list(zip(segs, segs[1:])) + [(segs[-1], segs[0])]
        for a, b in pairs:
            wrap = b is segs[0]
            if not wrap and abs(a.end - b.start) > 1e-9:
                issues.append(f"gap/overlap between {a.end} and {b.start} deg")
                continue
            sa, va, aa = a.eval(a.end)
            sb, vb, ab = b.eval(b.start)
            at = f"{a.end:g} deg" + (" (cycle wrap)" if wrap else "")
            if abs(sa - sb) > 1e-6:
                issues.append(f"position jump at {at}: {sa:.4f} -> {sb:.4f}")
            if abs(va - vb) > 1e-6:
                issues.append(f"velocity jump at {at}: {va:.4f} -> {vb:.4f} per deg "
                              f"(infinite acceleration: impossible for a servo, destroys a cam follower)")
            if abs(aa - ab) > 1e-6:
                warns.append(f"acceleration step at {at}: {aa:.5f} -> {ab:.5f} per deg^2 (jerk spike)")
        status = FAIL if issues else (WARN if warns else PASS)
        results.append(CheckResult("CYC-LAW", status,
                                   f"axis {axis.id}: {len(issues)} discontinuities, {len(warns)} jerk warnings",
                                   issues + warns))
    return results


def check_cycle_limits(proj: Project) -> list[CheckResult]:
    results = []
    cph = proj.speeds[-1][1]
    w = omega_deg_s(cph)
    for axis in proj.axes.values():
        vmax_lim = proj.num(axis.spec["vmax"])
        amax_lim = proj.num(axis.spec["amax"])
        vs, accs = [], []
        for t in np.arange(0, 360, 0.1):
            _, v, a = axis.eval(t)
            vs.append(abs(v) * w)
            accs.append(abs(a) * w * w)
        vpk, apk = max(vs), max(accs)
        ok = vpk <= vmax_lim and apk <= amax_lim
        unit = axis.spec.get("unit", "mm")
        results.append(CheckResult(
            "CYC-LIMITS", PASS if ok else FAIL,
            f"axis {axis.id} @ {cph:g} cph: v_pk {vpk:,.0f}/{vmax_lim:,.0f} {unit}/s, "
            f"a_pk {apk:,.0f}/{amax_lim:,.0f} {unit}/s^2",
            [], speed="max"))
    return results


# ------------------------------------------------------------- valve timing
def check_valve_timing(proj: Project) -> list[CheckResult]:
    results = []
    for name, cph in proj.speeds:
        world = World(proj, cph)
        lines, bad = [], []
        for vid, v in proj.cycle["valves"].items():
            on, off = world.valve_window(vid)
            width = (off - on) % 360.0
            lines.append(f"{vid}: commanded {v['on']:g}-{v['off']:g} deg -> effective {on:.2f}-{off:.2f} deg")
            if width <= 0.0:
                bad.append(f"{vid}: effective window collapsed (delays exceed command width)")
        results.append(CheckResult("VALVE-TIMING", FAIL if bad else PASS,
                                   f"{len(proj.cycle['valves'])} valves @ {cph:g} cph", bad + lines, speed=name))
    return results


# ------------------------------------------------------------ clearance sweep
def clearance_required(proj: Project, a: str, b: str, theta: float) -> float:
    cl = proj.layout["clearance"]
    for rule in cl.get("rules", []):
        pair = set(rule["between"])
        if pair == {a, b} and in_window(theta, rule["window"]):
            return float(rule["min_mm"])
    return float(cl["default_min_mm"])


def check_sweep(proj: Project) -> list[CheckResult]:
    results = []
    step = float(proj.layout["clearance"].get("step_deg", 0.25))
    for name, cph in proj.speeds:
        world = World(proj, cph)
        worst: dict[tuple[str, str], tuple[float, float, float]] = {}  # pair -> (margin, dist, theta)
        violations: dict[tuple[str, str], list[float]] = {}
        for t in frange(step):
            for mid, mpoly in world.moving_bodies(t):
                for sid, spoly in world.static_bodies(t):
                    d = mpoly.distance(spoly)
                    if mpoly.intersects(spoly) and mpoly.intersection(spoly).area > 1e-9:
                        d = -mpoly.intersection(spoly).area ** 0.5  # rough penetration depth
                    req = clearance_required(proj, mid, sid, t)
                    margin = d - req
                    key = (mid, sid)
                    if key not in worst or margin < worst[key][0]:
                        worst[key] = (margin, d, t)
                    if margin < -1e-6:
                        violations.setdefault(key, []).append(t)
        details = []
        for (m, s), angles in sorted(violations.items()):
            _, d, t = worst[(m, s)]
            details.append(f"{m} vs {s}: below required clearance from {angles[0]:.2f} to {angles[-1]:.2f} deg; "
                           f"worst {d:.2f} mm at {t:.2f} deg"
                           + (" (INTERFERENCE)" if d < 0 else ""))
        tight = sorted(((v[0], k, v) for k, v in worst.items() if (k not in violations)), key=lambda x: x[0])[:4]
        for margin, (m, s), (_, d, t) in tight:
            details.append(f"tightest OK: {m} vs {s}: {d:.2f} mm at {t:.2f} deg (margin {margin:.2f} mm)")
        results.append(CheckResult("SWEEP-CLEARANCE", FAIL if violations else PASS,
                                   f"{len(frange(step))} steps @ {cph:g} cph, {len(violations)} pairs in violation",
                                   details, speed=name))
    return results


# --------------------------------------------------------------- product path
def _at_port(proj: Project, x: float, z: float, port: str) -> tuple[bool, float, float]:
    p = proj.layout["ports"][port]
    dx, dz = x - p["x"], z - p["z"]
    return abs(dx) <= p["tol_x"] and abs(dz) <= p["tol_z"], dx, dz


def _vel(world: World, t: float) -> float:
    _, vx, _ = world.ax_x.eval(t)
    _, vz, _ = world.ax_z.eval(t)
    return math.hypot(vx, vz) * omega_deg_s(world.cph)


def check_product(proj: Project) -> list[CheckResult]:
    results = []
    vel_eps = float(proj.layout["ports"].get("max_speed_at_port_mm_s", 5.0))
    slip = proj.param("sheet_slip_accel_mm_s2")
    for name, cph in proj.speeds:
        world = World(proj, cph)
        on, off = world.grip

        # PICK: vacuum effective while still parked at pick port, and stays parked until then
        ok_on, dx, dz = _at_port(proj, *world.carrier(on), "pick")
        issues = []
        if not ok_on:
            issues.append(f"vacuum becomes effective at {on:.2f} deg but carrier is {dx:+.2f} mm x / {dz:+.2f} mm z "
                          f"from the pick port: picks air, or the wrong sheet")
        if _vel(world, on) > vel_eps:
            issues.append(f"carrier moving {_vel(world, on):.0f} mm/s when vacuum becomes effective")
        cmd_on = proj.cycle["valves"][world.grip_valve]["on"]
        t = cmd_on
        while in_window(t, (cmd_on, on)) and t < cmd_on + 360:
            if not _at_port(proj, *world.carrier(t), "pick")[0]:
                issues.append(f"carrier leaves pick port at {t % 360:.2f} deg, before vacuum is established ({on:.2f} deg)")
                break
            t += 0.05
        results.append(CheckResult("PROD-PICK", FAIL if issues else PASS,
                                   f"grip effective {on:.2f} deg @ {cph:g} cph", issues, speed=name))

        # PLACE: release at place port, carrier at rest
        ok_off, dx, dz = _at_port(proj, *world.carrier(off), "place")
        issues = []
        if not ok_off:
            issues.append(f"vacuum releases at {off:.2f} deg with carrier {dx:+.2f} mm x / {dz:+.2f} mm z from the place port: "
                          f"product lands off-register or is dropped from height")
        if _vel(world, off) > vel_eps:
            issues.append(f"carrier moving {_vel(world, off):.0f} mm/s at release: product is thrown, not placed")
        results.append(CheckResult("PROD-PLACE", FAIL if issues else PASS,
                                   f"release effective {off:.2f} deg, registration error {dx:+.3f} mm @ {cph:g} cph",
                                   issues, speed=name))

        # CARRY: inertial load on a gripped sheet
        peak, at = 0.0, None
        t = on
        span = (off - on) % 360.0
        for k in range(int(span / 0.1) + 1):
            tt = (on + k * 0.1) % 360.0
            _, _, ax = world.ax_x.eval(tt)
            _, _, az = world.ax_z.eval(tt)
            a = math.hypot(ax, az) * omega_deg_s(cph) ** 2
            if a > peak:
                peak, at = a, tt
        issues = []
        if peak > slip:
            issues.append(f"peak carrier acceleration {peak:,.0f} mm/s^2 at {at:.2f} deg exceeds sheet slip limit "
                          f"{slip:,.0f} mm/s^2: sheet shifts on the vacuum plate")
        results.append(CheckResult("PROD-CARRY", FAIL if issues else PASS,
                                   f"peak accel while gripped {peak:,.0f} / {slip:,.0f} mm/s^2 @ {cph:g} cph",
                                   issues, speed=name))
    return results


# --------------------------------------------------------------------- glue
def check_glue(proj: Project) -> list[CheckResult]:
    g = proj.layout.get("glue")
    if not g:
        return []
    results = []
    plen = Polygon(proj.layout["product"]["polygon"]).bounds  # minx, minz, maxx, maxz
    bead = g["bead"]
    for name, cph in proj.speeds:
        world = World(proj, cph)
        on, off = world.valve_window(g["valve"])
        span = (off - on) % 360.0
        xs, gaps, off_product = [], [], 0
        n = max(int(span / 0.01), 2)
        for k in range(n + 1):
            t = (on + span * k / n) % 360.0
            cx, cz = world.carrier(t)
            sx = g["nozzle_x"] - cx  # position on the sheet under the nozzle
            if not world.gripped(t) or not (plen[0] <= sx <= plen[2]):
                off_product += 1
                continue
            xs.append(sx)
            droop = world.sheet.at(t, sx) if world.sheet is not None else 0.0
            gaps.append(cz + plen[1] + droop - g["nozzle_z"])
        issues = []
        if off_product:
            issues.append(f"{off_product / (n + 1):.0%} of the glue shot lands off the product (on the machine)")
        if xs:
            lo, hi = min(xs), max(xs)
            if abs(lo - bead["start_mm"]) > bead["tol_mm"] or abs(hi - bead["end_mm"]) > bead["tol_mm"]:
                issues.append(f"bead {lo:.2f}-{hi:.2f} mm from edge; spec {bead['start_mm']}-{bead['end_mm']} "
                              f"+/-{bead['tol_mm']} mm")
            gmin, gmax = min(gaps), max(gaps)
            if gmin < g["gap"]["min_mm"] or gmax > g["gap"]["max_mm"]:
                issues.append(f"nozzle gap {gmin:.2f}-{gmax:.2f} mm; spec {g['gap']['min_mm']}-{g['gap']['max_mm']} mm")
            summary = f"bead {lo:.2f}-{hi:.2f} mm, gap {gmin:.2f}-{gmax:.2f} mm @ {cph:g} cph"
        else:
            summary = f"no glue on product @ {cph:g} cph"
            issues.append("glue never lands on the product")
        results.append(CheckResult("GLUE-BEAD", FAIL if issues else PASS, summary, issues, speed=name))
    return results


def check_sheet(proj: Project) -> list[CheckResult]:
    if "sheet_bending_stiffness_mNm" not in proj.data["params"]["params"]:
        return []
    results = []
    limit = proj.param("sheet_max_deflection_mm")
    for name, cph in proj.speeds:
        world = World(proj, cph)
        sh = world.sheet
        wmin, tmin, wmax, tmax = sh.envelope()
        issues = []
        if max(-wmin, wmax) > limit:
            issues.append(f"overhang deflection {wmin:+.2f}/{wmax:+.2f} mm exceeds {limit} mm")
        notes = [f"first bending mode of the overhang: {sh.first_mode_hz:.1f} Hz; clamped under plate "
                 f"{sh.clamp[0]:.0f}-{sh.clamp[1]:.0f} mm",
                 f"max droop {wmin:+.2f} mm at {tmin:.1f} deg, max lift {wmax:+.2f} mm at {tmax:.1f} deg",
                 "deformed sheet is used by SWEEP-CLEARANCE and GLUE-BEAD",
                 "NOT modelled: edgewise aeroelastic flutter, in-plane buckling, curl, air cushion -> PT video test"]
        results.append(CheckResult("SHEET-DYN", FAIL if issues else PASS,
                                   f"droop {wmin:+.2f} mm / lift {wmax:+.2f} mm, f1 {sh.first_mode_hz:.0f} Hz @ {cph:g} cph",
                                   issues + notes, speed=name))
    return results


ALL_CHECKS = [check_sheet, check_cycle_law, check_cycle_limits, check_valve_timing, check_sweep, check_product, check_glue]


def run_all(proj: Project) -> list[CheckResult]:
    from .bom import run_bom
    from .sil import run_sil
    from .sweep3d import run_3d
    out = []
    for fn in ALL_CHECKS:
        out.extend(fn(proj))
    out.extend(run_3d(proj))
    out.extend(run_bom(proj))
    out.extend(run_sil(proj))
    return out
