# Actuation policy: mechanical cam > servo > pneumatic

Default order for a new machine (`cycle.yaml: actuation_preference`). Anything below the first choice needs an
`actuation_reason`; ACT-POLICY fails without one, and every reason is listed for review in each report.

## Why cams first

A mechanical cam *is* its motion law. Nothing to tune, nothing to lose at power-up, and the follower is
geometrically locked to the main shaft, so timing cannot drift between stations. Cam-driven indexers still
outnumber servo-driven ones in assembly automation because they are reliable, durable and simple to run; the
profile is set by the cam, not by a controls engineer. MDF designs cams from the same `cycle.yaml` motion law as
servo axes, checks them (pressure angle, curvature/undercut, Hertz stress, follower jump, roller life, camshaft
torque) and exports the profile (DXF/CSV/STEP) for the machinist.

## Where a servo is the better answer (push back here)

- **Long strokes.** A plate cam's size grows with stroke; beyond ~100-150 mm use a cam-driven linkage or a servo.
  The example's 600 mm X transfer would need a ~1.3 m cam.
- **Format changeovers.** A new format means a new cam (or an adjustable linkage). If formats change weekly,
  an electronic cam is a parameter change.
- **Motion that must change at run time** (registration correction, skip-a-cycle, variable dwell).
- **Axes riding on other axes**, where a camshaft can't reach.
- A good hybrid: **one main shaft (servo or gearmotor as an electronic line shaft) driving mechanical cams for the
  short, tightly-coupled motions**, plus servo axes only where the list above applies.

## Where pneumatics are the right answer

- **Vacuum generation and blow-off** (ejectors): not motion, no alternative worth having.
- **Clamping/holding to a force, not a position**, where force control is the point and stroke timing doesn't matter.
- **Rarely-moved adjustments** (format stops moved at changeover).
- **Safe-state behaviour** that needs stored energy, or deliberately has none (dump valves).

Avoid pneumatics for timed motion inside the machine cycle: response varies with supply pressure, temperature,
seal wear and load, so its timing drifts in degrees with speed and with age. When a pneumatic actuator is unavoidable,
its response time is an assumed parameter with a physical test, like every other delay.

## Cam design limits used by the checks (sources)

| Limit | Value | Source |
|---|---|---|
| Pressure angle, translating follower | ≤ 30° | Norton, *Design of Machinery*; Iowa State ME325 notes |
| Pressure angle, oscillating follower | ≤ 35° | Norton (oscillating followers: not yet implemented in MDF) |
| Pitch radius / roller radius | target ≥ 2, floor 1.5; < 1 undercuts | Norton; check Hertz stress when small |
| Roller life | L10 = (C/P)^(10/3) × 10^6 rev | roller bearing life (McGill / ISO 281) |
