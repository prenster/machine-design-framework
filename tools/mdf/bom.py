"""BOM, interface, sizing and I/O consistency checks.

Catches conflicts *between* specifications - the class of error that survives every per-part review:
  BOM-IFACE   connected ports disagree (shaft 14 mm into a 12 mm bore, 24 VDC coil on a 230 VAC output,
              G1/8 fitting into an M5 port, encoder protocol mismatch, drive current below motor current),
              or a required port is left unconnected
  BOM-XREF    the same fact stated twice disagrees: params.yaml says 'datasheet' but the BOM part says
              otherwise; layout/3D bodies reference parts that are not in the BOM
  BOM-SIZING  each axis vs. its catalog module and motor at max speed: speed, acceleration, stroke,
              payload, peak torque, RMS torque, motor rpm, inertia ratio
  BOM-CONSTRAINT  project-specific rules in constraints.yaml (air budget, 24 V budget, valve frequency...)
  IO-MAP      I/O list vs. cards and devices: channel collisions, voltage/current mismatch, safety devices
              on non-safety inputs, cycle valves without an output
"""
from __future__ import annotations

import ast
import math
import operator
from types import SimpleNamespace

import numpy as np

from .checks import FAIL, PASS, WARN, CheckResult
from .motion import omega_deg_s
from .project import Project

G = 9.81

# (out_type, in_type): [(spec_key, relation)]   relation: eq | ge (out >= in)
COMPAT = {
    ("shaft_out", "shaft_in"): [("diameter_mm", "eq")],
    ("motor_power_out", "motor_power_in"): [("voltage_v", "eq"), ("current_a", "ge")],
    ("encoder_out", "encoder_in"): [("protocol", "eq")],
    ("pneumatic_out", "pneumatic_in"): [("thread", "eq")],
    ("vacuum_out", "vacuum_in"): [("thread", "eq")],
    ("fieldbus", "fieldbus"): [("protocol", "eq")],
    ("mount_male", "mount_female"): [("pattern", "eq")],
    ("tube_out", "tube_in"): [("od_mm", "eq")],
}


def _spec(part: dict, key: str):
    v = part.get("specs", {}).get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v


def parts_by_id(proj: Project) -> dict:
    return {p["id"]: p for p in proj.data["bom"]["parts"]}


# -------------------------------------------------------------- interfaces
def check_interfaces(proj: Project) -> list[CheckResult]:
    parts = parts_by_id(proj)
    issues, unverified, ok = [], [], 0
    connected = set()
    for a_ref, b_ref in proj.data["bom"].get("connections", []):
        try:
            (ap, an), (bp, bn) = a_ref.split("."), b_ref.split(".")
        except ValueError:
            issues.append(f"bad connection reference {a_ref} - {b_ref} (use PART.port)")
            continue
        if ap not in parts or bp not in parts:
            issues.append(f"{a_ref} - {b_ref}: part not in BOM")
            continue
        pa = {p["name"]: p for p in parts[ap].get("ports", [])}.get(an)
        pb = {p["name"]: p for p in parts[bp].get("ports", [])}.get(bn)
        if pa is None or pb is None:
            issues.append(f"{a_ref} - {b_ref}: port not defined on part")
            continue
        connected |= {(ap, an), (bp, bn)}
        rules = COMPAT.get((pa["type"], pb["type"]))
        if rules is None and (pb["type"], pa["type"]) in COMPAT:
            pa, pb, a_ref, b_ref = pb, pa, b_ref, a_ref
            rules = COMPAT[(pa["type"], pb["type"])]
        if rules is None:
            issues.append(f"{a_ref} ({pa['type']}) cannot connect to {b_ref} ({pb['type']})")
            continue
        bad = False
        for key, rel in rules:
            va, vb = pa.get("spec", {}).get(key), pb.get("spec", {}).get(key)
            if va is None or vb is None:
                unverified.append(f"{a_ref} - {b_ref}: '{key}' not known on one side: NOT VERIFIED (look it up)")
                bad = True
            elif rel == "eq" and va != vb:
                issues.append(f"{a_ref} - {b_ref}: {key} {va} != {vb}")
                bad = True
            elif rel == "ge" and float(va) < float(vb):
                issues.append(f"{a_ref} - {b_ref}: {key} supply {va} < demand {vb}")
                bad = True
        ok += not bad
    for pid, part in parts.items():
        for port in part.get("ports", []):
            if port.get("required") and (pid, port["name"]) not in connected:
                issues.append(f"{pid}.{port['name']} ({port['type']}) is required but not connected")
    status = FAIL if issues else (WARN if unverified else PASS)
    return [CheckResult("BOM-IFACE", status,
                        f"{ok} connections verified, {len(issues)} conflicts, {len(unverified)} unverified",
                        issues + unverified)]


# ------------------------------------------------------------ cross-refs
def check_xref(proj: Project) -> list[CheckResult]:
    parts = parts_by_id(proj)
    issues, n = [], 0
    for name, p in proj.data["params"]["params"].items():
        ref = p.get("from_part")
        if not ref:
            if p.get("source") == "datasheet":
                issues.append(f"param {name} is 'datasheet' but names no BOM part (from_part: PART.spec)")
            continue
        n += 1
        pid, key = ref.split(".", 1)
        if pid not in parts:
            issues.append(f"param {name}: from_part {pid} not in BOM")
            continue
        v = _spec(parts[pid], key)
        if v is None:
            issues.append(f"param {name}: {pid} has no spec '{key}'")
        elif abs(float(v) - float(p["value"])) > 1e-9 * max(1.0, abs(float(v))):
            issues.append(f"param {name} = {p['value']} but {pid}.{key} = {v} (BOM and params disagree)")
    refs = [b.get("part") for b in proj.layout["carrier"]["bodies"] + proj.layout["static"] if b.get("part")]
    a3 = proj.data.get("assembly3d")
    if a3:
        refs += [b.get("part") for b in a3["bodies"] if b.get("part")]
    for r in sorted(set(refs)):
        n += 1
        if r not in parts:
            issues.append(f"geometry references part {r}, which is not in the BOM")
    for axis_id, spec in proj.cycle["axes"].items():
        for k in ("module", "motor"):
            if spec.get(k) and spec[k] not in parts:
                issues.append(f"axis {axis_id} {k} {spec[k]} not in BOM")
    return [CheckResult("BOM-XREF", FAIL if issues else PASS, f"{n} cross-references, {len(issues)} conflicts", issues)]


# ---------------------------------------------------------------- sizing
def axis_derived(proj: Project) -> dict:
    parts = parts_by_id(proj)
    cph = proj.speeds[-1][1]
    w = omega_deg_s(cph)
    out = {}
    # which axes carry which: an axis listed in 'rides_on' moves with that axis
    rides = {aid: s.get("rides_on") for aid, s in proj.cycle["axes"].items()}

    def carried_by(axis_id):
        """all axes whose motion is carried by axis_id (itself + axes riding on it, transitively)"""
        res = {axis_id}
        changed = True
        while changed:
            changed = False
            for a, r in rides.items():
                if r in res and a not in res:
                    res.add(a)
                    changed = True
        return res

    for aid, spec in proj.cycle["axes"].items():
        mod, mot = parts.get(spec.get("module")), parts.get(spec.get("motor"))
        ax = proj.axes[aid]
        th = np.arange(0, 360, 0.1)
        ev = np.array([ax.eval(t) for t in th])
        pos, vel, acc = ev[:, 0], ev[:, 1] * w, ev[:, 2] * w * w        # mm, mm/s, mm/s^2
        d = SimpleNamespace(v_peak=float(np.max(np.abs(vel))), a_peak=float(np.max(np.abs(acc))),
                            pos_min=float(pos.min()), pos_max=float(pos.max()))
        group = carried_by(aid)
        payload = 0.0
        for p in parts.values():
            if p.get("moves_with") in group:
                payload += float(_spec(p, "mass_kg") or 0.0) * p.get("qty", 1)
        d.payload_kg = payload
        if mod and mot:
            carriage = float(_spec(mod, "carriage_mass_kg") or 0.0)
            m = payload + carriage
            feed = float(_spec(mod, "feed_mm_per_rev")) / 1000.0           # m/rev
            eta = float(_spec(mod, "efficiency") or 0.9)
            fric = float(_spec(mod, "friction_n") or 0.0)
            vertical = (_spec(mod, "orientation") == "vertical")
            fric_t = float(_spec(mod, "friction_torque_nm") or 0.0)   # load-independent drag torque at the input
            j = (float(_spec(mot, "rotor_inertia_kgcm2")) + float(_spec(mod, "input_inertia_kgcm2") or 0.0)
                 + float(_spec(mod, "coupling_inertia_kgcm2") or 0.0)) * 1e-4
            k = feed / (2 * math.pi)                                       # m per rad
            a_si, v_si = acc / 1000.0, vel / 1000.0
            force = m * a_si + (m * G if vertical else 0.0) + fric * np.sign(v_si)
            torque = force * k / eta + j * a_si / k + fric_t * np.sign(v_si)
            d.moving_mass_kg = m
            d.force_peak_n = float(np.max(np.abs(force)))
            d.torque_peak_nm = float(np.max(np.abs(torque)))
            d.torque_rms_nm = float(np.sqrt(np.mean(torque**2)))
            d.speed_peak_rpm = d.v_peak / 1000.0 / feed * 60.0
            d.inertia_ratio = (m * k**2 + (float(_spec(mod, "input_inertia_kgcm2") or 0.0) + float(_spec(mod, "coupling_inertia_kgcm2") or 0.0)) * 1e-4) / (float(_spec(mot, "rotor_inertia_kgcm2")) * 1e-4)
        out[aid] = d
    return out


def check_sizing(proj: Project) -> list[CheckResult]:
    parts = parts_by_id(proj)
    der = axis_derived(proj)
    margin = proj.param("sizing_torque_margin") if "sizing_torque_margin" in proj.data["params"]["params"] else 1.25
    results = []
    for aid, spec in proj.cycle["axes"].items():
        mod, mot = parts.get(spec.get("module")), parts.get(spec.get("motor"))
        if spec.get("type") == "mechanical_cam":
            continue      # sized by CAM-<axis>
        if not (mod and mot):
            results.append(CheckResult("BOM-SIZING", WARN, f"axis {aid}: no module/motor in cycle.yaml, not sized"))
            continue
        d = der[aid]
        rows = [
            ("speed", d.v_peak, _spec(mod, "v_max_mm_s"), "mm/s"),
            ("acceleration", d.a_peak, _spec(mod, "a_max_mm_s2"), "mm/s^2"),
            ("stroke", d.pos_max - min(0.0, d.pos_min), _spec(mod, "stroke_mm"), "mm"),
            ("payload", d.payload_kg, _spec(mod, "payload_max_kg"), "kg"),
            ("module drive torque", d.torque_peak_nm, _spec(mod, "max_drive_torque_nm"), "Nm"),
            ("peak torque x margin", d.torque_peak_nm * margin, _spec(mot, "peak_torque_nm"), "Nm"),
            ("RMS torque x margin", d.torque_rms_nm * margin, _spec(mot, "rated_torque_nm"), "Nm"),
            ("motor speed", d.speed_peak_rpm, _spec(mot, "max_speed_rpm"), "rpm"),
        ]
        issues, lines, unv = [], [], []
        for name, need, have, unit in rows:
            if have is None:
                unv.append(f"{name}: need {need:,.2f} {unit}, limit not in BOM: NOT VERIFIED")
                continue
            have = float(have)
            line = f"{name}: need {need:,.2f} / have {have:,.2f} {unit} ({need / have:.0%})"
            (issues if need > have else lines).append(line)
        if d.pos_min < -1e-6:
            issues.append(f"cycle drives axis to {d.pos_min:.2f} mm, below the module's zero end")
        ir = d.inertia_ratio
        warn = []
        if ir > 10:
            warn.append(f"load/rotor inertia ratio {ir:.1f}:1 > 10:1 - tuning will be soft; consider larger rotor or gearbox")
        lines.append(f"moving mass {d.moving_mass_kg:.2f} kg, peak force {d.force_peak_n:.0f} N, inertia ratio {ir:.1f}:1")
        warn += unv
        status = FAIL if issues else (WARN if warn else PASS)
        results.append(CheckResult("BOM-SIZING", status,
                                   f"axis {aid} ({spec['module']} + {spec['motor']}) @ {proj.speeds[-1][1]:g} cph, "
                                   f"torque margin x{margin}",
                                   issues + warn + lines, speed="max"))
    return results


# ----------------------------------------------------------- constraints
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
        ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.Eq: operator.eq, ast.NotEq: operator.ne}
_FUNCS = {"min": min, "max": max, "abs": abs, "sqrt": math.sqrt}


def _eval(node, ns):
    if isinstance(node, ast.Expression):
        return _eval(node.body, ns)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ns:
            raise KeyError(node.id)
        return ns[node.id]
    if isinstance(node, ast.Attribute):
        base = _eval(node.value, ns)
        if isinstance(base, dict):
            if node.attr not in base:
                raise KeyError(node.attr)
            return base[node.attr]
        return getattr(base, node.attr)
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval(node.left, ns), _eval(node.right, ns))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval(node.operand, ns))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a, ns) for a in node.args])
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ns)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, ns)
            if not _OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, ns) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    raise ValueError(f"unsupported expression element {type(node).__name__}")


def namespace(proj: Project) -> dict:
    parts = parts_by_id(proj)
    part_ns = {pid: {k: (v["value"] if isinstance(v, dict) else v) for k, v in p.get("specs", {}).items()}
               for pid, p in parts.items()}
    for pid, p in parts.items():
        part_ns[pid]["qty"] = p.get("qty", 1)
    params = {k: v["value"] for k, v in proj.data["params"]["params"].items()}
    cph = proj.speeds[-1][1]
    budget = SimpleNamespace()
    budget.current_24v_a = sum(float(_spec(p, "supply_24v_current_a") or 0) * p.get("qty", 1) for p in parts.values())
    air = 0.0
    io = proj.data.get("io_list", {})
    for s in io.get("signals", []):
        dev = parts.get(s.get("air_consumer") or s.get("device"))
        if dev and s.get("cycle_valve"):
            v = proj.cycle["valves"][s["cycle_valve"]]
            duty = ((v["off"] - v["on"]) % 360.0) / 360.0
            air += float(_spec(dev, "air_consumption_nl_min") or 0) * duty
    for p in parts.values():
        air += float(_spec(p, "air_consumption_nl_min_continuous") or 0) * p.get("qty", 1)
    budget.air_nl_min = air
    return {"part": part_ns, "param": params, "axis": axis_derived(proj), "budget": budget,
            "cycles_per_s_max": cph / 3600.0, "cph_max": cph}


def check_constraints(proj: Project) -> list[CheckResult]:
    cons = proj.data.get("constraints", {}).get("constraints", [])
    if not cons:
        return []
    ns = namespace(proj)
    results = []
    for c in cons:
        try:
            tree = ast.parse(c["expr"], mode="eval")
            ok = bool(_eval(tree, ns))
            detail = []
            body = tree.body
            if isinstance(body, ast.Compare) and len(body.comparators) == 1:
                lhs = _eval(body.left, ns)
                rhs = _eval(body.comparators[0], ns)
                detail.append(f"{c['expr']}  ->  {lhs:,.4g} vs {rhs:,.4g}"
                              if isinstance(lhs, (int, float)) and isinstance(rhs, (int, float))
                              else f"{c['expr']}  ->  {lhs!r} vs {rhs!r}")
            status = PASS if ok else FAIL
            summary = c.get("text", c["expr"])
            if not ok and c.get("fail_message"):
                detail.insert(0, c["fail_message"])
        except (KeyError, ValueError, ZeroDivisionError, TypeError) as e:
            status, summary, detail = FAIL, c.get("text", c["expr"]), [f"cannot evaluate: {e}"]
        results.append(CheckResult(c["id"], status, summary, detail))
    return results


# --------------------------------------------------------------------- I/O
def check_io(proj: Project) -> list[CheckResult]:
    io = proj.data.get("io_list")
    if not io:
        return []
    parts = parts_by_id(proj)
    issues, used = [], {}
    n = 0
    for s in io["signals"]:
        if s.get("virtual"):
            continue
        n += 1
        tag = s["tag"]
        card, dev = parts.get(s.get("card")), parts.get(s.get("device"))
        if card is None:
            issues.append(f"{tag}: card {s.get('card')} not in BOM")
            continue
        if dev is None:
            issues.append(f"{tag}: device {s.get('device')} not in BOM")
            continue
        key = (s["card"], s["ch"])
        if key in used:
            issues.append(f"{tag}: {s['card']} ch {s['ch']} already used by {used[key]}")
        used[key] = tag
        chans = int(_spec(card, "channels"))
        if not (0 <= s["ch"] < chans):
            issues.append(f"{tag}: channel {s['ch']} does not exist on {s['card']} ({chans} channels)")
        kind = _spec(card, "io_type")
        if s["dir"] == "out" and kind not in ("DO", "SDO"):
            issues.append(f"{tag}: output wired to {s['card']} ({kind})")
        if s["dir"] == "in" and kind not in ("DI", "SDI"):
            issues.append(f"{tag}: input wired to {s['card']} ({kind})")
        cv = _spec(card, "voltage_v")
        if s["dir"] == "out":
            dv = _spec(dev, "coil_voltage_v")
            if dv is not None and dv != cv:
                issues.append(f"{tag}: {s['device']} coil {dv} V on {s['card']} output {cv} V")
            di, ci = _spec(dev, "coil_current_a"), _spec(card, "current_per_channel_a")
            if di is not None and ci is not None and float(di) > float(ci):
                issues.append(f"{tag}: {s['device']} draws {di} A, {s['card']} channel rated {ci} A")
        else:
            dv = _spec(dev, "signal_voltage_v")
            if dv is not None and dv != cv:
                issues.append(f"{tag}: {s['device']} signals {dv} V into {s['card']} {cv} V input")
        if _spec(dev, "safety_rated") and not _spec(card, "safety_rated"):
            issues.append(f"{tag}: safety device {s['device']} wired to non-safety card {s['card']}")
    mapped = {s.get("cycle_valve") for s in io["signals"] if s.get("cycle_valve")}
    for v in proj.cycle["valves"]:
        if v not in mapped:
            issues.append(f"cycle valve '{v}' has no output signal in io_list.yaml")
    return [CheckResult("IO-MAP", FAIL if issues else PASS, f"{n} physical signals, {len(issues)} conflicts", issues)]


def run_bom(proj: Project) -> list[CheckResult]:
    if "bom" not in proj.data:
        return []
    return check_interfaces(proj) + check_xref(proj) + check_sizing(proj) + check_constraints(proj) + check_io(proj)
