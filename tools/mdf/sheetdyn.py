"""Flexible sheet dynamics on a vacuum carrier (side view).

The sheet is an Euler-Bernoulli beam (per unit width) discretised with Hermite cubic elements.
Nodes under the vacuum plate are clamped to the carrier. The overhangs are free and respond to:
  - gravity
  - carrier vertical acceleration (base excitation)
  - aerodynamic drag on vertical motion:  q = -0.5 * rho * Cd * v|v|
  - Rayleigh damping set from a modal damping ratio

Output: deflection w(x, theta) relative to the carrier, used by the planar sweep (deformed product
polygon) and by the glue check (true nozzle gap under a drooping edge).

What this model does NOT capture (state it in every report):
  - aeroelastic flutter from edgewise airflow (leading-edge lift/instability) -> high-speed video test
  - in-plane buckling of an overhang under X deceleration
  - curl, humidity, grain-direction variation beyond the E value you give it
  - air cushion / squeeze film at pick and place
Calibrate D (bending stiffness) with the cantilever droop test and damping with video.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .motion import omega_deg_s

G = 9.81


@dataclass
class SheetResult:
    x_nodes: np.ndarray          # mm, carrier frame
    thetas: np.ndarray           # deg, sample angles (inside grip window)
    w: np.ndarray                # mm, shape (len(thetas), n_nodes), + = up
    first_mode_hz: float
    clamp: tuple[float, float]

    def deflection(self, theta: float) -> np.ndarray | None:
        """Nodal deflection at theta (nearest sample), None if outside grip window."""
        if len(self.thetas) == 0:
            return None
        d = np.abs(((self.thetas - theta) + 180.0) % 360.0 - 180.0)
        i = int(np.argmin(d))
        if d[i] > 0.6:
            return None
        return self.w[i]

    def at(self, theta: float, x: float) -> float:
        w = self.deflection(theta)
        if w is None:
            return 0.0
        return float(np.interp(x, self.x_nodes, w))

    def envelope(self) -> tuple[float, float, float, float]:
        """(min w, theta at min, max w, theta at max)."""
        i_min = np.unravel_index(np.argmin(self.w), self.w.shape)
        i_max = np.unravel_index(np.argmax(self.w), self.w.shape)
        return (float(self.w[i_min]), float(self.thetas[i_min[0]]),
                float(self.w[i_max]), float(self.thetas[i_max[0]]))


def _beam_matrices(n_el: int, le: float, D: float, m: float):
    """Global K, M for a beam of n_el elements, length le each (SI, per unit width)."""
    ndof = 2 * (n_el + 1)
    K = np.zeros((ndof, ndof))
    M = np.zeros((ndof, ndof))
    k = D / le**3 * np.array([[12, 6 * le, -12, 6 * le],
                              [6 * le, 4 * le**2, -6 * le, 2 * le**2],
                              [-12, -6 * le, 12, -6 * le],
                              [6 * le, 2 * le**2, -6 * le, 4 * le**2]])
    mm = m * le / 420 * np.array([[156, 22 * le, 54, -13 * le],
                                  [22 * le, 4 * le**2, 13 * le, -3 * le**2],
                                  [54, 13 * le, 156, -22 * le],
                                  [-13 * le, -3 * le**2, -22 * le, 4 * le**2]])
    for e in range(n_el):
        idx = slice(2 * e, 2 * e + 4)
        K[idx, idx] += k
        M[idx, idx] += mm
    return K, M


def simulate(proj, world, supported=lambda theta: False) -> SheetResult | None:
    """Simulate the sheet over the grip window at world.cph. None if sheet params are absent."""
    p = proj.data["params"]["params"]
    if "sheet_bending_stiffness_mNm" not in p:
        return None
    D = proj.param("sheet_bending_stiffness_mNm") * 1e-3         # N*m (per m width)
    m = proj.param("sheet_grammage_gsm") * 1e-3                    # kg/m^2
    zeta = proj.param("sheet_damping_ratio")
    cd = proj.param("sheet_drag_coefficient")
    rho = 1.2

    poly = world.product_poly
    x0, _, x1, _ = poly.bounds
    plate = None
    for bid, b in world.carrier_bodies:
        if bid == proj.layout["product"].get("held_by", "vacuum_plate"):
            plate = b.bounds
    if plate is None:
        plate = world.carrier_bodies[0][1].bounds
    c0, c1 = max(plate[0], x0), min(plate[2], x1)

    n_el = max(20, int(round((x1 - x0) / 2.0)))
    le_mm = (x1 - x0) / n_el
    xn = x0 + le_mm * np.arange(n_el + 1)
    K, M = _beam_matrices(n_el, le_mm / 1000.0, D, m)
    ndof = K.shape[0]
    clamped = [i for i, x in enumerate(xn) if c0 - 1e-9 <= x <= c1 + 1e-9]
    fixed = set()
    for i in clamped:
        fixed |= {2 * i, 2 * i + 1}
    free = np.array([d for d in range(ndof) if d not in fixed])
    Kf, Mf = K[np.ix_(free, free)], M[np.ix_(free, free)]

    # first mode and Rayleigh damping (mass+stiffness proportional, zeta at modes 1 and 2)
    evals = np.sort(np.real(np.linalg.eigvals(np.linalg.solve(Mf, Kf))))
    evals = evals[evals > 1e-9]
    w1 = math.sqrt(evals[0])
    w2 = math.sqrt(evals[1]) if len(evals) > 1 else 3 * w1
    a_r = 2 * zeta * w1 * w2 / (w1 + w2)
    b_r = 2 * zeta / (w1 + w2)
    Cf = a_r * Mf + b_r * Kf

    # nodal load vector for a uniform pressure q (per unit width): consistent load
    def load_vec(q_nodes):
        f = np.zeros(ndof)
        for e in range(n_el):
            le = le_mm / 1000.0
            q = 0.5 * (q_nodes[e] + q_nodes[e + 1])
            f[2 * e:2 * e + 4] += q * np.array([le / 2, le**2 / 12, le / 2, -le**2 / 12])
        return f[free]

    omega = omega_deg_s(world.cph)
    on, off = world.grip
    span = (off - on) % 360.0
    dt = min(1e-4, 0.05 / omega)  # s; <= 0.05 deg per step
    n_steps = int(math.ceil(span / omega / dt))
    beta, gam = 0.25, 0.5
    Keff = Kf + gam / (beta * dt) * Cf + 1 / (beta * dt**2) * Mf
    Keff_inv = np.linalg.inv(Keff)
    u = np.zeros(len(free))
    v = np.zeros(len(free))
    # initial: sheet resting flat (supported by stack) -> released at grip, so start at rest, w=0
    def accel_base(theta):
        _, _, az = world.ax_z.eval(theta)
        _, vz, _ = world.ax_z.eval(theta)
        return az * omega**2 / 1000.0, vz * omega / 1000.0   # m/s^2, m/s

    def ext_force(theta, u_full_vel_w):
        az, vz = accel_base(theta)
        v_abs = vz + u_full_vel_w   # m/s at nodes
        q = -m * (G + az) - 0.5 * rho * cd * v_abs * np.abs(v_abs)
        return load_vec(q)

    def nodal_w(vec):
        full = np.zeros(ndof)
        full[free] = vec
        return full[0::2]

    F = ext_force(on, nodal_w(v))
    a = np.linalg.solve(Mf, F - Cf @ v - Kf @ u)
    thetas, ws = [], []
    sample_every = max(1, int(round(0.25 / (omega * dt))))
    for k in range(n_steps + 1):
        theta = (on + k * dt * omega) % 360.0
        if k % sample_every == 0:
            thetas.append(theta)
            ws.append(nodal_w(u) * 1000.0)
        theta_n = (on + (k + 1) * dt * omega) % 360.0
        F = ext_force(theta_n, nodal_w(v))
        rhs = F + Mf @ (u / (beta * dt**2) + v / (beta * dt) + (1 / (2 * beta) - 1) * a) \
                + Cf @ (gam / (beta * dt) * u + (gam / beta - 1) * v + dt * (gam / (2 * beta) - 1) * a)
        u_new = Keff_inv @ rhs
        a_new = (u_new - u) / (beta * dt**2) - v / (beta * dt) - (1 / (2 * beta) - 1) * a
        v = v + dt * ((1 - gam) * a + gam * a_new)
        u, a = u_new, a_new
        if supported(theta_n):
            # sheet lying on the stack (pick) or pressed onto the signature (place): flat, at rest
            u[:] = 0.0
            v[:] = 0.0
            a[:] = 0.0
    return SheetResult(x_nodes=xn, thetas=np.array(thetas), w=np.array(ws),
                       first_mode_hz=w1 / (2 * math.pi), clamp=(c0, c1))
