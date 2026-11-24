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
from .report import assumption_audit, markdown, overall, side_view_svg, traceability


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mdf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="run every check on a station project")
    v.add_argument("project")
    v.add_argument("--out", default=None, help="output dir (default <project>/build)")
    g = sub.add_parser("plc", help="regenerate PLC GVLs from cycle.yaml / io_list.yaml")
    g.add_argument("project")
    args = ap.parse_args(argv)

    if args.cmd == "plc":
        from . import plcgen
        for pth in plcgen.write(load(args.project)):
            print(f"wrote {pth}")
        return 0

    try:
        proj = load(args.project)
    except ProjectError as e:
        print(f"PROJECT ERROR: {e}", file=sys.stderr)
        return 2

    results = run_all(proj)
    trace = traceability(proj, results)
    audit = assumption_audit(proj)
    out = Path(args.out) if args.out else proj.root / "build"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(markdown(proj, results, trace, audit))
    side_view_svg(proj, out / "side_view.svg")
    if "assembly3d" in proj.data:
        try:
            from .render3d import render
            render(proj, out / "station_3d.png")
        except Exception as e:  # noqa: BLE001 - preview only
            print(f"(3D preview skipped: {e})")

    for r in results:
        print(f"[{r.status:4}] {r.check_id:16} {r.speed or '':4} {r.summary}")
        if r.status != "PASS":
            for d in r.details:
                if not d.startswith(("tightest OK", "t=")) and "-> effective" not in d:
                    print(f"         - {d}")
    for t in trace:
        if t["status"] != "PASS":
            print(f"[{t['status']:4}] {t['id']:16} {t['note']}")
    pending = sum(1 for a in audit if a["status"] == "PENDING")
    print(f"\n{pending} assumed parameters awaiting physical calibration (see report).")
    verdict = overall(results, trace, audit)
    print(f"VERDICT: {verdict}   report: {out / 'report.md'}")
    return 1 if verdict == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
