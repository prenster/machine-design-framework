"""Traceability, assumption audit, markdown report and side-view SVG."""
from __future__ import annotations

from pathlib import Path

from shapely import affinity
from shapely.geometry import Polygon

from .checks import FAIL, PASS, WARN, CheckResult, World
from .project import Project

RANK = {PASS: 0, "REVIEW": 1, "PENDING": 1, WARN: 2, FAIL: 3}


def traceability(proj: Project, results: list[CheckResult]) -> list[dict]:
    by_check: dict[str, str] = {}
    for r in results:
        prev = by_check.get(r.check_id, PASS)
        by_check[r.check_id] = r.status if RANK[r.status] > RANK[prev] else prev
    tests = {t["id"]: t for t in proj.data["tests"]["tests"]}
    rows = []
    for req in proj.data["requirements"]["requirements"]:
        v = req["verification"]
        refs = v["ref"] if isinstance(v.get("ref"), list) else ([v["ref"]] if v.get("ref") else [])
        status, note = PASS, ""
        if v["method"] == "check":
            for ref in refs:
                s = by_check.get(ref)
                if s is None:
                    status, note = FAIL, f"no check named {ref}"
                    break
                if RANK[s] > RANK[status]:
                    status = s
                if s != PASS:
                    note = (note + "; " if note else "") + f"{ref} {s}"
        elif v["method"] == "test":
            for ref in refs:
                t = tests.get(ref)
                if t is None:
                    status, note = FAIL, f"no physical test named {ref}"
                    break
                if t.get("status") != "done":
                    status, note = "PENDING", f"{ref} not yet run"
                elif t.get("result") != "pass":
                    status, note = FAIL, f"{ref} result: {t.get('result')}"
        else:
            status, note = "REVIEW", "needs chief-engineer review"
        rows.append({"id": req["id"], "text": req["text"], "method": v["method"],
                     "refs": ", ".join(refs), "status": status, "note": note})
    return rows


def assumption_audit(proj: Project) -> list[dict]:
    tests = {t["id"]: t for t in proj.data["tests"]["tests"]}
    rows = []
    for name, p in proj.data["params"]["params"].items():
        if p.get("source") != "assumed":
            continue
        tid = p.get("calibrated_by")
        t = tests.get(tid) if tid else None
        if not tid or t is None:
            status = FAIL
            note = "assumed with no calibrating physical test: the sim's verdict rests on a guess nobody will check"
        elif t.get("status") == "done":
            status, note = WARN, f"{tid} has been run: replace the assumed value with the measured one"
        else:
            status, note = "PENDING", f"calibrated by {tid} (not yet run)"
        rows.append({"param": name, "value": p["value"], "unit": p.get("unit", ""), "status": status, "note": note})
    return rows


def overall(results, trace, audit) -> str:
    worst = PASS
    for s in [r.status for r in results] + [t["status"] for t in trace] + [a["status"] for a in audit]:
        if s in (FAIL, WARN) and RANK[s] > RANK[worst]:
            worst = s
    return worst


def markdown(proj: Project, results, trace, audit) -> str:
    verdict = overall(results, trace, audit)
    name = proj.data["requirements"].get("station", proj.root.name)
    out = [f"# Verification report: {name}", "",
           f"**Verdict: {verdict}** (FAIL blocks the gate; PENDING items are physical tests still owed)", "",
           "## Checks", "", "| Check | Speed | Status | Summary |", "|---|---|---|---|"]
    for r in results:
        out.append(f"| {r.check_id} | {r.speed or '-'} | {r.status} | {r.summary} |")
    out += ["", "### Details", ""]
    for r in results:
        if r.details and (r.status != PASS or r.check_id in ("SWEEP-CLEARANCE", "VALVE-TIMING")):
            out.append(f"**{r.check_id}** ({r.speed or '-'}, {r.status})")
            out += [f"- {d}" for d in r.details]
            out.append("")
    out += ["## Requirements traceability", "", "| Req | Method | Ref | Status | Note |", "|---|---|---|---|---|"]
    for t in trace:
        out.append(f"| {t['id']} | {t['method']} | {t['refs']} | {t['status']} | {t['note']} |")
    out += ["", "## Assumptions the simulation rests on", "",
            "Every PASS above is conditional on these values. Each must be replaced by a measurement.", "",
            "| Parameter | Value | Status | Note |", "|---|---|---|---|"]
    for a in audit:
        out.append(f"| {a['param']} | {a['value']} {a['unit']} | {a['status']} | {a['note']} |")
    return "\n".join(out) + "\n"


def side_view_svg(proj: Project, path: Path) -> None:
    """Side view: static bodies, carrier-origin path, product at key angles."""
    cph = proj.speeds[1][1]
    world = World(proj, cph)
    shapes: list[tuple[Polygon, str, str]] = []
    for _, poly in world.static:
        shapes.append((poly, "#c9c9c9", "#555"))
    on, off = world.grip
    glue = proj.layout.get("glue")
    keys = [("pick", on), ("place", off)]
    if glue:
        gon, _ = world.valve_window(glue["valve"])
        keys.insert(1, ("glue", gon))
    colors = {"pick": "#2b7bb9", "glue": "#d98c1f", "place": "#2e9e5b"}
    for label, t in keys:
        x, z = world.carrier(t)
        shapes.append((affinity.translate(world.product_poly, x, z), "none", colors[label]))
        for _, b in world.carrier_bodies:
            shapes.append((affinity.translate(b, x, z), "none", colors[label]))
    pts = [world.carrier(t / 2) for t in range(720)]
    xs = [p[0] for p in pts] + [c[0] for s, _, _ in shapes for c in s.exterior.coords]
    zs = [p[1] for p in pts] + [c[1] for s, _, _ in shapes for c in s.exterior.coords]
    pad = 20
    minx, maxx, minz, maxz = min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad
    scale = 1400 / (maxx - minx)
    zex = 4.0  # vertical exaggeration so mm-scale clearances are visible
    W, H = 1400, (maxz - minz) * scale * zex

    def tx(x, z):
        return (x - minx) * scale, H - (z - minz) * scale * zex

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H + 40:.0f}" '
             f'viewBox="0 0 {W:.0f} {H + 40:.0f}" font-family="sans-serif" font-size="13">',
             '<rect width="100%" height="100%" fill="white"/>']
    for poly, fill, stroke in shapes:
        d = " ".join(f"{a:.1f},{b:.1f}" for a, b in (tx(*c) for c in poly.exterior.coords))
        parts.append(f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    path_d = " ".join(f"{a:.1f},{b:.1f}" for a, b in (tx(*p) for p in pts))
    parts.append(f'<polyline points="{path_d}" fill="none" stroke="#b03030" stroke-dasharray="5,4"/>')
    if glue:
        nx, nz = tx(glue["nozzle_x"], glue["nozzle_z"])
        parts.append(f'<circle cx="{nx:.1f}" cy="{nz:.1f}" r="4" fill="#d98c1f"/>')
    legend = "  ".join(f"{k} @ {t:.1f}°" for k, t in keys)
    parts.append(f'<text x="10" y="{H + 25:.0f}">Side view @ {cph:g} cph, vertical x4. Dashed: carrier origin path. '
                 f'Outlines: carrier + product at {legend}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts))
