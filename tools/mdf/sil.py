"""Software-in-the-loop: the real Structured Text program against a plant model, with fault injection.

Each PLC scan (scan_ms):
  1. plant -> PLC inputs (machine angle, vacuum switch, double-sheet sensor, guard, e-stop, air, buttons)
  2. one scan of the transpiled ST program
  3. PLC outputs -> plant; plant advances one scan with exact event timing inside the scan:
     valve outputs change on scan boundaries (as in a real PLC task), devices respond after their
     millisecond delays (not quantised), grip/release/glue are evaluated at the exact effective times.

What this proves: sequencing, interlocks, fault reactions and output timing including scan
quantisation, against the same plant geometry the static checks use.
What it does not: drive dynamics (axes follow the cam exactly), fieldbus latency, safety-controller
behaviour (modelled only as the inputs the PLC sees).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .checks import FAIL, PASS, CheckResult
from .motion import ms_to_deg, omega_deg_s
from .project import Project
from . import st, plcgen


@dataclass
class SheetOutcome:
    cycle: int
    n: int = 1
    placed: bool = False
    dropped: bool = False
    dx: float | None = None
    bead: list[float] = field(default_factory=list)   # [min, max] sheet-x of glue
    gaps: list[float] = field(default_factory=list)


class Valve:
    def __init__(self, on_ms: float, off_ms: float):
        self.on_ms, self.off_ms = on_ms, off_ms
        self.cmd = False
        self.eff = False
        self.pending: tuple[float, bool] | None = None

    def command(self, state: bool, t: float):
        if state == self.cmd:
            return
        self.cmd = state
        target_t = t + (self.on_ms if state else self.off_ms)
        if self.pending and self.pending[1] != state:
            self.pending = None          # a pending opposite change is cancelled
            if self.eff == state:
                return
        if self.eff != state:
            self.pending = (target_t, state)


class Plant:
    def __init__(self, proj: Project, cph: float, scen: dict):
        self.p = proj
        self.cph = cph
        self.omega = omega_deg_s(cph) / 1000.0          # deg per ms
        lay = proj.layout
        car = lay["carrier"]
        self.ax_x, self.ax_z = proj.axes[car["x_axis"]], proj.axes[car["z_axis"]]
        self.ports = lay["ports"]
        self.glue = lay.get("glue")
        prod = lay["product"]["polygon"]
        self.L = max(pt[0] for pt in prod) - min(pt[0] for pt in prod)
        valves = proj.cycle["valves"]
        io = {s.get("cycle_valve"): s["tag"].lower() for s in proj.data["io_list"]["signals"] if s.get("cycle_valve")}
        self.valve_tag = io
        self.valves = {vid: Valve(proj.num(v["on_delay"]), proj.num(v["off_delay"])) for vid, v in valves.items()}
        self.grip_valve = lay["product"]["grip_valve"]
        self.glue_valve = self.glue["valve"] if self.glue else None
        self.angle = 0.0
        self.t = 0.0
        self.cycle = 0
        self.running = False
        self.stack = int(scen.get("stack", 10_000))
        self.gripped: SheetOutcome | None = None
        self.outcomes: list[SheetOutcome] = []
        self.glue_on_machine_mm = 0.0
        self.glue_by_cycle: dict[int, float] = {}
        self.inject = scen.get("inject", [])
        self.host_signals = proj.data.get("interfaces", {}).get("signals", [])
        self.host_data = {k.lower(): v for k, v in (scen.get("host_data") or {}).items()}
        self.follows = (scen.get("expect", {}).get("registration_follows") or "").lower()
        # per-cycle superimposed offsets on the carrier axes
        self.sup = {}
        for aid in (proj.layout["carrier"]["x_axis"], proj.layout["carrier"]["z_axis"]):
            sp = proj.cycle["axes"][aid].get("superimposed")
            if sp:
                self.sup[aid] = {"spec": sp, "prev": 0.0, "new": 0.0}
        self.prev_angle = 0.0
        self.inputs = {"xguardclosed": True, "xestopok": True, "xairok": True, "xglueready": True,
                       "xhostbookpresent": True,
                       "xstartpb": False, "xstoppb": False, "xresetpb": False,
                       "xsimdrivefaultx": False, "xsimdrivefaultz": False}
        self.events: list[tuple[float, str]] = []

    # -- geometry
    def _offset(self, axis_id, angle):
        st = self.sup.get(axis_id)
        if not st:
            return 0.0
        from .motion import offset_profile
        return offset_profile(angle, st["spec"]["blend"], st["spec"]["return_blend"], st["new"])

    def carrier(self, angle):
        return (self.ax_x.pos(angle) + self._offset(self.ax_x.id, angle),
                self.ax_z.pos(angle) + self._offset(self.ax_z.id, angle))

    def host_value(self, tag: str, cycle: int):
        vals = self.host_data.get(tag.lower())
        if not vals:
            return 0.0
        return float(vals[cycle % len(vals)])

    def at_port(self, angle, port, cycle=None):
        x, z = self.carrier(angle)
        p = self.ports[port]
        px = p["x"]
        if port == "place" and self.follows:
            px += self.host_value(self.follows, self.cycle if cycle is None else cycle)   # this book's own target
        return abs(x - px) <= p["tol_x"] and abs(z - p["z"]) <= p["tol_z"], x - px

    def _injected(self, kind: str) -> dict | None:
        for inj in self.inject:
            if inj["type"] == kind and self.cycle in inj.get("cycles", [inj.get("cycle")]):
                return inj
        return None

    # -- inputs for the PLC
    def plc_inputs(self) -> dict:
        d = dict(self.inputs)
        d["rangle"] = self.angle
        vac = self.valves[self.grip_valve]
        d["xvacok"] = bool(vac.eff and self.gripped is not None and self.inputs["xairok"])
        d["xdoublesheet"] = bool(self.gripped is not None and self.gripped.n >= 2)
        # host handshake: value for the NEXT cycle becomes valid at available_at + latency
        for sig in self.host_signals:
            if sig["tag"].lower() == "xhostbookpresent":
                valid_from = sig.get("available_at_deg", 0.0) + ms_to_deg(sig.get("latency_ms", 0.0), self.cph)
                target = self.cycle + 1 if self.angle >= valid_from % 360.0 and valid_from < 360 else self.cycle
                gap = any(i["type"] == "host_gap" and target in i.get("cycles", []) for i in self.inject)
                if self.angle >= valid_from % 360.0 or self.angle < 10:
                    d["xhostbookpresent"] = not gap
        for sig in self.host_signals:
            tag = sig["tag"].lower()
            if tag in self.host_data:
                valid = (sig.get("available_at_deg", 0.0) + ms_to_deg(sig.get("latency_ms", 0.0), self.cph)) % 360.0
                c = self.cycle if self.angle >= valid else self.cycle - 1
                if sig.get("applies_to", "current") == "next":
                    c += 1
                d[tag] = self.host_value(tag, c)
        g = self.gripped
        min_len = float(self.p.data["params"]["params"].get("bead_min_length_mm", {}).get("value", 0.0))
        d["xbeadok"] = bool(g is not None and len(g.bead) == 2 and (g.bead[1] - g.bead[0]) >= min_len)
        # scripted switches by cycle/angle
        for inj in self.inject:
            if inj.get("cycle") == self.cycle and self.angle >= inj.get("angle", 0) and not inj.get("_fired"):
                key = {"guard_open": "xguardclosed", "estop": "xestopok", "air_loss": "xairok",
                       "glue_not_ready": "xglueready", "drive_fault_x": "xsimdrivefaultx",
                       "drive_fault_z": "xsimdrivefaultz"}.get(inj["type"])
                if key:
                    val = key.startswith("xsim")       # fault flags go TRUE, ok-signals go FALSE
                    self.inputs[key] = val
                    d[key] = val
                    inj["_fired"] = True
                    inj["_t"] = self.t
                    self.events.append((self.t, f"inject {inj['type']} at cycle {self.cycle} {self.angle:.1f} deg"))
                    if inj["type"] == "air_loss":
                        # vacuum collapses with the air; glue cannot fire
                        for v in self.valves.values():
                            v.eff = False
                            v.pending = None
                        self._release(self.t, self.angle)
        return d

    # -- one scan
    def step(self, out: dict, dt: float):
        t0, a0 = self.t, self.angle
        for aid, st in self.sup.items():
            a = float(st["spec"]["blend"][0])
            if (self.prev_angle < a <= a0) or (a0 < self.prev_angle and (a > self.prev_angle or a <= a0)):
                st["prev"], st["new"] = st["new"], float(out.get(st["spec"]["tag"].lower(), 0.0))
        self.prev_angle = a0
        running = bool(out.get("xmasterrun"))
        for vid, v in self.valves.items():
            tag = self.valve_tag.get(vid)
            if tag:
                cmd = bool(out.get(tag)) and self.inputs["xairok"]
                v.command(cmd, t0)
        omega = self.omega if running else 0.0

        def angle_at(t):
            return a0 + omega * (t - t0)

        # chronological effective transitions inside (t0, t0+dt]
        evs = []
        for vid, v in self.valves.items():
            if v.pending and v.pending[0] <= t0 + dt:
                evs.append((max(v.pending[0], t0), vid, v.pending[1]))
        evs.sort()
        glue_from = t0 if (self.glue_valve and self.valves[self.glue_valve].eff) else None
        for te, vid, state in evs:
            v = self.valves[vid]
            v.eff, v.pending = state, None
            ang = angle_at(te) % 360.0
            if vid == self.grip_valve:
                self._grip(te, ang) if state else self._release(te, ang)
            if vid == self.glue_valve:
                if state:
                    glue_from = te
                else:
                    if glue_from is not None:
                        self._glue(angle_at(glue_from), angle_at(te))
                    glue_from = None
        if glue_from is not None:
            self._glue(angle_at(glue_from), angle_at(t0 + dt))
        self.t = t0 + dt
        new_angle = a0 + omega * dt
        if new_angle >= 360.0:
            self.cycle += 1
            new_angle -= 360.0
        self.angle = new_angle
        self.running = running

    # -- product events
    def _grip(self, t, ang):
        if self.gripped is not None:
            return
        ok, _ = self.at_port(ang, "pick")
        if not ok or self.stack <= 0 or self._injected("pick_fail"):
            return
        n = 2 if self._injected("double_sheet") else 1
        self.stack -= n
        self.gripped = SheetOutcome(cycle=self.cycle, n=n)

    def _release(self, t, ang):
        s = self.gripped
        if s is None:
            return
        ok, dx = self.at_port(ang, "place", s.cycle)
        _, z = self.carrier(ang)
        on_surface = abs(z - self.ports["place"]["z"]) <= self.ports["place"]["tol_z"] and abs(dx) < 50.0
        if ok or on_surface:
            s.placed, s.dx = True, dx        # registration error (if any) is judged by registration_tol_mm
            if not ok:
                self.events.append((t, f"sheet placed OFF-REGISTER by {dx:+.2f} mm (cycle {s.cycle})"))
        else:
            s.dropped = True
            self.events.append((t, f"sheet DROPPED at {ang:.1f} deg (cycle {s.cycle})"))
        self.outcomes.append(s)
        self.gripped = None

    def _glue(self, a1, a2):
        """Glue effective from angle a1 to a2 (continuous, may exceed 360)."""
        if self._injected("glue_clog"):
            return                      # nozzle clogged: valve opens, nothing comes out
        g = self.glue
        n = max(2, int(abs(a2 - a1) / 0.01))
        on_sheet = []
        machine_mm = 0.0
        prev_x = None
        for k in range(n + 1):
            a = (a1 + (a2 - a1) * k / n) % 360.0
            cx, cz = self.carrier(a)
            step = abs(cx - prev_x) if prev_x is not None else 0.0
            prev_x = cx
            sx = g["nozzle_x"] - cx
            if self.gripped is not None and 0.0 <= sx <= self.L:
                on_sheet.append((sx, cz - g["nozzle_z"]))
            else:
                machine_mm += max(step, 0.01)
        if on_sheet:
            s = self.gripped
            xs = [o[0] for o in on_sheet] + s.bead
            s.bead = [min(xs), max(xs)]
            s.gaps += [o[1] for o in on_sheet]
        if machine_mm:
            self.glue_on_machine_mm += machine_mm
        self.glue_by_cycle[self.cycle] = self.glue_by_cycle.get(self.cycle, 0.0) + len(on_sheet) + machine_mm


def run_scenario(proj: Project, scen: dict, speed_name: str, cph: float, sources: dict) -> CheckResult:
    G, prog, clock, _ = st.load_program(sources, proj.data["sil"]["program"])
    scan = proj.num(proj.data["sil"]["scan_ms"])
    plant = Plant(proj, cph, {**scen, "inject": [dict(i) for i in scen.get("inject", [])]})
    cycles = scen["cycles"]
    states = {0: "IDLE", 1: "RUN", 2: "STOPPING", 9: "FAULT"}
    stop_t = glue_off_t = None
    max_scans = int((cycles + 1) * 360.0 / plant.omega / scan) + 2000
    t = 0.0
    k = 0
    while plant.cycle < cycles and k < max_scans:
        clock.now_ms = t
        plant.inputs["xstartpb"] = t < 50.0
        for name, val in plant.plc_inputs().items():
            setattr(G, name, val)
        prog()
        out = {n: getattr(G, n) for n in ("xmasterrun", *plant.valve_tag.values(),
                                           *[st["spec"]["tag"].lower() for st in plant.sup.values()])}
        inj_t = min([i["_t"] for i in plant.inject if "_t" in i], default=None)
        if inj_t is not None:
            if stop_t is None and not out["xmasterrun"]:
                stop_t = t - inj_t
            gt = plant.valve_tag.get(plant.glue_valve)
            if glue_off_t is None and gt and not out[gt]:
                glue_off_t = t - inj_t
        if k > 100 and not out["xmasterrun"] and int(prog.istate) in (0, 9):
            # stopped; run a little longer to let delays settle, then end
            for _ in range(int(50 / scan)):
                plant.step(out, scan)
            break
        plant.step(out, scan)
        t += scan
        k += 1

    exp = scen["expect"]
    issues, notes = [], []
    placed = [o for o in plant.outcomes if o.placed]
    dropped = [o for o in plant.outcomes if o.dropped]
    final = states.get(int(prog.istate), str(prog.istate))
    notes.append(f"{plant.cycle} cycles, {len(placed)} placed, {len(dropped)} dropped, final {final} "
                 f"(fault {int(prog.ifaultcode)}), glue on machine {plant.glue_on_machine_mm:.1f} mm")
    if "placed" in exp:
        want = exp["placed"]
        if isinstance(want, int) and len(placed) != want:
            issues.append(f"placed {len(placed)} sheets, expected {want}")
        if want == "all":
            if len(placed) < plant.cycle:
                issues.append(f"placed {len(placed)} of {plant.cycle} cycles")
    if "placed_without_glue_max" in exp:
        bare = [o for o in placed if not o.bead]
        if len(bare) > exp["placed_without_glue_max"]:
            issues.append(f"{len(bare)} sheets placed WITHOUT glue (cycles {[o.cycle for o in bare]})")
    if "dropped_max" in exp and len(dropped) > exp["dropped_max"]:
        issues.append(f"{len(dropped)} sheets dropped (max {exp['dropped_max']})")
    if exp.get("registration_follows"):
        notes.append(f"registration measured against each book's own target ({exp['registration_follows']})")
        if placed:
            notes.append(f"worst registration error {max(abs(o.dx) for o in placed):.3f} mm over {len(placed)} books")
    if "registration_tol_mm" in exp:
        bad = [o for o in placed if abs(o.dx) > exp["registration_tol_mm"]]
        if bad:
            issues.append(f"{len(bad)} sheets off register, worst {max(abs(o.dx) for o in bad):.3f} mm")
    if exp.get("bead_in_spec") and plant.glue:
        b = plant.glue["bead"]
        gap = plant.glue["gap"]
        worst = None
        for o in placed:
            if not o.bead:
                issues.append(f"cycle {o.cycle}: placed sheet has no glue")
                continue
            if abs(o.bead[0] - b["start_mm"]) > b["tol_mm"] or abs(o.bead[1] - b["end_mm"]) > b["tol_mm"]:
                issues.append(f"cycle {o.cycle}: bead {o.bead[0]:.2f}-{o.bead[1]:.2f} mm out of spec "
                              f"{b['start_mm']}-{b['end_mm']} +/-{b['tol_mm']}")
            if o.gaps and (min(o.gaps) < gap["min_mm"] or max(o.gaps) > gap["max_mm"]):
                issues.append(f"cycle {o.cycle}: nozzle gap {min(o.gaps):.2f}-{max(o.gaps):.2f} mm out of spec")
            worst = o
        if worst is not None and worst.bead:
            notes.append(f"bead with scan quantisation: {min(o.bead[0] for o in placed if o.bead):.2f}-"
                         f"{max(o.bead[1] for o in placed if o.bead):.2f} mm from edge")
    if "glue_on_machine_mm_max" in exp and plant.glue_on_machine_mm > exp["glue_on_machine_mm_max"]:
        issues.append(f"{plant.glue_on_machine_mm:.1f} mm of glue shot onto the machine")
    for c in exp.get("no_glue_on_cycles", []):
        if plant.glue_by_cycle.get(c):
            issues.append(f"glue fired on cycle {c}")
    if "final_state" in exp and final != exp["final_state"]:
        issues.append(f"final state {final}, expected {exp['final_state']}")
    if "fault_code" in exp and int(prog.ifaultcode) != exp["fault_code"]:
        issues.append(f"fault code {int(prog.ifaultcode)}, expected {exp['fault_code']}")
    if "stop_within_ms" in exp:
        if stop_t is None:
            issues.append("master never stopped after the injected event")
        elif stop_t > exp["stop_within_ms"]:
            issues.append(f"master stopped {stop_t:.1f} ms after the event (max {exp['stop_within_ms']})")
        else:
            notes.append(f"master stop reaction {stop_t:.1f} ms")
    if "glue_off_within_ms" in exp and glue_off_t is not None and glue_off_t > exp["glue_off_within_ms"]:
        issues.append(f"glue output off {glue_off_t:.1f} ms after the event (max {exp['glue_off_within_ms']})")
    for te, msg in plant.events[:6]:
        notes.append(f"t={te:.0f} ms: {msg}")
    return CheckResult(scen["id"], FAIL if issues else PASS, f"{scen['text']} @ {cph:g} cph", issues + notes,
                       speed=speed_name)


def plc_sources(proj: Project) -> dict[str, str]:
    """generated + src + the SIL target only (other targets use vendor types outside the subset)."""
    root = proj.root / "plc"
    target = proj.data.get("sil", {}).get("target", "sim")
    files = [f for f in sorted(root.rglob("*.st"))
             if "targets" not in f.relative_to(root).parts or f.relative_to(root).parts[1] == target]
    return {str(f.relative_to(proj.root)): f.read_text() for f in files}


def run_sil(proj: Project) -> list[CheckResult]:
    if "sil" not in proj.data:
        return []
    results = []
    gen_issues = plcgen.stale(proj)
    results.append(CheckResult("PLC-GEN", FAIL if gen_issues else PASS,
                               "generated GVLs match cycle.yaml / io_list.yaml" if not gen_issues
                               else "generated PLC files out of date", gen_issues))
    sources = plc_sources(proj)
    try:
        _, _, _, code = st.load_program(sources, proj.data["sil"]["program"])
        results.append(CheckResult("PLC-COMPILE", PASS,
                                   f"{len(sources)} ST files parsed and transpiled ({len(code.splitlines())} lines)"))
    except st.STError as e:
        results.append(CheckResult("PLC-COMPILE", FAIL, "Structured Text does not compile", [str(e)]))
        return results
    # stale generated files still run: that is what would be downloaded to the PLC
    speed_map = {"min": proj.speeds[0], "nom": proj.speeds[1], "max": proj.speeds[2]}
    for scen in proj.data["sil"]["scenarios"]:
        for sp in scen.get("speeds", ["nom"]):
            name, cph = speed_map[sp]
            results.append(run_scenario(proj, scen, name, cph, sources))
    return results
