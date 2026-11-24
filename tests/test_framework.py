"""Unit tests for framework mechanics not fully exercised by the examples.

Each test checks one behaviour in both directions where possible: the good case passes AND a planted
fault fails. Run: `make test` (CI runs it on every push).
"""
from __future__ import annotations

import copy
import math
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from mdf import checks, motion, st  # noqa: E402
from mdf.checks import FAIL, PASS  # noqa: E402
from mdf.project import load  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "conveyor"
EXAMPLE = ROOT / "examples" / "pick-glue-place"


def fixture():
    return load(FIX)


def reload_axes(p):
    for aid, spec in p.cycle["axes"].items():
        p.axes[aid] = motion.Axis(aid, spec)


# ---------------------------------------------------------------- motion
def test_offset_profile_returns_to_zero():
    f = lambda t: motion.offset_profile(t, (150, 205), (270, 335), 12.0)  # noqa: E731
    assert f(100) == 0.0
    assert f(240) == pytest.approx(12.0)
    assert f(350) == pytest.approx(0.0)
    assert 0.0 < f(170) < 12.0


def test_incremental_axis_wraps_with_pitch():
    p = fixture()
    res = {r.summary.split(":")[0]: r.status for r in checks.check_cycle_law(p)}
    assert res["axis conveyor"] == PASS
    p.cycle["axes"]["conveyor"].pop("incremental_pitch")
    reload_axes(p)
    res = {r.summary.split(":")[0]: r.status for r in checks.check_cycle_law(p)}
    assert res["axis conveyor"] == FAIL          # without the pitch, 400 -> 0 is a position jump


# ---------------------------------------------------------------- hand-offs
def test_flying_handoff_matched():
    p = fixture()
    r = [r for r in checks.check_handoffs(p)]
    assert r and all(x.status == PASS for x in r), [x.details for x in r]


def test_flying_handoff_mismatch_detected():
    p = fixture()
    p.cycle["valves"]["grip"]["off"] = 220           # release while carrier decelerates, conveyor accelerates
    r = checks.check_handoffs(p)
    assert any(x.status == FAIL for x in r)
    assert any("velocity mismatch" in d or "position mismatch" in d for x in r for d in x.details)


def test_matched_flying_handoff_tolerates_release_delay():
    """In a matched-velocity hand-off both frames move together, so a late release lands in the same place."""
    p = fixture()
    p.cycle["valves"]["grip"]["off_delay"] = 30      # 30 ms = 5.4 deg late at max speed, still inside the shared window
    assert all(x.status == PASS for x in checks.check_handoffs(p))


def test_static_place_is_delay_sensitive():
    """Releasing onto a stationary target while the carrier still moves is not delay tolerant."""
    p = fixture()
    p.layout["handoffs"] = [{"id": "HO-STATIC", "from": "carrier", "to": "port:place", "at": "grip.off",
                             "tol_mm": 0.3, "vel_tol_mm_s": 5}]
    assert any(x.status == FAIL for x in checks.check_handoffs(p))


# ---------------------------------------------------------------- frames in the sweep
def test_conveyor_bodies_swept():
    p = fixture()
    assert all(r.status == PASS for r in checks.check_sweep(p)), [r.details for r in checks.check_sweep(p)]
    p.layout["moving"][0]["polygon"] = [[200, -10], [205, -10], [205, 5], [200, 5]]   # tall cleat
    res = checks.check_sweep(p)
    assert any(r.status == FAIL for r in res)
    assert any("cleat#1" in d for r in res for d in r.details)    # caught on the NEXT cleat (upstream copy)


def test_placed_product_rides_conveyor():
    p = fixture()
    w = checks.World(p, 2000)
    x1, _ = w.placed_pose(150)
    x2, _ = w.placed_pose(200)
    assert x2 > x1 + 40                              # it moves with the belt after release


# ---------------------------------------------------------------- example: per-book offset in static checks
def test_offset_case_moves_place_port_only():
    p = load(EXAMPLE, "large_offset_max")
    w = checks.World(p, 2400)
    assert w.carrier(0)[0] == pytest.approx(0.0, abs=1e-9)        # pick unaffected (offset returned)
    assert w.carrier(230)[0] == pytest.approx(615.0, abs=1e-6)    # place shifted by the 15 mm case
    assert w.port("place")[0] == pytest.approx(615.0)


# ---------------------------------------------------------------- ST transpiler
ST_SRC = """
VAR_GLOBAL
    gIn : BOOL;
    gOut : INT;
END_VAR
FUNCTION Twice : INT
VAR_INPUT x : INT; END_VAR
Twice := x * 2;
END_FUNCTION
PROGRAM MAIN
VAR
    t : TON;
    n : INT := 0;
END_VAR
t(IN := gIn, PT := T#10MS);
CASE n OF
0: IF t.Q THEN n := 1; END_IF;
1, 2: n := Twice(n) + 1;
ELSE
    n := 99;
END_CASE;
gOut := n;
END_PROGRAM
"""


def test_st_timer_case_function():
    G, prog, clock, _ = st.load_program({"t.st": ST_SRC})
    G.gin = True
    outs = []
    for k in range(15):
        clock.now_ms = float(k)
        prog()
        outs.append(G.gout)
    assert outs[0] == 0 and outs[-1] == 99
    assert 1 in outs or 3 in outs


def test_st_rejects_unknown_identifier():
    with pytest.raises(st.STError):
        st.load_program({"t.st": ST_SRC.replace("gOut := n;", "gOut := nope;")})


def test_st_rejects_loops():
    with pytest.raises(st.STError):
        st.load_program({"t.st": ST_SRC.replace("gOut := n;", "FOR n := 1 TO 3 DO gOut := n; END_FOR;")})


# ---------------------------------------------------------------- cams and stacks
def test_cam_dwell_curvature_is_prime_radius():
    from mdf.cam import analyse
    p = load(EXAMPLE, "nominal")
    a = analyse(p, "jogger")
    dwell = a["s"] < 1e-9
    assert float(sorted(a["rho"][dwell])[len(a["rho"][dwell]) // 2]) == pytest.approx(a["rp"], rel=1e-3)


def test_stack_rss_matches_hand_calc(tmp_path):
    from mdf.stacks import run_stacks
    p = load(EXAMPLE, "nominal")
    p.data["stacks"] = {"stacks": [{"id": "STK-T", "text": "t", "target": {"tol": 1.0}, "contributors": [
        {"name": "a", "tol": 0.3, "source": "x"}, {"name": "b", "tol": 0.4, "source": "x"}]}]}
    r = run_stacks(p)[0]
    assert "WC +/-0.700" in r.summary and "RSS +/-0.500" in r.summary and r.status == PASS


# ---------------------------------------------------------------- integrity
def test_lock_detects_weakened_check(tmp_path):
    from mdf.integrity import check_lock, write_lock
    dst = tmp_path / "proj"
    shutil.copytree(EXAMPLE, dst, ignore=shutil.ignore_patterns("build"))
    write_lock(load(dst, "nominal"), approved_by="test")
    assert check_lock(load(dst, "nominal"))[0].status == PASS
    lay = (dst / "layout.yaml").read_text().replace("default_min_mm: 2.0", "default_min_mm: 0.5")
    (dst / "layout.yaml").write_text(lay)
    r = check_lock(load(dst, "nominal"))[0]
    assert r.status == FAIL and any("default_min_mm: 2.0 -> 0.5" in d for d in r.details)


# ---------------------------------------------------------------- line integration timing
def test_per_book_value_must_be_sampled_before_blend():
    from mdf.line import check_line
    p = load(EXAMPLE, "nominal")
    assert check_line(p)[0].status != FAIL
    p.cycle["sensors"]["host_spine"]["check_at"] = 160          # after the 150 deg blend start: too late
    r = check_line(p)[0]
    assert r.status == FAIL and any("blend starts" in d for d in r.details)
