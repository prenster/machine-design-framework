"""Station 3D geometry (build123d). Units mm.

Frames (see assembly3d.yaml):
  machine - static
  x       - moves with x_transfer only   (coordinates given at carrier x = 0)
  xz      - moves with x_transfer + z_lift (coordinates given at carrier x = 0, z = 0)
  product - the endsheet, carried while gripped (carrier frame)

Simple prismatic solids are deliberate at concept stage: envelopes, not detailed parts.
Replace each envelope with the catalog STEP model (or a detailed custom part) as the design matures;
body ids must stay the same so clearance rules and the BOM links keep working.
"""
from build123d import Box, Pos


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def build(p: dict) -> dict:
    t = p["sheet_thickness_mm"]
    return {
        # ---- machine (static) ----
        "table":              box(-160, 860, -180, 180, -50, -40),
        "stack":              box(0, 150, -100, 100, -40, 0),
        "stack_fence":        box(152, 156, -100, 100, -40, 6),
        "side_guide_l":       box(0, 150, 101, 105, -40, 5),
        "side_guide_r":       box(0, 150, -105, -101, -40, 5),
        "nozzle_body":        box(300, 310, -95, 95, -30, -1),       # glue jet bar, tips at z = -1
        "glue_bracket_l":     box(298, 312, 95, 125, -40, -10),
        "glue_bracket_r":     box(298, 312, -125, -95, -40, -10),
        "signature":          box(600, 770, -110, 110, -25, 0),
        "conveyor":           box(580, 820, -130, 130, -40, -25),
        "signature_backstop": box(594, 598, -110, 110, -25, 4),
        "beam":               box(-140, 840, -25, 25, 110, 150),     # X module body
        "upright_l":          box(-160, -120, -25, 25, -40, 110),
        "upright_r":          box(820, 860, -25, 25, -40, 110),
        # ---- x frame ----
        "carriage":           box(10, 140, 25, 35, 100, 160),
        "z_module":           box(50, 100, 35, 75, 45, 160),       # body bottom clears the bracket at full lift
        # ---- xz frame ----
        "z_slide":            box(55, 95, 75, 85, 12, 90),
        "z_bracket":          box(50, 100, -10, 85, 12, 20),
        "vacuum_plate":       box(5, 145, -90, 90, 0.15, 12),
        "ejector":            box(115, 135, -60, -40, 12, 30),
        # ---- product ----
        "endsheet":           box(0, 150, -100, 100, 0, t),
    }
