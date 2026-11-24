"""Mechanical cam design: plate (radial) cam with translating roller follower.

Driven by the same cycle.yaml motion law as every other axis (machine angle = camshaft angle), so a
mechanical cam and an electronic cam are interchangeable designs of the same motion.

Checks (CAM-<axis>), at max speed:
  pressure angle      |phi| <= limit (30 deg translating follower; Norton, Design of Machinery)
                      force-closed cams: rise only (the spring drives the return); form-closed: both
  curvature           convex pitch-curve radius >= ratio x roller radius (2 target, 1.5 floor; < 1 undercuts)
  Hertz stress        line contact roller/cam vs. allowable for the cam material
  follower jump       force-closed: spring + external load must keep contact force >= margin at all angles
  roller bearing      roller speed <= rating; L10 life (roller bearing exponent 10/3) >= required hours
  camshaft torque     peak / RMS from power balance T*w = F*v (reported for drive sizing)
Exports build/cams/<axis>.csv, .dxf (R12 polyline) and .step (extruded profile) for the machinist.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .checks import FAIL, PASS, WARN, CheckResult
from .motion import omega_deg_s


def _spec(parts, pid, key, default=None):
    p = parts.get(pid) or {}
    v = p.get("specs", {}).get(key, default)
    return v["value"] if isinstance(v, dict) else v


def analyse(proj, axis_id: str, n: int = 3600) -> dict:
    ax = proj.axes[axis_id]
    spec = proj.cycle["axes"][axis_id]
    cam = spec["cam"]
    parts = {p["id"]: p for p in proj.data.get("bom", {}).get("parts", [])}
    rf = float(cam.get("roller_radius_mm") or _spec(parts, cam["roller_part"], "outer_diameter_mm") / 2.0)
    rb = float(cam["base_radius_mm"])
    e = float(cam.get("offset_mm", 0.0))
    rp = rb + rf
    d = math.sqrt(rp * rp - e * e)
    th = np.linspace(0.0, 360.0, n, endpoint=False)
    ev = np.array([ax.eval(t) for t in th])
    s = ev[:, 0]
    sp = ev[:, 1] * 180.0 / math.pi                       # mm/rad
    spp = ev[:, 2] * (180.0 / math.pi) ** 2              # mm/rad^2
    phi = np.degrees(np.arctan2(sp - e, d + s))
    # pitch curve in cam frame (cam rotates +theta, follower fixed)
    t = np.radians(th)
    xf, yf = e, d + s
    px = xf * np.cos(t) + yf * np.sin(t)
    py = -xf * np.sin(t) + yf * np.cos(t)
    dx, dy = np.gradient(px, t), np.gradient(py, t)
    ddx, ddy = np.gradient(dx, t), np.gradient(dy, t)
    kappa = (dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)
    rho = 1.0 / np.where(np.abs(kappa) < 1e-12, 1e-12, kappa)   # sign: + convex for this orientation
    if np.median(rho) < 0:
        rho = -rho
    # surface: offset pitch curve inward by roller radius
    nrm = np.hypot(dx, dy)
    nx, ny = dy / nrm, -dx / nrm                          # right-hand normal
    if np.mean(nx * px + ny * py) > 0:                    # make it point inward
        nx, ny = -nx, -ny
    sx, sy = px + rf * nx, py + rf * ny
    return {"theta": th, "s": s, "sp": sp, "spp": spp, "phi": phi, "rho": rho, "rf": rf, "rb": rb, "rp": rp,
            "pitch": (px, py), "surface": (sx, sy)}


def _follower_mass(proj, axis_id, cam) -> float:
    m = float(cam.get("follower_mass_kg", 0.0))
    for p in proj.data.get("bom", {}).get("parts", []):
        if p.get("moves_with") == axis_id:
            mv = p.get("specs", {}).get("mass_kg", 0.0)
            m += float(mv["value"] if isinstance(mv, dict) else mv) * p.get("qty", 1)
    return m


def check_cam(proj, axis_id: str, out_dir: Path | None) -> CheckResult:
    spec = proj.cycle["axes"][axis_id]
    cam = spec["cam"]
    lim = cam.get("limits", {})
    parts = {p["id"]: p for p in proj.data.get("bom", {}).get("parts", [])}
    a = analyse(proj, axis_id)
    cph = proj.speeds[-1][1]
    w = math.radians(omega_deg_s(cph))                    # rad/s
    issues, warns, lines = [], [], []

    # pressure angle
    phi_lim = float(lim.get("pressure_angle_deg", 30.0))
    closure = cam.get("closure", "force")
    rising = a["sp"] > 1e-9
    mask = rising if closure == "force" else np.ones_like(rising)
    phi_max = float(np.max(np.abs(a["phi"][mask]))) if mask.any() else 0.0
    (issues if phi_max > phi_lim else lines).append(
        f"pressure angle max {phi_max:.1f} deg ({'rise' if closure == 'force' else 'rise+return'}), limit {phi_lim}")

    # curvature / undercut
    rf = a["rf"]
    convex = a["rho"][a["rho"] > 0]
    rho_min = float(np.min(convex)) if len(convex) else float("inf")
    ratio = rho_min / rf
    rmin = float(lim.get("curvature_ratio_min", 2.0))
    if ratio < 1.0:
        issues.append(f"UNDERCUT: convex pitch radius {rho_min:.1f} mm < roller radius {rf:.1f} mm")
    elif ratio < 1.5:
        issues.append(f"pitch radius / roller radius {ratio:.2f} < 1.5")
    elif ratio < rmin:
        warns.append(f"pitch radius / roller radius {ratio:.2f} below target {rmin} (check Hertz stress)")
    else:
        lines.append(f"min convex pitch radius {rho_min:.1f} mm = {ratio:.1f} x roller radius")

    # forces
    m = _follower_mass(proj, axis_id, cam)
    k = float(cam.get("spring", {}).get("rate_n_per_mm", 0.0))
    f0 = float(cam.get("spring", {}).get("preload_n", 0.0))
    fext = float(cam.get("external_load_n", 0.0))
    acc = a["spp"] / 1000.0 * w * w                       # m/s^2
    f_follow = m * acc + (f0 + k * a["s"] if closure == "force" else 0.0) + fext * (a["sp"] > 0)
    fn = np.abs(f_follow) / np.cos(np.radians(a["phi"]))
    if closure == "force":
        margin = float(lim.get("jump_margin_n", 10.0))
        fmin = float(np.min(f_follow))
        i = int(np.argmin(f_follow))
        (issues if fmin < margin else lines).append(
            f"min contact force {fmin:.1f} N at {a['theta'][i]:.1f} deg (follower jump if < {margin} N); "
            f"spring {f0:.0f} N + {k} N/mm, follower mass {m:.2f} kg")

    # Hertz (line contact)
    widths = [float(w) for w in (_spec(parts, cam.get("cam_part"), "width_mm"), _spec(parts, cam.get("roller_part"), "width_mm")) if w]
    width = min(widths) if widths else 10.0   # contact length = narrower of cam and roller
    e1 = float(_spec(parts, cam.get("cam_part"), "e_modulus_gpa", 205.0)) * 1e3
    e2 = float(_spec(parts, cam.get("roller_part"), "e_modulus_gpa", 205.0)) * 1e3
    nu = 0.3
    rc = np.where(a["rho"] > 0, a["rho"] - rf, a["rho"] - rf)      # cam surface radius (concave negative)
    rc = np.where(np.abs(rc) < 1e-6, 1e-6, rc)
    curv = 1.0 / rf + 1.0 / rc
    estar = 1.0 / ((1 - nu ** 2) / e1 + (1 - nu ** 2) / e2)        # MPa
    p_hz = np.sqrt(np.maximum(fn, 0) / (math.pi * width) * np.maximum(curv, 0) * estar)  # N/mm^2 = MPa
    allow = _spec(parts, cam.get("cam_part"), "allowable_hertz_mpa")
    pmax = float(np.max(p_hz))
    if allow is None:
        warns.append(f"Hertz stress {pmax:.0f} MPa: cam material allowable not in BOM: NOT VERIFIED")
    else:
        (issues if pmax > float(allow) else lines).append(f"Hertz stress {pmax:.0f} MPa, allowable {allow} MPa")

    # roller bearing
    rp = cam.get("roller_part")
    if rp in parts:
        v_contact = np.abs(a["sp"]) / 1000.0 * w + (a["rp"] / 1000.0) * w     # approx. surface speed m/s
        n_roll = float(np.max(v_contact) / (2 * math.pi * rf / 1000.0) * 60.0)
        nlim = _spec(parts, rp, "max_speed_rpm")
        if nlim is not None:
            (issues if n_roll > float(nlim) else lines).append(f"roller speed {n_roll:,.0f} rpm, rated {nlim}")
        track = _spec(parts, rp, "track_load_capacity_n")
        if track is not None:
            (issues if float(np.max(fn)) > float(track) else lines).append(
                f"peak contact force {np.max(fn):.0f} N, roller track load capacity {track} N")
        c_dyn = _spec(parts, rp, "dynamic_load_rating_n")
        need_h = float(lim.get("roller_life_h", 20000))
        if c_dyn is not None:
            p_eq = float(np.mean(fn ** (10 / 3)) ** (3 / 10))            # equivalent load over the cycle
            n_mean = float(np.mean(v_contact) / (2 * math.pi * rf / 1000.0) * 60.0)
            l10_h = (float(c_dyn) / max(p_eq, 1e-9)) ** (10 / 3) * 1e6 / (60.0 * max(n_mean, 1e-9))
            (issues if l10_h < need_h else lines).append(
                f"roller L10 life {l10_h:,.0f} h at P_eq {p_eq:.0f} N (need {need_h:,.0f} h)")
        else:
            warns.append("roller dynamic load rating not in BOM: life NOT VERIFIED")

    # camshaft torque
    torque = f_follow * a["sp"] / 1000.0                  # N*m (F * ds/dtheta)
    lines.append(f"camshaft torque peak {np.max(np.abs(torque)):.2f} Nm, RMS {np.sqrt(np.mean(torque**2)):.2f} Nm "
                 f"@ {cph:g} cph (add to main-drive sizing)")
    lines.append(f"base circle R{a['rb']:.0f}, roller R{rf:.1f}, stroke {np.ptp(a['s']):.1f} mm")

    if out_dir is not None:
        _export(axis_id, a, out_dir / "cams", float(_spec(parts, cam.get("cam_part"), "width_mm") or width))
        lines.append(f"profile exported: build/cams/{axis_id}.dxf / .csv / .step")
    status = FAIL if issues else (WARN if warns else PASS)
    return CheckResult(f"CAM-{axis_id.upper()}", status,
                       f"plate cam, translating roller, {closure}-closed @ {cph:g} cph", issues + warns + lines,
                       speed="max", data={"torque_peak_nm": float(np.max(np.abs(torque))),
                                          "torque_rms_nm": float(np.sqrt(np.mean(torque ** 2)))})


def _export(axis_id: str, a: dict, out: Path, width: float):
    out.mkdir(parents=True, exist_ok=True)
    sx, sy = a["surface"]
    with open(out / f"{axis_id}.csv", "w") as fh:
        fh.write("theta_deg,follower_mm,surface_x_mm,surface_y_mm,pressure_angle_deg\n")
        for row in zip(a["theta"], a["s"], sx, sy, a["phi"]):
            fh.write(",".join(f"{v:.4f}" for v in row) + "\n")
    dxf = ["0", "SECTION", "2", "ENTITIES", "0", "POLYLINE", "8", "CAM", "66", "1", "70", "1"]
    for x, y in zip(sx, sy):
        dxf += ["0", "VERTEX", "8", "CAM", "10", f"{x:.4f}", "20", f"{y:.4f}", "30", "0.0"]
    dxf += ["0", "SEQEND", "0", "CIRCLE", "8", "BORE", "10", "0.0", "20", "0.0", "30", "0.0", "40", "10.0",
            "0", "ENDSEC", "0", "EOF"]
    (out / f"{axis_id}.dxf").write_text("\n".join(dxf) + "\n")
    try:
        from build123d import Polyline, export_step, extrude, make_face
        pts = [(float(x), float(y)) for x, y in zip(sx[::4], sy[::4])]
        solid = extrude(make_face(Polyline(*pts, close=True)), amount=width)
        export_step(solid, str(out / f"{axis_id}.step"))
    except Exception:  # noqa: BLE001 - DXF/CSV are the primary outputs
        pass


def run_cams(proj, out_dir: Path | None = None) -> list[CheckResult]:
    out_dir = out_dir or proj.root / "build"
    res = []
    for aid, spec in proj.cycle["axes"].items():
        if spec.get("type") == "mechanical_cam" and spec.get("cam"):
            res.append(check_cam(proj, aid, out_dir))
    return res
