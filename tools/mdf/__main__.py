"""mdf CLI.

    python -m mdf verify <project_dir> [--out <dir>]

Exit code 0 = no FAIL (PENDING physical tests allowed), 1 = FAIL, 2 = project error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import FAIL, run_all
from .project import ProjectError, load
from .report import RANK, assumption_audit, markdown, overall, side_view_svg, traceability


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mdf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="run every check on a station project")
    v.add_argument("project")
    v.add_argument("--out", default=None, help="output dir (default <project>/build)")
    v.add_argument("--variant", default=None, help="run one product variant (default: all variants defined)")
    v.add_argument("--gate", default=None, choices=["G1", "G2", "G3", "G4", "G5"],
                   help="enforce fidelity/actions required for this gate")
    g = sub.add_parser("plc", help="regenerate PLC GVLs from cycle.yaml / io_list.yaml")
    g.add_argument("project")
    lk = sub.add_parser("lock", help="approve current check definitions (chief engineer only)")
    lk.add_argument("project")
    lk.add_argument("--by", default=None, help="approver's name (a person). Omit to write an unreviewed baseline.")
    ck = sub.add_parser("checks", help="print the current check definitions in readable form (for review)")
    ck.add_argument("project")
    an = sub.add_parser("animate", help="render the machine cycle to MP4 (3D + timing strip)")
    an.add_argument("project")
    an.add_argument("--variant", default=None)
    an.add_argument("--cycles", type=int, default=1)
    an.add_argument("--frames-per-cycle", type=int, default=180)
    an.add_argument("--out", default=None)
    nw = sub.add_parser("new", help="scaffold a station project from the reference example")
    nw.add_argument("dest")
    cc = sub.add_parser("claimcheck", help="fail unless the last verify is current and not FAIL")
    cc.add_argument("projects", nargs="+")
    args = ap.parse_args(argv)

    if args.cmd == "animate":
        from .animate import animate
        from .project import variants as list_variants
        v = args.variant or (list_variants(args.project) or [None])[0]
        proj = load(args.project, v)
        out = Path(args.out) if args.out else proj.root / "build" / f"cycle{'-' + v if v else ''}.mp4"
        print(f"wrote {animate(proj, out, args.cycles, args.frames_per_cycle)}")
        return 0
    if args.cmd == "new":
        import shutil
        src = Path(__file__).resolve().parents[2] / "examples" / "pick-glue-place"
        dest = Path(args.dest)
        if dest.exists():
            print(f"{dest} exists; refusing to overwrite")
            return 2
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("build", "checks.lock", "__pycache__"))
        (dest / "intake").mkdir(exist_ok=True)
        (dest / "intake" / "QUESTIONS.md").write_text("# Open questions\n\n(filled by the mdf-intake skill)\n")
        (dest / "README.md").write_text(
            "# New station (scaffolded from examples/pick-glue-place)\n\n"
            "Every file still describes the reference example. Replace them in the order in\n"
            "templates/README.md, starting from the intake (skill mdf-intake). Until then, treat\n"
            "everything here as placeholder. No checks.lock yet: run `make lock` after approval.\n")
        print(f"scaffolded {dest}")
        return 0
    if args.cmd == "lock":
        from .integrity import write_lock
        path = write_lock(load(args.project), args.by)
        print(f"wrote {path} and CHECKS.md " + (f"(approved by {args.by})" if args.by else "(UNREVIEWED baseline)"))
        return 0
    if args.cmd == "checks":
        from .integrity import readable
        print(readable(load(args.project)))
        return 0
    if args.cmd == "claimcheck":
        from .integrity import claimcheck
        bad = 0
        for pdir in args.projects:
            ok, msg = claimcheck(Path(pdir))
            print(("OK   " if ok else "STOP ") + msg)
            bad += not ok
        return 1 if bad else 0

    if args.cmd == "plc":
        from . import plcgen
        for pth in plcgen.write(load(args.project)):
            print(f"wrote {pth}")
        return 0

    from .project import variants as list_variants
    try:
        vlist = [args.variant] if args.variant else (list_variants(args.project) or [None])
    except (OSError, ProjectError) as e:
        print(f"PROJECT ERROR: {e}", file=sys.stderr)
        return 2
    base_out = Path(args.out) if args.out else Path(args.project) / "build"
    verdicts, all_results = [], []
    for variant in vlist:
        if variant:
            print(f"\n===== variant: {variant} =====")
        out = base_out / f"variant-{variant}" if variant and len(vlist) > 1 else base_out
        rc = _verify_one(args, variant, out, verdicts, all_results)
        if rc == 2:
            return 2
    verdict = max(verdicts, key=lambda v: RANK.get(v, 3))
    from .integrity import write_verify_record
    root = Path(args.project)
    (root / "build").mkdir(exist_ok=True)
    write_verify_record(root, root / "build", verdict, all_results)   # claim record always lives with the project
    if len(vlist) > 1:
        print(f"\nVARIANTS: " + ", ".join(f"{v}={d}" for v, d in zip(vlist, verdicts)))
    print(f"OVERALL VERDICT: {verdict}")
    return 1 if verdict == FAIL else 0


def _verify_one(args, variant, out, verdicts, all_results) -> int:
    try:
        proj = load(args.project, variant)
    except ProjectError as e:
        print(f"PROJECT ERROR: {e}", file=sys.stderr)
        return 2
    results = run_all(proj)
    trace = traceability(proj, results)
    audit = assumption_audit(proj)
    out.mkdir(parents=True, exist_ok=True)
    from .actions import build as build_actions
    actions = build_actions(proj, results)
    verdict = overall(results, trace, audit)
    blocking = [a for a in actions if args.gate and a.blocks_by(args.gate)]
    if blocking:
        verdict = "FAIL"
    (out / "report.md").write_text(markdown(proj, results, trace, audit, actions, args.gate, verdict))
    side_view_svg(proj, out / "side_view.svg")
    if "assembly3d" in proj.data:
        try:
            from .render3d import render
            render(proj, out / "station_3d.png")
        except Exception as e:  # noqa: BLE001 - preview only
            print(f"(3D preview skipped: {e})")
    for r in results:
        print(f"[{r.status:4}] {r.check_id:16} {r.speed or '':4} {r.summary}")
        if r.status not in ("PASS", "ACCEPTED"):
            for d in r.details:
                if not d.startswith(("tightest OK", "t=")) and "-> effective" not in d:
                    print(f"         - {d}")
    for t in trace:
        if t["status"] != "PASS":
            print(f"[{t['status']:4}] {t['id']:16} {t['note']}")
    pending = sum(1 for a in audit if a["status"] == "PENDING")
    print(f"\n{pending} assumed parameters awaiting physical calibration (see report).")
    kinds = {}
    for a in actions:
        kinds[a.kind] = kinds.get(a.kind, 0) + 1
    print("human actions: " + (", ".join(f"{v} {k}" for k, v in sorted(kinds.items())) or "none"))
    for a in [a for a in actions if a.priority == 1][:8]:
        print(f"  [{a.kind}] {a.item}: {a.why} (blocks {a.blocks})")
    if args.gate:
        print(f"gate {args.gate}: {len(blocking)} blocking actions")
    print(f"VERDICT{' [' + variant + ']' if variant else ''}: {verdict}   report: {out / 'report.md'}")
    verdicts.append(verdict)
    all_results.extend(results)
    return 0

if __name__ == "__main__":
    sys.exit(main())
