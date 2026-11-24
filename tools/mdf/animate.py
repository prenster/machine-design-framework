"""Cycle animation: 3D station + timing strip, rendered to MP4 with no CAD software.

    python mdf.py animate [PROJECT] [--variant V] [--cycles N] [--frames-per-cycle F]

Everything comes from the same data the checks use (cycle.yaml motion and valve timing, layout/CAD,
valve delays at nominal speed), so the video shows the design as verified, not a separate drawing.
The caption shows the active segment notes from cycle.yaml, so the narrative is the design's own.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from .checks import World, in_window  # noqa: E402
from .motion import omega_deg_s  # noqa: E402
from .sweep3d import _load_cad, _mesh  # noqa: E402

COL = {"machine": "#c4c4c4", "x": "#6a8caf", "xz": "#2b7bb9", "product": "#e0a030", "placed": "#2e9e5b"}


def _note(axis, theta):
    for seg, spec in zip(axis.segments, axis.spec["segments"]):
        if seg.start <= theta < seg.end:
            return spec.get("note", "")
    return ""


def animate(proj, out: Path, cycles: int = 1, frames_per_cycle: int = 180, fps: int = 30) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH (Windows: winget install ffmpeg)")
    a3 = proj.data["assembly3d"]
    parts = _load_cad(proj)
    meshes = {b["id"]: _mesh(parts[b["id"]]) for b in a3["bodies"]}
    frame_of = {b["id"]: b["frame"] for b in a3["bodies"]}
    frames = a3["frames"]
    cph = proj.speeds[1][1]
    w = World(proj, cph)
    pid = proj.layout["product"]["id"]
    glue = proj.layout.get("glue")
    gwin = w.valve_window(glue["valve"]) if glue else None
    cyc_s = 360.0 / omega_deg_s(cph)
    slow = (frames_per_cycle / fps) / cyc_s
    # timing strip data
    th = np.linspace(0, 360, 721)
    xs = [w.carrier(t)[0] for t in th]
    zs = [w.carrier(t)[1] for t in th]
    tmp = Path(tempfile.mkdtemp())
    n = cycles * frames_per_cycle
    for k in range(n):
        theta = (k * 360.0 / frames_per_cycle) % 360.0
        fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
        ax = fig.add_axes([-0.12, 0.17, 1.24, 0.78], projection="3d")
        x, z = w.carrier(theta)
        for bid, m in meshes.items():
            fr = frame_of[bid]
            if bid == pid:
                if w.gripped(theta):
                    off = (x, 0.0, z)
                    color = COL["product"]
                elif w.placed(theta):
                    px, pz = w.placed_pose(theta)
                    off, color = (px, 0.0, pz), COL["placed"]
                else:
                    continue
            else:
                f = frames.get(fr, {})
                off = (w.apos(f.get("x"), theta), w.apos(f.get("y"), theta), w.apos(f.get("z"), theta))
                color = COL.get(fr, "#999")
            ax.add_collection3d(Poly3DCollection(m.vertices[m.faces] + off, facecolor=color, edgecolor="#555",
                                                 linewidths=0.1, alpha=0.5 if fr == "machine" else 0.95))
        if gwin and in_window(theta, gwin) and w.gripped(theta):
            ax.scatter([glue["nozzle_x"]], [0], [glue["nozzle_z"] + 2], s=120, c="#ff3b30", depthshade=False)
        ax.set_xlim(-160, 860); ax.set_ylim(-260, 260); ax.set_zlim(-60, 170)
        ax.set_box_aspect((1020, 520, 230), zoom=1.55)
        ax.view_init(elev=24, azim=-60 + 10 * np.sin(np.radians(theta)))
        ax.set_axis_off()
        nx = _note(w.ax_x, theta)
        nz = _note(w.ax_z, theta)
        state = "GRIPPED" if w.gripped(theta) else ("placed" if w.placed(theta) else "")
        fig.text(0.02, 0.95, f"{proj.data['requirements'].get('station', proj.root.name)}", fontsize=12, weight="bold")
        fig.text(0.02, 0.915, f"{theta:5.1f}°   @ {cph:g} cph, shown at {slow:.2f}x speed   {state}", fontsize=11,
                 family="monospace")
        fig.text(0.02, 0.88, f"X: {nx}" + (f"   |   Z: {nz}" if nz else ""), fontsize=10, color="#333")
        # timing strip
        tx = fig.add_axes([0.06, 0.08, 0.88, 0.14])
        tx.plot(th, xs, lw=1.5, label="X (mm)")
        tz = tx.twinx()
        tz.plot(th, zs, lw=1.2, color="#d98c1f", label="Z (mm)")
        for v, (on, off), c in [(w.grip_valve, w.grip, "#2e9e5b")] + ([(glue["valve"], gwin, "#ff3b30")] if glue else []):
            if on <= off:
                tx.axvspan(on, off, ymin=0.0, ymax=0.08, color=c, alpha=0.7)
            else:
                tx.axvspan(on, 360, ymin=0.0, ymax=0.08, color=c, alpha=0.7)
                tx.axvspan(0, off, ymin=0.0, ymax=0.08, color=c, alpha=0.7)
        tx.axvline(theta, color="k", lw=1.5)
        tx.set_xlim(0, 360)
        tx.set_xlabel("machine angle (deg)   green bar: vacuum effective   red bar: glue effective", fontsize=9)
        tx.set_ylabel("X mm")
        tz.set_ylabel("Z mm")
        fig.savefig(tmp / f"f{k:05d}.png")
        plt.close(fig)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(out)],
                   check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out
