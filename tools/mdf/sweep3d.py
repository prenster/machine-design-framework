"""3D collision / clearance sweep over the full machine cycle.

Geometry comes from the project's build123d script (cad/station.py: build(params) -> {id: Part}).
Each body is tessellated once, then for every machine angle (step_deg) and every speed:
  - moving frames are placed from the cycle diagram (x, z axes)
  - the product is present only while gripped (valve delays at that speed), and stays where it was
    released (endsheet_placed) until it leaves the station
  - every pair of bodies in different frames is checked with FCL: interference, then minimum distance
    against the required clearance (layout.yaml rules by body id; default otherwise)
Mechanically guided contacts (carriage on its rail...) are declared in layout clearance.guided_pairs.

Outputs: SWEEP-3D results, build/station.step (assembly at 0 deg) and build/station.glb for viewing.
The flexible sheet is checked in the planar sweep (SHEET-DYN); in 3D the product is rigid.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import fcl
import numpy as np
import trimesh

from .checks import FAIL, PASS, CheckResult, World, clearance_required, frange


def _load_cad(proj):
    a3 = proj.data["assembly3d"]
    path = proj.root / a3["cad"]
    spec = importlib.util.spec_from_file_location(f"cad_{hashlib.md5(str(path).encode()).hexdigest()}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    params = {k: v["value"] for k, v in proj.data["params"]["params"].items()}
    return mod.build(params)


def _mesh(part) -> trimesh.Trimesh:
    verts, tris = part.tessellate(0.05)
    v = np.array([[p.X, p.Y, p.Z] for p in verts], dtype=float)
    return trimesh.Trimesh(vertices=v, faces=np.array(tris, dtype=np.int64), process=True)


def _fcl_obj(mesh: trimesh.Trimesh):
    m = fcl.BVHModel()
    m.beginModel(len(mesh.vertices), len(mesh.faces))
    m.addSubModel(mesh.vertices, mesh.faces)
    m.endModel()
    return fcl.CollisionObject(m, fcl.Transform())


def _export(parts: dict, out: Path):
    try:
        from build123d import Compound, export_step
        export_step(Compound(children=list(parts.values())), str(out / "station.step"))
    except Exception:  # noqa: BLE001 - viewing artefact only
        pass
    scene = trimesh.Scene()
    for bid, part in parts.items():
        scene.add_geometry(_mesh(part), node_name=bid, geom_name=bid)
    scene.export(str(out / "station.glb"))


def _overlap_depth(ma, oa, mb, ob) -> float:
    """Smallest extent of the intersection volume (mm); 0 for touching bodies."""
    a = ma.copy()
    a.apply_translation(oa)
    b = mb.copy()
    b.apply_translation(ob)
    try:
        inter = trimesh.boolean.intersection([a, b], engine="manifold")
    except Exception:  # noqa: BLE001
        return 1.0     # cannot resolve: report as interference rather than hide it
    if inter is None or inter.is_empty or inter.volume < 1e-6:
        return 0.0
    ext = inter.bounds[1] - inter.bounds[0]
    return float(max(min(ext), 1e-3))


def run_3d(proj, out_dir: Path | None = None) -> list[CheckResult]:
    a3 = proj.data.get("assembly3d")
    if not a3:
        return []
    try:
        parts = _load_cad(proj)
    except Exception as e:  # noqa: BLE001
        return [CheckResult("SWEEP-3D", FAIL, "CAD script failed", [f"{type(e).__name__}: {e}"])]
    bodies = a3["bodies"]
    missing = [b["id"] for b in bodies if b["id"] not in parts]
    if missing:
        return [CheckResult("SWEEP-3D", FAIL, "bodies missing from CAD", [f"not built by cad script: {missing}"])]
    out_dir = out_dir or proj.root / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    _export(parts, out_dir)
    pre = [_cad_assert(a3, parts)] if any(b.get("expect") for b in bodies) else []

    frames = a3["frames"]
    meshes = {b["id"]: _mesh(parts[b["id"]]) for b in bodies}
    objs = {bid: _fcl_obj(m) for bid, m in meshes.items()}
    bounds = {bid: m.bounds for bid, m in meshes.items()}
    frame_of = {b["id"]: b["frame"] for b in bodies}
    product_id = proj.layout["product"]["id"]
    placed_id = f"{product_id}_placed"
    objs[placed_id] = _fcl_obj(meshes[product_id])
    bounds[placed_id] = bounds[product_id]
    frame_of[placed_id] = "placed"
    guided = {frozenset(p) for p in proj.layout["clearance"].get("guided_pairs", [])}
    ids = list(frame_of)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]
             if frame_of[a] != frame_of[b] and frozenset((a, b)) not in guided
             and not ({frame_of[a], frame_of[b]} <= {"machine", "placed"})
             and not ({frame_of[a], frame_of[b]} == {"product", "xz"})]   # product is held by the xz frame
    step = float(a3.get("step_deg", 0.5))
    results = []
    req = fcl.DistanceRequest()
    creq = fcl.CollisionRequest()
    meshes_all = dict(meshes)
    meshes_all[placed_id] = meshes[product_id]
    for name, cph in proj.speeds:
        world = World(proj, cph)
        worst: dict[tuple, tuple[float, float, float]] = {}
        viol: dict[tuple, list[float]] = {}
        release_pose = world.carrier(world.grip[1])
        for t in frange(step):
            x, z = world.carrier(t)
            off = {"machine": (0.0, 0.0, 0.0), "placed": (release_pose[0], 0.0, release_pose[1])}
            for fid, f in frames.items():
                off[fid] = (x if f.get("x") else 0.0, 0.0, z if f.get("z") else 0.0)
            off["product"] = (x, 0.0, z)
            present = {bid: True for bid in ids}
            present[product_id] = world.gripped(t)
            present[placed_id] = world.placed(t)
            for bid in ids:
                if present[bid]:
                    objs[bid].setTranslation(np.array(off[frame_of[bid]]))
            for a, b in pairs:
                if not (present[a] and present[b]):
                    continue
                need = clearance_required(proj, a, b, t)
                # broad phase on translated AABBs
                oa, ob = np.array(off[frame_of[a]]), np.array(off[frame_of[b]])
                lo_a, hi_a = bounds[a][0] + oa, bounds[a][1] + oa
                lo_b, hi_b = bounds[b][0] + ob, bounds[b][1] + ob
                gap = np.maximum(0.0, np.maximum(lo_a - hi_b, lo_b - hi_a))
                if float(np.linalg.norm(gap)) > need + 3.0:
                    continue
                cres = fcl.CollisionResult()
                if fcl.collide(objs[a], objs[b], creq, cres):
                    # FCL reports touching (coplanar) faces as contact; measure the real overlap exactly
                    dep = _overlap_depth(meshes_all[a], oa, meshes_all[b], ob)
                    d = -dep if dep > 0 else 0.0
                else:
                    d = fcl.distance(objs[a], objs[b], req, fcl.DistanceResult())
                margin = d - need
                key = (a, b)
                if key not in worst or margin < worst[key][0]:
                    worst[key] = (margin, d, t)
                if margin < -1e-6:
                    viol.setdefault(key, []).append(t)
        details = []
        for (a, b), angs in sorted(viol.items()):
            _, d, t = worst[(a, b)]
            what = (f"INTERFERENCE ({-d:.2f} mm deep)" if d < 0
                    else f"{d:.2f} mm < {clearance_required(proj, a, b, t)} mm required")
            details.append(f"{a} vs {b}: {what} from {angs[0]:.1f} to {angs[-1]:.1f} deg (worst at {t:.1f} deg)")
        tight = sorted(((v[0], k, v) for k, v in worst.items() if k not in viol), key=lambda z: z[0])[:4]
        for margin, (a, b), (_, d, t) in tight:
            details.append(f"tightest OK: {a} vs {b}: {d:.2f} mm at {t:.1f} deg (margin {margin:.2f} mm)")
        results.append(CheckResult("SWEEP-3D", FAIL if viol else PASS,
                                   f"{len(meshes)} bodies, {len(pairs)} pairs x {len(frange(step))} steps @ {cph:g} cph, "
                                   f"{len(viol)} pairs in violation", details, speed=name,
                                   data={"worst": {k: v[0] for k, v in worst.items()}}))
    return pre + results


def _cad_assert(a3, parts) -> CheckResult:
    """Kernel measurements of each body against declared expectations (silent-failure screen)."""
    issues, ok = [], 0
    for b in a3["bodies"]:
        exp = b.get("expect")
        if not exp:
            continue
        part = parts[b["id"]]
        tol = float(exp.get("tol_pct", 1.0)) / 100.0
        bb = part.bounding_box()
        size = [bb.size.X, bb.size.Y, bb.size.Z]
        if "bbox_mm" in exp:
            for axis, got, want in zip("XYZ", size, exp["bbox_mm"]):
                if abs(got - want) > max(tol * abs(want), 0.01):
                    issues.append(f"{b['id']}: bounding box {axis} {got:.2f} mm, expected {want} mm")
        if "volume_mm3" in exp:
            vol = part.volume
            want = float(exp["volume_mm3"])
            if abs(vol - want) > tol * want:
                issues.append(f"{b['id']}: volume {vol:,.0f} mm3, expected {want:,.0f} mm3 "
                              f"(missing or extra internal feature?)")
        if "min_z_mm" in exp and abs(bb.min.Z - exp["min_z_mm"]) > 0.01:
            issues.append(f"{b['id']}: lowest point z {bb.min.Z:.2f} mm, expected {exp['min_z_mm']} mm")
        ok += 1
    return CheckResult("CAD-ASSERT", FAIL if issues else PASS,
                       f"{ok} bodies measured against declared expectations", issues)
