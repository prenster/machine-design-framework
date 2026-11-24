"""Static isometric render of the 3D station at chosen machine angles (matplotlib, no GPU needed)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from .checks import World  # noqa: E402
from .sweep3d import _load_cad, _mesh  # noqa: E402

COLORS = {"machine": "#bdbdbd", "x": "#6a8caf", "xz": "#2b7bb9", "product": "#e0a030", "placed": "#2e9e5b"}


def render(proj, out: Path, angles=(0.0, 129.0, 224.0)):
    a3 = proj.data["assembly3d"]
    parts = _load_cad(proj)
    meshes = {b["id"]: _mesh(parts[b["id"]]) for b in a3["bodies"]}
    frame_of = {b["id"]: b["frame"] for b in a3["bodies"]}
    world = World(proj, proj.speeds[1][1])
    pid = proj.layout["product"]["id"]
    fig = plt.figure(figsize=(10, 3.4 * len(angles)))
    for i, ang in enumerate(angles):
        ax = fig.add_subplot(len(angles), 1, i + 1, projection="3d")
        x, z = world.carrier(ang)
        for bid, m in meshes.items():
            fr = frame_of[bid]
            if bid == pid and not world.gripped(ang):
                continue
            off = [0.0, 0.0, 0.0]
            if fr in ("x", "xz", "product"):
                off[0] = x
            if fr in ("xz", "product"):
                off[2] = z
            tris = m.vertices[m.faces] + off
            ax.add_collection3d(Poly3DCollection(tris, facecolor=COLORS.get(fr, "#999"), edgecolor="#444",
                                                 linewidths=0.15, alpha=0.55 if fr == "machine" else 0.9))
        ax.set_xlim(-160, 860); ax.set_ylim(-260, 260); ax.set_zlim(-60, 170)
        ax.set_box_aspect((1020, 520, 230), zoom=0.95)
        ax.view_init(elev=22, azim=-62)
        ax.set_axis_off()
        ax.text2D(0.02, 0.85, f"{ang:.0f}°", transform=ax.transAxes, fontsize=13)
    fig.suptitle("Station 3D (build123d) at pick, glue and place: grey static, blue moving, orange sheet", fontsize=12)
    fig.subplots_adjust(left=0, right=1, top=0.95, bottom=0, hspace=-0.15)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
